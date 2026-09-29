"""
Talks to AI providers, with automatic fallback.

Almost every AI provider now speaks the same "OpenAI-compatible" language:
the same request format, just a different web address (base_url), key and
model names. So ONE piece of code can talk to all of them.

The providers are tried from top to bottom. If one is busy, out of free
requests, or broken, we quietly move on to the next. Providers without a key
in your .env file are simply skipped.
"""

import os
import time
from dotenv import load_dotenv
from openai import (
    OpenAI,
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    RateLimitError,
    APIStatusError,
    APIConnectionError,
)

load_dotenv()

# ── The fallback chain ────────────────────────────────────────
# key      = the name of the variable in .env that holds your API key
# base_url = the provider's OpenAI-compatible web address
# models   = tried in order; if one isn't available we try the next
PROVIDERS = [
    {
        "name": "Groq",
        "key": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
    },
    {
        "name": "Mistral",
        "key": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "models": ["mistral-small-latest", "mistral-medium-latest"],
    },
    {
        "name": "NVIDIA",
        "key": "NVIDIA_API_KEY",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "models": ["nvidia/nemotron-3-super-120b-a12b", "openai/gpt-oss-20b"],
    },
    {
        "name": "Cerebras",
        "key": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "models": ["gpt-oss-120b", "qwen-3.8-27b"],
    },
    {
        "name": "OpenRouter",
        "key": "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openai/gpt-oss-120b:free", "meta-llama/llama-3.3-70b-instruct:free"],
    },
    {
        "name": "Cohere",
        "key": "COHERE_API_KEY",
        "base_url": "https://api.cohere.ai/compatibility/v1",
        "models": ["command-a-plus-05-2026", "command-a-03-2025"],
    },
    {
        "name": "Cloudflare",
        "key": "CLOUDFLARE_API_TOKEN",
        # Cloudflare also needs your account ID, which goes inside the address.
        "base_url": "https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1",
        "models": ["@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct"],
    },
    {
        "name": "Hugging Face",
        "key": "HF_TOKEN",
        "base_url": "https://router.huggingface.co/v1",
        "models": ["openai/gpt-oss-120b", "meta-llama/Llama-3.3-70B-Instruct"],
    },
    {
        "name": "Gemini",
        "key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "models": ["gemini-3.5-flash-lite", "gemini-3.8-flash"],
    },
    {
        # Optional: a model running on your own laptop with Ollama. No key and
        # no limits, but slower. Only used if OLLAMA_MODEL is set in .env.
        "name": "Ollama (your laptop)",
        "key": None,
        "base_url": "http://localhost:11434/v1",
        "models_from_env": "OLLAMA_MODEL",
    },
]

# How long to leave a provider alone after certain problems (in seconds),
# so we don't waste time asking it again on the very next question.
REST_AFTER_RATE_LIMIT = 300    # out of free requests for now: 5 minutes
REST_AFTER_SERVER_ERROR = 30   # busy or broken: 30 seconds
REST_AFTER_BAD_KEY = 3600      # key rejected: 1 hour (fix it in .env)

REQUEST_TIMEOUT = 45           # give up on a single request after 45 seconds

_resting_until = {}  # provider name -> time when we may try it again
_clients = {}        # provider name -> its OpenAI-compatible client


class NoProviderAvailable(Exception):
    """Raised when every provider failed or none is set up."""


def _base_url(provider):
    # Fill in things like {CLOUDFLARE_ACCOUNT_ID} from .env. None if missing.
    try:
        return provider["base_url"].format(**os.environ)
    except KeyError:
        return None


def _models(provider):
    if "models_from_env" in provider:
        model = os.getenv(provider["models_from_env"], "").strip()
        return [model] if model else []
    return provider["models"]


def usable_providers():
    """Providers that have a key (and anything else they need) in .env."""
    usable = []
    for provider in PROVIDERS:
        has_key = provider["key"] is None or os.getenv(provider["key"], "").strip()
        if has_key and _base_url(provider) and _models(provider):
            usable.append(provider)
    return usable


def _client(provider):
    name = provider["name"]
    if name not in _clients:
        _clients[name] = OpenAI(
            api_key=os.getenv(provider["key"], "").strip() if provider["key"] else "ollama",
            base_url=_base_url(provider),
            timeout=REQUEST_TIMEOUT,
            max_retries=0,  # no hidden retries: we move to the next provider instead
        )
    return _clients[name]


def _rest(provider, seconds):
    _resting_until[provider["name"]] = time.time() + seconds


def _is_resting(provider):
    return time.time() < _resting_until.get(provider["name"], 0)


def _log(provider, model, message):
    print(f"  [{provider['name']} · {model}] {message}")


def ask_llm(system_prompt, user_prompt):
    """
    Ask each provider in turn until one answers.
    Returns (answer_text, "Provider · model") so we can show who answered.
    """
    providers = usable_providers()
    if not providers:
        raise NoProviderAvailable("No AI provider is set up. Add at least one API key to your .env file.")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    problems = []

    for provider in providers:
        if _is_resting(provider):
            continue

        for model in _models(provider):
            try:
                response = _client(provider).chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.3,
                )
                if not getattr(response, "choices", None):
                    _log(provider, model, "sent back something that isn't an answer, moving on")
                    problems.append(f"{provider['name']}: unexpected response")
                    break
                text = (response.choices[0].message.content or "").strip()
                if not text:
                    _log(provider, model, "gave an empty answer, trying the next one")
                    problems.append(f"{provider['name']}: empty answer")
                    continue
                return text, f"{provider['name']} · {model}"

            except (AuthenticationError, PermissionDeniedError):
                _log(provider, model, "key was rejected; check it in .env")
                problems.append(f"{provider['name']}: key rejected")
                _rest(provider, REST_AFTER_BAD_KEY)
                break  # every model here would fail the same way

            except (NotFoundError, BadRequestError, UnprocessableEntityError) as error:
                _log(provider, model, f"model not available ({error.status_code}), trying the next model")
                problems.append(f"{provider['name']} {model}: not available")
                continue

            except RateLimitError:
                _log(provider, model, "out of free requests for now (429), moving on")
                problems.append(f"{provider['name']}: rate limited")
                _rest(provider, REST_AFTER_RATE_LIMIT)
                break

            except APIStatusError as error:
                if error.status_code == 410:
                    _log(provider, model, "this model has been retired (410), trying the next model")
                    problems.append(f"{provider['name']} {model}: retired")
                    continue
                _log(provider, model, f"server error ({error.status_code}), trying the next one")
                problems.append(f"{provider['name']}: error {error.status_code}")
                continue

            except APIConnectionError:
                _log(provider, model, "couldn't connect or timed out, moving on")
                problems.append(f"{provider['name']}: no connection")
                _rest(provider, REST_AFTER_SERVER_ERROR)
                break

            except Exception as error:
                # Anything else unexpected: note it and try the next provider.
                _log(provider, model, f"unexpected problem ({type(error).__name__}), moving on")
                problems.append(f"{provider['name']}: {type(error).__name__}")
                _rest(provider, REST_AFTER_SERVER_ERROR)
                break

        else:
            # Every model of this provider failed with server errors.
            if not _is_resting(provider):
                _rest(provider, REST_AFTER_SERVER_ERROR)

    if not problems:
        raise NoProviderAvailable("All providers are resting after recent errors. Try again in a minute.")
    raise NoProviderAvailable("Every provider failed: " + "; ".join(problems))

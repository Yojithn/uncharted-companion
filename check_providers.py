"""
Checks every AI provider listed in llm.py:
  1. Is its key in .env?
  2. Does the key work?
  3. Do the model names in llm.py still exist? (free models change often)
  4. Does a tiny test question actually get an answer?

Run it after adding or changing keys:   python check_providers.py
"""

import re
import time
from openai import (
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    RateLimitError,
    APIStatusError,
    APIConnectionError,
)
from llm import PROVIDERS, usable_providers, _client, _models

TEST_MESSAGES = [{"role": "user", "content": "Reply with exactly one word: ready"}]


def words(model_id):
    return set(re.split(r"[/\-_:.@]", model_id.lower())) - {""}


def similar_models(missing, available, limit=6):
    # Rank the provider's real models by how many name-parts they share.
    wanted = set().union(*(words(m) for m in missing))
    ranked = sorted(available, key=lambda m: len(wanted & words(m)), reverse=True)
    return ranked[:limit]


def list_models(client):
    try:
        return sorted(m.id.removeprefix("models/") for m in client.models.list())
    except Exception:
        return None  # some providers don't support listing models


def check(provider):
    client = _client(provider)
    working, missing = [], []

    for model in _models(provider):
        start = time.time()
        try:
            response = client.chat.completions.create(model=model, messages=TEST_MESSAGES)
            if not getattr(response, "choices", None):
                print(f"     FAIL  {model}  sent back something that isn't an answer: {str(response)[:80]!r}")
                continue
            reply = (response.choices[0].message.content or "").strip()
            seconds = time.time() - start
            if reply:
                print(f"     OK    {model}  (answered in {seconds:.1f}s: \"{reply[:30]}\")")
                working.append(model)
            else:
                print(f"     ??    {model}  (connected, but the answer was empty)")
        except (AuthenticationError, PermissionDeniedError):
            print("     FAIL  key rejected. Copy the key again into .env (no quotes, no spaces).")
            return
        except (NotFoundError, BadRequestError, UnprocessableEntityError) as error:
            print(f"     FAIL  {model}  not available here ({error.status_code})")
            missing.append(model)
        except RateLimitError as error:
            print(f"     WAIT  {model}  rate limited right now (the key works, just try later)")
            print(f"           provider said: {str(error.message)[:120]}")
            working.append(model)
        except APIStatusError as error:
            if error.status_code == 410:
                print(f"     FAIL  {model}  retired by the provider (410)")
                missing.append(model)
            else:
                print(f"     FAIL  {model}  server error {error.status_code}")
        except APIConnectionError:
            print("     FAIL  couldn't connect (check your internet, or that Ollama is running)")
            return
        except Exception as error:
            print(f"     FAIL  {model}  unexpected problem: {type(error).__name__}: {str(error)[:80]}")

    if missing:
        available = list_models(client)
        if available:
            print("     Models this provider does offer that look similar:")
            for model in similar_models(missing, available):
                print(f"       - {model}")
            print("     Put one of these in the provider's \"models\" list in llm.py.")


if __name__ == "__main__":
    usable = usable_providers()
    print(f"\nChecking {len(usable)} provider(s) with keys set up...\n")

    for position, provider in enumerate(PROVIDERS, start=1):
        label = f"{position:>2}. {provider['name']}"
        if provider not in usable:
            needs = provider["key"] or "OLLAMA_MODEL"
            if "{CLOUDFLARE_ACCOUNT_ID}" in provider["base_url"]:
                needs += " and CLOUDFLARE_ACCOUNT_ID"
            print(f"{label:<26} not set up (add {needs} to .env)")
            continue
        print(f"{label}")
        check(provider)
        print()

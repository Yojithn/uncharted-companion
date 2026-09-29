# The retrieval half we already built and tested.
from search_test import search

# The generation half: tries every AI provider you've set up, in order.
from llm import ask_llm

# Standing instructions for the AI. It sees these before every question.
SYSTEM_PROMPT = """You are a friendly game companion for Uncharted 4: A Thief's End.
You help the player with the story, characters, puzzles, treasures and missions.

Rules:
- Answer ONLY using the game notes you are given. Do not use outside knowledge.
- If the notes don't contain the answer, say you don't have that information yet. Never guess.
- For puzzles and missions, give clear step-by-step instructions.
- Mention the chapter when the notes show which chapter something is in.
- Keep answers short and easy to follow."""


def build_prompt(question, hits):
    # Turn the retrieved chunks into one block of "game notes" for the AI.
    notes = "\n\n".join(f"[Source: {hit['source']}]\n{hit['text']}" for hit in hits)
    return f"Game notes:\n{notes}\n\nPlayer's question: {question}"


def answer(question):
    hits = search(question, n_results=4)                   # 1. Retrieve
    prompt = build_prompt(question, hits)                  # 2. Augment
    reply, answered_by = ask_llm(SYSTEM_PROMPT, prompt)    # 3. Generate
    sources = sorted({hit["source"] for hit in hits})
    return reply, sources, answered_by


if __name__ == "__main__":
    print("\nUncharted 4 companion ready. Ask a question, or type 'quit' to exit.")

    while True:
        question = input("\nYou: ").strip()

        if question.lower() in ("quit", "exit"):
            break
        if question == "":
            continue

        try:
            reply, sources, answered_by = answer(question)
        except Exception as error:
            print(f"\nSomething went wrong: {error}")
            continue

        print(f"\nCompanion: {reply}")
        print(f"(from: {', '.join(sources)} | answered by {answered_by})")

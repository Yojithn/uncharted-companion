from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb

# Take the settings straight from ingest.py, so the search ALWAYS uses the
# exact same model and database that built the collection.
from ingest import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL

# A second model that reads the question and a chunk TOGETHER and judges
# how well that chunk answers the question. Slower, but much more accurate.
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"

# How many chunks the fast first search hands over to the re-ranker.
CANDIDATES = 20

# Load the database and both models ONCE, when this file is first loaded.
# Loading a model takes a few seconds, so we don't want to redo it for
# every single question (that matters once we're chatting in a loop).
print("Loading search models...")
collection = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION_NAME)
embedder = SentenceTransformer(EMBED_MODEL)
reranker = CrossEncoder(RERANK_MODEL)


def search(query, n_results=3):
    # --- Step 1: fast search. Cast a wide net and grab 20 likely chunks. ---
    query_embedding = embedder.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=CANDIDATES
    )
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    # --- Step 2: careful re-ranking. Score each (question, chunk) pair. ---
    pairs = [(query, doc) for doc in documents]
    scores = reranker.predict(pairs)

    candidates = []
    for position, (doc, meta, score) in enumerate(zip(documents, metadatas, scores), start=1):
        candidates.append({
            "text": doc,
            "source": meta["source"],
            "score": float(score),
            "first_pass_rank": position
        })

    # Highest re-ranker score first, then keep only the best few.
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:n_results]


if __name__ == "__main__":
    query = input("Ask something about Uncharted 4: ")

    for hit in search(query):
        print(f"--- from {hit['source']}  (relevance: {hit['score']:.2f}, "
              f"was #{hit['first_pass_rank']} before re-ranking) ---")
        print(hit["text"])
        print()

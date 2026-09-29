"""
Quick verification of the ingested ChromaDB data for the Uncharted 4 RAG companion.
Run this from the project root with the venv active:

    venv\Scripts\activate
    python verify.py
"""

from sentence_transformers import SentenceTransformer
import chromadb

CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "uncharted4"

TEST_QUERIES = [
    "Who is Sam Drake?",
    "What happened at the pirate colony of Libertalia?",
    "Tell me about Nathan and Elena's relationship.",
]


def main():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME)

    print(f"Collection '{COLLECTION_NAME}' contains {collection.count()} chunks.\n")

    # 1. Peek at a few raw stored chunks (sanity check on ingestion, no embedding needed)
    print("=== Sample of 3 stored chunks ===")
    sample = collection.peek(limit=3)
    for doc, meta in zip(sample["documents"], sample["metadatas"]):
        print(f"--- from {meta['source']} ---")
        print(doc[:200] + ("..." if len(doc) > 200 else ""))
        print()

    # 2. Run a few real semantic search queries to confirm retrieval quality
    print("=== Semantic search test ===")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    for query in TEST_QUERIES:
        print(f"\nQuery: {query}")
        query_embedding = model.encode([query]).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=2)

        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            print(f"  [{meta['source']}] (distance={dist:.3f})")
            print(f"    {doc[:150].strip()}...")


if __name__ == "__main__":
    main()

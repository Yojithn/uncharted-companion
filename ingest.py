import os
from collections import Counter
from sentence_transformers import SentenceTransformer
import chromadb

DATA_DIR = "data"
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "uncharted4"

# A model trained on real question -> answer pairs, so it's built to match
# a short question ("who is Nathan's mentor?") to the passage that ANSWERS it.
# Same size, speed and vector length (384) as the model we used before.
EMBED_MODEL = "multi-qa-MiniLM-L6-cos-v1"


def load_and_chunk():
    all_chunks = []

    for filename in os.listdir(DATA_DIR):
        if not filename.endswith(".txt"):
            continue

        filepath = os.path.join(DATA_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        raw_pieces = content.split("\n\n")

        for piece in raw_pieces:
            chunk_text = piece.strip()
            if chunk_text == "":
                continue

            all_chunks.append({
                "text": chunk_text,
                "source": filename
            })

    return all_chunks


def embed_chunks(chunks):
    print(f"Loading embedding model {EMBED_MODEL} (first run downloads it)...")
    model = SentenceTransformer(EMBED_MODEL)

    texts = [chunk["text"] for chunk in chunks]

    print(f"Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts)

    return embeddings


def store_chunks(chunks, embeddings):
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Remove the old collection so re-running doesn't create duplicates.
    # On the very first run there's nothing to delete, which raises an
    # error — so we catch that and carry on.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    # "cosine" tells Chroma to compare vectors by the angle between them,
    # which is how this embedding model is designed to be compared.
    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    documents = [chunk["text"] for chunk in chunks]
    metadatas = [{"source": chunk["source"]} for chunk in chunks]
    ids = [str(i) for i in range(len(chunks))]

    collection.add(
        documents=documents,
        embeddings=embeddings.tolist(),
        metadatas=metadatas,
        ids=ids
    )

    return collection


if __name__ == "__main__":
    chunks = load_and_chunk()
    print(f"Total chunks: {len(chunks)}")
    print()

    print("Chunks per source file:")
    counts = Counter(chunk["source"] for chunk in chunks)
    for filename, count in sorted(counts.items()):
        print(f"  {filename}: {count}")
    print()

    embeddings = embed_chunks(chunks)
    print()

    collection = store_chunks(chunks, embeddings)
    print(f"Stored {collection.count()} chunks in ChromaDB at ./{CHROMA_DIR}")

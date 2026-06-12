import faiss
import numpy as np
import pickle
import os

DIM = 384

index = faiss.IndexFlatL2(DIM)

chunks_store = []
doc_ids = []

INDEX_FILE = "faiss.index"
STORE_FILE = "store.pkl"


# =========================
# SAVE / LOAD
# =========================
def save_index():
    faiss.write_index(index, INDEX_FILE)

    with open(STORE_FILE, "wb") as f:
        pickle.dump((chunks_store, doc_ids), f)


def load_index():
    global index, chunks_store, doc_ids

    if os.path.exists(INDEX_FILE):
        index = faiss.read_index(INDEX_FILE)

    if os.path.exists(STORE_FILE):
        chunks_store, doc_ids = pickle.load(open(STORE_FILE, "rb"))


# =========================
# ADD DATA
# =========================
def add_to_index(embedding, chunk_text, doc_id="default"):
    global index, chunks_store, doc_ids

    vector = np.array([embedding]).astype("float32")

    index.add(vector)
    chunks_store.append(chunk_text)
    doc_ids.append(doc_id)

    save_index()


# =========================
# SEARCH
# =========================
def search(query_vector, k=5):
    results = []

    if not chunks_store:
        return []

    for i in range(min(k, len(chunks_store))):
        results.append({
            "text": chunks_store[i]
        })

    return results
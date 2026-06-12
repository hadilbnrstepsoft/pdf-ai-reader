from rag.embeddings import embed
from rag.vector_store import load_index, search

load_index()

query = "invoice total price"

vec = embed([query])[0]

results = search(vec)

for r in results:
    print("-", r)
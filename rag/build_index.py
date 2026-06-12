from rag.embeddings import embed
from rag.vector_store import add_to_index

def chunk_text(text, size=500):
    return [text[i:i+size] for i in range(0, len(text), size)]


def build_index_from_text(text, doc_id):
    chunks = chunk_text(text)

    for chunk in chunks:
        vector = embed(chunk)
        add_to_index(vector, chunk, doc_id)

    print(f"INDEX BUILT for {doc_id}")
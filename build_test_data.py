from rag.embeddings import embed
from rag.vector_store import add_vectors

text = """
Invoice 1: Apple MacBook 1200 euros
Invoice 2: Dell Laptop 900 euros
Invoice 3: HP Monitor 300 euros
"""

chunks = text.split("\n")

vectors = embed(chunks)

add_vectors(vectors, chunks)

print("INDEX BUILT")
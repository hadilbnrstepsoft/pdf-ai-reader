from rag.pdf_loader import extract_pdf_text
from rag.chunking import chunk_text
from rag.embeddings import embed
from rag.vector_store import add_vectors, load_index

load_index()

# TEST PDF
file_path = "temp.pdf"

with open(file_path, "rb") as f:
    pages = extract_pdf_text(f)

chunks = chunk_text(pages)

vectors = embed(chunks)

add_vectors(vectors, chunks)

print("PDF INDEXED SUCCESSFULLY")
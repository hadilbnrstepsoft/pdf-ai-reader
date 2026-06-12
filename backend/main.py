from fastapi import FastAPI, UploadFile, File, Depends
from backend.auth import get_current_user
from backend.pdf_service import extract_pdf_text, generate_json
from backend.db import save_document, get_documents
from backend.rag import answer_question

app = FastAPI()

# =========================
# UPLOAD PDF
# =========================
@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    content = await file.read()

    text = extract_pdf_text(content)
    json_data = generate_json(text)

    doc_id = save_document(user["id"], file.filename, text, json_data)

    return {
        "doc_id": doc_id,
        "json": json_data
    }

# =========================
# LIST DOCUMENTS
# =========================
@app.get("/documents")
def list_docs(user=Depends(get_current_user)):
    return get_documents(user["id"])

# =========================
# CHAT (RAG)
# =========================
@app.post("/chat")
def chat(question: str, doc_id: int, user=Depends(get_current_user)):
    return answer_question(user["id"], doc_id, question)
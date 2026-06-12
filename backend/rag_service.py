from db import get_connection
import requests

def answer_question(user_id, doc_id, question):

    # =========================
    # DB CONNECTION FIX
    # =========================
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT text, json_data FROM documents WHERE id=?",
        (doc_id,)
    )

    doc = cur.fetchone()
    conn.close()

    # =========================
    # SAFE EXTRACTION
    # =========================
    context = doc[0] if doc else ""
    json_data = doc[1] if doc else ""

    # =========================
    # PROMPT
    # =========================
    prompt = f"""
You are a PDF assistant.

DOCUMENT:
{context}

STRUCTURED DATA:
{json_data}

QUESTION:
{question}

Answer clearly and precisely.
"""

    # =========================
    # OLLAMA CALL
    # =========================
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    return {"answer": res.json()["response"]}
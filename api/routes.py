from fastapi import APIRouter
import requests

router = APIRouter()

# 👉 SIMPLE CHAT (no RAG crash safe)
@router.post("/chat")
async def chat(payload: dict):

    question = payload.get("question")

    if not question:
        return {"error": "No question provided"}

    prompt = f"""
You are a PDF assistant.

User question:
{question}

Answer clearly and concisely.
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    try:
        return {
            "answer": response.json()["response"]
        }
    except:
        return {
            "answer": "LLM error"
        }
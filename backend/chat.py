import sys
import os
import requests

# ADD PROJECT ROOT
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from rag.embeddings import embed
from rag.vector_store import search


# =========================
# OLLAMA
# =========================
def ask_ollama(prompt):
    try:
        r = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        return r.json().get("response", "")

    except Exception as e:
        return f"Error: {e}"


# =========================
# CHAT WITH PDF
# =========================
def chat_with_pdf(question, pdf_text="", json_data=None):

    try:
        query_vector = embed(question)
        results = search(query_vector, k=5)
    except:
        results = []

    context = ""

    for r in results:
        context += f"\n[DOC]\n{r.get('text','')}\n"

    # DEBUG
    print("\n======================")
    print("QUESTION:", question)
    print("PDF LENGTH:", len(pdf_text))
    print("JSON DATA:", str(json_data)[:500])
    print("======================\n")

    prompt = f"""
You are a PDF assistant.

STRICT RULES:
- Use ONLY information from the PDF.
- Never invent data.

PDF CONTENT:
{pdf_text[:3000]}

QUESTION:
{question}

ANSWER:
"""
    answer = ask_ollama(prompt)

    print("\nANSWER:")
    print(answer)
    print("\n")

    return answer
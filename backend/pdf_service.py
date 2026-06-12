import fitz
import requests
import json
import re

def extract_pdf_text(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def generate_json(text):
    prompt = f"""
Return ONLY valid JSON:

{{
  "company_name": "",
  "document_type": "",
  "date": "",
  "summary": "",
  "invoice_total": "",
  "articles": []
}}

TEXT:
{text}
"""

    res = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "llama3", "prompt": prompt, "stream": False}
    )

    raw = res.json()["response"]

    try:
        return json.loads(raw)
    except:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(match.group()) if match else {}
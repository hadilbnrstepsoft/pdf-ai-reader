import streamlit as st
import fitz
import requests
import pandas as pd
import json
import re

from db import init_db, get_connection
from auth import login_user, register_user
from chat import chat_with_pdf

# =========================
# INIT
# =========================
init_db()

st.set_page_config(page_title="PDF AI SaaS", layout="wide")

# =========================
# SESSION STATE
# =========================
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""

if "json_data" not in st.session_state:
    st.session_state.json_data = None

if "chat" not in st.session_state:
    st.session_state.chat = []


# =========================
# DB
# =========================
def get_documents(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, filename, json_data
        FROM pdf_history
        WHERE user_id=?
        ORDER BY id DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# =========================
# PDF EXTRACTION
# =========================
def extract_text(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "\n".join(
        b[4].strip()
        for page in doc
        for b in page.get_text("blocks")
        if b[4].strip()
    )


# =========================
# CURRENCY PARSER (IMPORTANT FIX)
# =========================
def extract_currencies(text):
    pattern = re.compile(r"(\d+)\s+([A-Z]{3})\s+(.+?)\s+([0-9,]+)\s+([0-9,]+)")

    result = []
    for line in text.splitlines():
        m = pattern.search(line)
        if m:
            result.append({
                "WNR": m.group(1),
                "ISO": m.group(2),
                "Name": m.group(3).strip(),
                "Ankauf": m.group(4),
                "Verkauf": m.group(5)
            })
    return result


# =========================
# SAFE PARSER (CRITICAL FIX)
# =========================
def parse_json(text):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

    return {
        "document_type": "",
        "invoice": {
            "company_name": "",
            "date": "",
            "total": "",
            "articles": []
        },
        "currencies": []
    }


# =========================
# OLLAMA
# =========================
def ask_ollama(prompt):
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


# =========================
# UI
# =========================
st.title("📄 PDF Reader AI")


# =========================
# AUTH
# =========================
if not st.session_state.user_id:

    st.subheader("Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user_id = login_user(u, p)
        if user_id:
            st.session_state.user_id = user_id
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()


# =========================
# UPLOAD
# =========================
file = st.file_uploader("Upload PDF", type="pdf")

if file:

    text = extract_text(file)
    st.session_state.pdf_text = text

    st.text_area("PDF TEXT", text[:5000], height=300)

    # -------------------------
    # CURR TABLE DISPLAY
    # -------------------------
    currencies = extract_currencies(text)

    if currencies:
        st.subheader("💱 Currency Table")
        st.dataframe(pd.DataFrame(currencies))


    # =========================
    # EXTRACT JSON
    # =========================
    if st.button("Extract structured data"):

        prompt = f"""
You are a document AI.

Detect:
- invoice OR currency_table

Return ONLY JSON:

{{
  "document_type": "invoice | currency_table",
  "invoice": {{
    "company_name": "",
    "date": "",
    "total": "",
    "articles": []
  }},
  "currencies": []
}}

TEXT:
{text}
"""

        result = ask_ollama(prompt)

        st.subheader("RAW OUTPUT")
        st.code(result)

        data = parse_json(result)
        st.session_state.json_data = data


# =========================
# SMART DISPLAY ENGINE (FIX IMPORTANT)
# =========================
if st.session_state.json_data:

    data = st.session_state.json_data
    doc_type = data.get("document_type")


    # =========================
    # INVOICE MODE
    # =========================
    if doc_type == "invoice":

        st.subheader("🧾 Invoice")

        inv = data.get("invoice", {})

        st.write("Company:", inv.get("company_name"))
        st.write("Date:", inv.get("date"))
        st.write("Total:", inv.get("total"))

        articles = inv.get("articles", [])

        if articles:
            st.subheader("Articles")
            st.dataframe(pd.DataFrame(articles))


    # =========================
    # CURRENCY MODE
    # =========================
    elif doc_type == "currency_table":

        st.subheader("💱 Currency Rates")

        df = pd.DataFrame(data.get("currencies", []))

        st.dataframe(df)


# =========================
# HISTORY
# =========================
if st.session_state.user_id:

    st.divider()
    st.subheader("History")

    for _, filename, data in get_documents(st.session_state.user_id):
        st.write(filename)
        st.code(str(data)[:200])


# =========================
# CHAT (PDF RAG)
# =========================
st.divider()
st.subheader("Chat with PDF")

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.write(m["content"])

q = st.chat_input("Ask question...")

if q:

    st.session_state.chat.append({"role": "user", "content": q})

    answer = chat_with_pdf(
        question=q,
        pdf_text=st.session_state.pdf_text,
        json_data=json.dumps(st.session_state.json_data or {})
    )

    st.session_state.chat.append({"role": "assistant", "content": answer})

    st.rerun()
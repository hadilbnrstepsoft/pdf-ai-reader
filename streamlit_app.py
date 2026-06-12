import streamlit as st
import fitz
import pandas as pd
import json
import re
import sqlite3

# =========================
# DATABASE SETUP
# =========================
DB_PATH = "saas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS pdf_history (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, filename TEXT, json_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

def get_connection():
    return sqlite3.connect(DB_PATH)

def register_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def login_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_documents(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, filename, json_data FROM pdf_history WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def save_pdf(user_id, filename, data):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO pdf_history (user_id, filename, json_data) VALUES (?, ?, ?)",
              (user_id, filename, json.dumps(data, ensure_ascii=False)))
    conn.commit()
    conn.close()

init_db()

# =========================
# SESSION STATE
# =========================
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "json_data" not in st.session_state:
    st.session_state.json_data = None
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""
if "chat" not in st.session_state:
    st.session_state.chat = []

# =========================
# FONCTIONS D'EXTRACTION
# =========================
def extract_text(file):
    if file is None:
        return ""
    doc = fitz.open(stream=file.read(), filetype="pdf")
    full_text = []
    for page in doc:
        full_text.append(page.get_text())
    return "\n".join(full_text)

def extract_currencies(text):
    pattern = re.compile(r"(\d+)\s+([A-Z]{3})\s+(.+?)\s+([0-9,]+)\s+([0-9,]+)")
    currencies = []
    for line in text.splitlines():
        m = pattern.search(line)
        if m:
            currencies.append({
                "WNR": m.group(1),
                "ISO": m.group(2),
                "Waehrung": m.group(3).strip(),
                "Ankauf": m.group(4),
                "Verkauf": m.group(5)
            })
    return currencies

def extract_articles_regex(text):
    """
    Extrait les articles à partir du tableau du PDF.
    Exemple de ligne : "1  MA0R00004  10.000,0 kg  1,29  12.900,00  LDPE 150 E natur"
    """
    articles = []
    pattern = re.compile(r'^\d+\s+(\S+)\s+([\d\.,]+\s*kg)\s+([\d\.,]+)\s+([\d\.,]+)\s+(.+)$', re.IGNORECASE)
    for line in text.splitlines():
        line = line.strip()
        m = pattern.match(line)
        if m:
            articles.append({
                "article_number": m.group(1),
                "description": m.group(5).strip(),
                "quantity": m.group(2).replace('kg', '').strip(),
                "price": m.group(3).replace(',', '.'),
                "total": m.group(4).replace(',', '.')
            })
    return articles

def chat_simple(question, pdf_text):
    """Recherche par mots-clés dans le texte du PDF."""
    if not pdf_text:
        return "Aucun document chargé."
    question_lower = question.lower()
    text_lower = pdf_text.lower()
    if question_lower in text_lower:
        # Affiche un extrait
        idx = text_lower.find(question_lower)
        start = max(0, idx - 150)
        end = min(len(pdf_text), idx + 250)
        snippet = pdf_text[start:end]
        return f"✅ Trouvé :\n\n...{snippet}..."
    else:
        return "❌ Information non trouvée dans le document."

# =========================
# UI STYLE
# =========================
st.set_page_config(page_title="PDF AI SaaS", layout="wide")
st.markdown("""
<style>
.stApp { background: linear-gradient(rgba(5,10,25,0.88), rgba(5,10,25,0.92)), url("https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=2070&auto=format&fit=crop"); background-size: cover; background-position: center; background-attachment: fixed; color: white; }
h1,h2,h3,h4,h5,p,label,span { color: white !important; }
.block-container { padding-top: 2rem; }
textarea, input { background: rgba(255,255,255,0.95) !important; color: black !important; border-radius: 14px !important; }
[data-testid="stDataFrame"] { background: rgba(255,255,255,0.95); border-radius: 15px; overflow: hidden; }
[data-testid="stDataFrame"] * { color: black !important; }
.pdf-card { background: rgba(255,255,255,0.08); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.12); border-radius: 24px; padding: 28px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.35); transition: 0.3s; }
.info-row { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }
.info-label { font-size: 16px; font-weight: 600; color: #94a3b8 !important; }
.info-value { font-size: 18px; font-weight: 700; text-align: right; }
.total-box { margin-top: 20px; background: linear-gradient(90deg,#2563eb,#06b6d4); border-radius: 18px; padding: 18px; text-align: center; font-size: 28px; font-weight: bold; box-shadow: 0 6px 20px rgba(37,99,235,0.4); }
.stButton button { background: linear-gradient(90deg,#2563eb,#0ea5e9); color: white; border: none; border-radius: 14px; padding: 12px 22px; font-weight: bold; transition: 0.3s; }
.stButton button:hover { transform: scale(1.03); }
section[data-testid="stSidebar"] { background: rgba(15,23,42,0.88); backdrop-filter: blur(10px); }
.card { background: rgba(255,255,255,0.05); border-radius: 16px; padding: 12px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.title("📄 PDF AI SaaS - Test Client")

# =========================
# AUTHENTIFICATION
# =========================
if st.session_state.user_id is None:
    st.subheader("🔐 Login / Register")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login"):
            uid = login_user(u, p)
            if uid:
                st.session_state.user_id = uid
                st.success("Logged in successfully")
                st.rerun()
            else:
                st.error("Invalid credentials")
    with tab2:
        u2 = st.text_input("New username")
        p2 = st.text_input("New password", type="password")
        if st.button("Register"):
            if register_user(u2, p2):
                st.success("Account created")
            else:
                st.error("User already exists")
    st.stop()

st.sidebar.success(f"Connecté (ID {st.session_state.user_id})")
if st.sidebar.button("Déconnexion"):
    st.session_state.user_id = None
    st.session_state.json_data = None
    st.session_state.pdf_text = ""
    st.session_state.chat = []
    st.rerun()

# =========================
# UPLOAD PDF ET EXTRACTION
# =========================
file = st.file_uploader("📤 Upload PDF", type=["pdf"])

if file:
    # Réinitialiser le pointeur pour lire le fichier
    file.seek(0)
    text = extract_text(file)
    st.session_state.pdf_text = text
    st.success(f"✅ Texte extrait : {len(text)} caractères")

    # Devises
    currencies = extract_currencies(text)
    if currencies:
        st.subheader("💱 Wechselkurse")
        st.dataframe(pd.DataFrame(currencies), use_container_width=True)

    # Extraction des articles
    articles = extract_articles_regex(text)
    if articles:
        st.subheader("📦 Articles détectés")
        df_articles = pd.DataFrame(articles)
        st.dataframe(df_articles, use_container_width=True)

        # Sauvegarde en base
        data = {
            "company_name": "",
            "document_type": "",
            "date": "",
            "summary": "",
            "invoice_total": "",
            "articles": articles
        }
        st.session_state.json_data = data
        save_pdf(st.session_state.user_id, file.name, data)
        st.success("💾 Données sauvegardées en base")
    else:
        st.warning("⚠️ Aucun article trouvé. Vérifiez le format du PDF (lignes commençant par un numéro, avec 'kg', prix, etc.).")

    # Aperçu du texte pour débogage (optionnel)
    with st.expander("🔍 Aperçu du texte brut (premières lignes)"):
        st.code("\n".join(text.splitlines()[:40]))

# =========================
# DONNÉES SAUVEGARDÉES
# =========================
if st.session_state.json_data:
    st.subheader("📦 Données extraites (dernier PDF)")
    if st.session_state.json_data.get("articles"):
        st.dataframe(pd.DataFrame(st.session_state.json_data["articles"]), use_container_width=True)

# =========================
# HISTORIQUE
# =========================
st.divider()
st.subheader("📚 Historique des PDF traités")
for doc_id, filename, data in get_documents(st.session_state.user_id):
    with st.expander(f"📄 {filename}"):
        st.json(data)

# =========================
# CHAT (recherche textuelle)
# =========================
st.divider()
st.subheader("💬 Assistant (recherche simple)")
for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if q := st.chat_input("Posez une question sur le document actuel"):
    st.session_state.chat.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        answer = chat_simple(q, st.session_state.pdf_text)
        st.write(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer})
    st.rerun()
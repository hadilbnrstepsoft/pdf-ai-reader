import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import json
import re
import sqlite3

# =========================
# DATABASE SETUP (tout dans le fichier)
# =========================
DB_PATH = "saas.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS pdf_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            json_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
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
              (user_id, filename, json.dumps(data)))
    conn.commit()
    conn.close()

init_db()

# =========================
# SESSION STATE INIT
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
# HF INFERENCE CLIENT
# =========================
@st.cache_resource
def get_hf_client():
    token = st.secrets.get("HF_TOKEN", "")
    if not token:
        st.warning("⚠️ HF_TOKEN not set. JSON extraction will use mock data.")
        return InferenceClient(token=token, provider="nebius") if token else None

client = get_hf_client()

import requests

def ask_huggingface(prompt, model="mistralai/Mistral-7B-Instruct-v0.3"):
    """
    Appelle l'API Hugging Face via requests (méthode fiable).
    """
    token = st.secrets.get("HF_TOKEN")
    if not token:
        st.error("❌ HF_TOKEN manquant dans les secrets.")
        return "{}"
    
    API_URL = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.2,
            "return_full_text": False
        }
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Le résultat peut être une liste ou un dict selon le modèle
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "{}")
        elif isinstance(result, dict):
            return result.get("generated_text", "{}")
        else:
            st.error(f"Réponse inattendue : {result}")
            return "{}"
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur réseau : {e}")
        return "{}"
    except Exception as e:
        st.error(f"Erreur lors du traitement : {e}")
        return "{}"
# =========================
# PDF EXTRACTION
# =========================
def extract_text(file_bytes):
    if not file_bytes:
        raise ValueError("Fichier vide")
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        blocks = page.get_text("blocks")
        for b in blocks:
            txt = b[4].strip()
            if txt:
                text_parts.append(txt)
    return "\n".join(text_parts)

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

def parse_json(raw):
    try:
        return json.loads(raw)
    except:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {"company_name": "", "document_type": "", "date": "", "summary": "", "invoice_total": "", "articles": []}

def chat_with_pdf(question, pdf_text, json_data):
    prompt = f"""
Tu es un assistant expert en analyse de documents PDF.
Voici le texte extrait du PDF :
{pdf_text[:3000]}

Voici les données structurées :
{json_data}

Question : {question}

Réponds de manière claire et précise.
"""
    return ask_huggingface(prompt, model="mistralai/Mistral-7B-Instruct-v0.3")

# =========================
# UI STYLING
# =========================
st.set_page_config(page_title="PDF AI SaaS", layout="wide")
st.markdown("""
<style>
.stApp {
    background: linear-gradient(rgba(5,10,25,0.88), rgba(5,10,25,0.92)),
                url("https://images.unsplash.com/photo-1516321318423-f06f85e504b3?q=80&w=2070&auto=format&fit=crop");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
    color: white;
}
h1,h2,h3,h4,h5,p,label,span { color: white !important; }
.block-container { padding-top: 2rem; }
textarea, input {
    background: rgba(255,255,255,0.95) !important;
    color: black !important;
    border-radius: 14px !important;
}
[data-testid="stDataFrame"] {
    background: rgba(255,255,255,0.95);
    border-radius: 15px;
    overflow: hidden;
}
[data-testid="stDataFrame"] * { color: black !important; }
.pdf-card {
    background: rgba(255,255,255,0.08);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 24px;
    padding: 28px;
    margin-top: 20px;
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    transition: 0.3s;
}
.pdf-card:hover { transform: translateY(-4px); }
.info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
.info-label {
    font-size: 16px;
    font-weight: 600;
    color: #94a3b8 !important;
}
.info-value { font-size: 18px; font-weight: 700; text-align: right; }
.total-box {
    margin-top: 20px;
    background: linear-gradient(90deg,#2563eb,#06b6d4);
    border-radius: 18px;
    padding: 18px;
    text-align: center;
    font-size: 28px;
    font-weight: bold;
    box-shadow: 0 6px 20px rgba(37,99,235,0.4);
}
.stButton button {
    background: linear-gradient(90deg,#2563eb,#0ea5e9);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 12px 22px;
    font-weight: bold;
    transition: 0.3s;
}
.stButton button:hover { transform: scale(1.03); }
section[data-testid="stSidebar"] {
    background: rgba(15,23,42,0.88);
    backdrop-filter: blur(10px);
}
</style>
""", unsafe_allow_html=True)

st.title("📄 PDF AI SaaS - Test Client")

# =========================
# AUTHENTIFICATION
# =========================
if st.session_state.user_id is None:
    st.subheader("🔐 Connexion / Inscription")
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        u = st.text_input("Nom d'utilisateur")
        p = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            uid = login_user(u, p)
            if uid:
                st.session_state.user_id = uid
                st.success("Connecté !")
                st.rerun()
            else:
                st.error("Identifiants invalides")
    with tab2:
        u2 = st.text_input("Nouveau nom")
        p2 = st.text_input("Nouveau mot de passe", type="password")
        if st.button("S'inscrire"):
            if register_user(u2, p2):
                st.success("Compte créé, vous pouvez vous connecter")
            else:
                st.error("Ce nom existe déjà")
    st.stop()

st.sidebar.success(f"Connecté (ID {st.session_state.user_id})")
if st.sidebar.button("Déconnexion"):
    st.session_state.user_id = None
    st.session_state.json_data = None
    st.session_state.pdf_text = ""
    st.session_state.chat = []
    st.rerun()

# =========================
# UPLOAD PDF AVEC GESTION D'ERREUR
# =========================
file = st.file_uploader("📤 Télécharger un PDF", type=["pdf"])

if file:
    try:
        file_bytes = file.read()
        if len(file_bytes) == 0:
            st.error("Le fichier est vide.")
            st.stop()

        with st.spinner("Extraction du texte..."):
            text = extract_text(file_bytes)
        st.session_state.pdf_text = text
        st.success(f"✅ Texte extrait : {len(text)} caractères")

        currencies = extract_currencies(text)
        if currencies:
            st.subheader("💱 Wechselkurse (devises)")
            st.dataframe(pd.DataFrame(currencies), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🧠 Extraire en JSON (via IA)"):
                with st.spinner("Appel à l'IA..."):
                    extraction_prompt = f"""
Analyse le document suivant et extrait les informations demandées.

Règles :
- Réponds UNIQUEMENT avec un JSON valide (aucun texte avant ou après).
- Si une information n'est pas trouvée, mets une chaîne vide "".
- Pour les articles, cherche des lignes qui contiennent typiquement : un nom de produit, une quantité, un prix unitaire, un total.
- La structure JSON doit être exactement celle-ci :

{{
  "company_name": "nom de l'entreprise émettrice",
  "document_type": "type de document (facture, devis, etc.)",
  "date": "date au format YYYY-MM-DD",
  "summary": "résumé court du document",
  "invoice_total": "montant total TTC",
  "articles": [
    {{
      "article_number": "référence article si présente",
      "description": "description du produit/service",
      "quantity": "quantité (nombre)",
      "price": "prix unitaire",
      "total": "montant total pour cette ligne"
    }}
  ]
}}

Document :
{text[:4000]}
"""
                    raw_json = ask_huggingface(extraction_prompt)
                    st.subheader("Réponse brute de l'IA")
                    st.code(raw_json)
                    data = parse_json(raw_json)
                    st.session_state.json_data = data
                    save_pdf(st.session_state.user_id, file.name, data)
                    st.success("✅ Données sauvegardées en base")
        with col2:
            st.text_area("📄 Aperçu du texte extrait", text[:2000], height=300)

    except Exception as e:
        st.error(f"❌ Erreur : {type(e).__name__}")
        st.error(str(e))
        st.exception(e)
        st.stop()

# =========================
# AFFICHAGE DES DONNÉES EXTRAITES
# =========================
if st.session_state.json_data:
    d = st.session_state.json_data
    st.subheader("📦 Données structurées")
    st.markdown(f"""
    <div class="pdf-card">
        <div class="info-row"><div class="info-label">🏢 Entreprise</div><div class="info-value">{d.get("company_name","")}</div></div>
        <div class="info-row"><div class="info-label">📝 Résumé</div><div class="info-value">{d.get("summary","")}</div></div>
        <div class="info-row"><div class="info-label">📄 Type</div><div class="info-value">{d.get("document_type","")}</div></div>
        <div class="info-row"><div class="info-label">📅 Date</div><div class="info-value">{d.get("date","")}</div></div>
        <div class="total-box">💰 Total : {d.get("invoice_total","")}</div>
    </div>
    """, unsafe_allow_html=True)
    # Affichage des articles (même si la liste est vide)
    articles = d.get("articles", [])
    st.subheader("📦 Articles")
    if articles and len(articles) > 0:
        st.dataframe(pd.DataFrame(articles), use_container_width=True)
    else:
        st.info("Aucun article détecté dans ce document.")

# =========================
# HISTORIQUE
# =========================
st.divider()
st.subheader("📚 Historique des PDF traités")
history = get_documents(st.session_state.user_id)
for doc_id, filename, data in history:
    with st.expander(f"📄 {filename}"):
        st.json(data)

# =========================
# CHAT ASSISTANT
# =========================
st.divider()
st.subheader("💬 Assistant PDF")
for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if q := st.chat_input("Posez une question sur le document actuel"):
    st.session_state.chat.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        with st.spinner("Réflexion..."):
            answer = chat_with_pdf(
                q,
                st.session_state.pdf_text,
                json.dumps(st.session_state.json_data) if st.session_state.json_data else "{}"
            )
            st.write(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer})
    st.rerun()
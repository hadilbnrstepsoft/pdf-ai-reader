import streamlit as st
import fitz
import pandas as pd
import json
import re
import sqlite3

# =========================
# DATABASE SETUP (identique)
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
def extract_text(file_bytes):
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

def extract_articles(text):
    """
    Extrait les articles au format :
    Artikelnummer: MAOR00004
    Bezeichnung: LDPE 150 E natur
    Menge: 10.000,0 kg
    Preis: 1,29
    Gesamtpreis: 12.900,00
    """
    articles = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("Artikelnummer:"):
            article = {"article_number": "", "description": "", "quantity": "", "price": "", "total": ""}
            article["article_number"] = line.replace("Artikelnummer:", "").strip()
            # Parcours des lignes suivantes pour trouver les autres champs
            for j in range(i+1, min(i+10, len(lines))):
                l = lines[j].strip()
                if l.startswith("Bezeichnung:"):
                    article["description"] = l.replace("Bezeichnung:", "").strip()
                elif l.startswith("Menge:"):
                    qty = l.replace("Menge:", "").strip()
                    qty = re.sub(r'\s*kg$', '', qty, flags=re.IGNORECASE)
                    article["quantity"] = qty
                elif l.startswith("Preis:"):
                    price = l.replace("Preis:", "").strip()
                    article["price"] = price.replace(',', '.')
                elif l.startswith("Gesamtpreis:"):
                    total = l.replace("Gesamtpreis:", "").strip()
                    article["total"] = total.replace(',', '.')
                    break
            articles.append(article)
        i += 1
    return articles

# =========================
# UI
# =========================
st.set_page_config(page_title="PDF AI SaaS", layout="wide")
st.markdown("""... (gardez votre style CSS) ...""", unsafe_allow_html=True)
st.title("📄 PDF AI SaaS - Test Client")

# AUTHENTIFICATION (identique)
if st.session_state.user_id is None:
    # ... (votre code d'authentification)
    st.stop()

st.sidebar.success(f"Connecté (ID {st.session_state.user_id})")
if st.sidebar.button("Déconnexion"):
    st.session_state.user_id = None
    st.session_state.json_data = None
    st.session_state.pdf_text = ""
    st.session_state.chat = []
    st.rerun()

# =========================
# UPLOAD PDF
# =========================
file = st.file_uploader("📤 Télécharger un PDF", type=["pdf"])

if file:
    try:
        file_bytes = file.read()
        if len(file_bytes) == 0:
            st.error("Fichier vide.")
            st.stop()

        with st.spinner("Extraction du texte..."):
            text = extract_text(file_bytes)
        st.session_state.pdf_text = text
        st.success(f"✅ Texte extrait : {len(text)} caractères")

        # Devises
        currencies = extract_currencies(text)
        if currencies:
            st.subheader("💱 Wechselkurse (devises)")
            st.dataframe(pd.DataFrame(currencies), use_container_width=True)

        # Articles (nouvelle méthode)
        articles = extract_articles(text)
        if articles:
            st.subheader("📦 Articles détectés")
            st.dataframe(pd.DataFrame(articles), use_container_width=True)
        else:
            st.info("Aucun article trouvé. Vérifiez que le texte contient 'Artikelnummer:'.")

        # Sauvegarde
        if st.button("💾 Sauvegarder les données extraites"):
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
            st.success("✅ Données sauvegardées en base")

        # Aperçu
        with st.expander("📄 Aperçu du texte extrait"):
            st.text_area("Texte", text[:2000], height=300)

    except Exception as e:
        st.error(f"Erreur : {e}")
        st.exception(e)

# Affichage des données sauvegardées, historique, chat (identique)
if st.session_state.json_data:
    d = st.session_state.json_data
    st.subheader("📦 Données sauvegardées")
    if d.get("articles"):
        st.dataframe(pd.DataFrame(d["articles"]), use_container_width=True)
    else:
        st.info("Aucun article sauvegardé.")

st.divider()
st.subheader("📚 Historique")
for doc_id, filename, data in get_documents(st.session_state.user_id):
    with st.expander(f"📄 {filename}"):
        st.json(data)

st.divider()
st.subheader("💬 Assistant")
# ... (votre chat simple)
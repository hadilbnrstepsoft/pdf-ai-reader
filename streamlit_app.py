import streamlit as st
import fitz  # PyMuPDF
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
# EXTRACTION TEXTE PDF
# =========================
def extract_text(file_bytes):
    """Extrait tout le texte d'un PDF."""
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
    """Extrait les devises selon le pattern fourni."""
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

# =========================
# EXTRACTION ARTICLES AVEC REGEX PERSONNALISABLE
# =========================
def extract_articles_with_regex(text, regex_pattern):
    """
    Extrait les articles en utilisant une regex fournie par l'utilisateur.
    La regex doit capturer (description, quantité, prix, total) selon l'ordre.
    Ici on suppose que la regex a 4 groupes : (quantité, description, prix, total)
    """
    pattern = re.compile(regex_pattern, re.IGNORECASE)
    articles = []
    for line in text.splitlines():
        match = pattern.search(line)
        if match:
            groups = match.groups()
            # Selon le nombre de groupes, on assigne intelligemment
            if len(groups) == 4:
                qty, desc, price, total = groups
            elif len(groups) == 3:
                qty, desc, price = groups
                total = ""
            elif len(groups) == 2:
                desc, qty = groups
                price = total = ""
            else:
                continue
            articles.append({
                "article_number": "",
                "description": desc.strip(),
                "quantity": qty.strip(),
                "price": price.strip().replace(',', '.') if price else "",
                "total": total.strip().replace(',', '.') if total else ""
            })
    return articles

# =========================
# UI
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
.pdf-card { background: rgba(255,255,255,0.08); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.12); border-radius: 24px; padding: 28px; margin-top: 20px; margin-bottom: 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.35); }
.info-row { display: flex; justify-content: space-between; padding: 16px 0; border-bottom: 1px solid rgba(255,255,255,0.08); }
.info-label { font-weight: 600; color: #94a3b8 !important; }
.info-value { font-weight: 700; text-align: right; }
.total-box { margin-top: 20px; background: linear-gradient(90deg,#2563eb,#06b6d4); border-radius: 18px; padding: 18px; text-align: center; font-size: 28px; font-weight: bold; }
.stButton button { background: linear-gradient(90deg,#2563eb,#0ea5e9); color: white; border: none; border-radius: 14px; padding: 12px 22px; font-weight: bold; }
section[data-testid="stSidebar"] { background: rgba(15,23,42,0.88); backdrop-filter: blur(10px); }
</style>
""", unsafe_allow_html=True)

st.title("📄 PDF AI SaaS - Test Client")

# =========================
# AUTH
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
# UPLOAD PDF
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

        # Affichage des lignes contenant des montants (aide au débogage)
        st.subheader("🔍 Lignes contenant des chiffres et une devise (EUR/€/euro)")
        lines_with_money = [l for l in text.splitlines() 
                            if any(c.isdigit() for c in l) and ('EUR' in l or '€' in l or 'euro' in l.lower())]
        if lines_with_money:
            st.code("\n".join(lines_with_money[:30]))
        else:
            st.warning("Aucune ligne avec devise trouvée. Vérifiez que le texte est bien extrait.")

        # Devises
        currencies = extract_currencies(text)
        if currencies:
            st.subheader("💱 Wechselkurse (devises)")
            st.dataframe(pd.DataFrame(currencies), use_container_width=True)

        # ---------- Extraction des articles avec regex personnalisable ----------
        st.subheader("📦 Extraction des articles")
        
        # Regex par défaut (essaye de capturer quantité x description prix total)
        default_regex = r'(\d+(?:[\.,]\d+)?)\s*x\s*(.+?)\s+([\d\.,]+)\s*(?:EUR|€)?\s+([\d\.,]+)\s*(?:EUR|€)?'
        
        # Widget pour saisir/modifier la regex
        custom_regex = st.text_input("Expression régulière personnalisée (si vide, utilisation de la regex par défaut)", 
                                     value=default_regex, key="regex_input")
        regex_to_use = custom_regex if custom_regex.strip() else default_regex
        
        # Bouton pour lancer l'extraction avec la regex courante
        if st.button("🔄 Extraire les articles avec cette regex"):
            articles = extract_articles_with_regex(text, regex_to_use)
            if articles:
                st.success(f"{len(articles)} article(s) trouvé(s) !")
                st.session_state.articles_temp = articles   # stockage temporaire
                st.dataframe(pd.DataFrame(articles), use_container_width=True)
            else:
                st.error("Aucun article trouvé. Ajustez votre regex en vous aidant des lignes affichées ci-dessus.")
                st.session_state.articles_temp = []
        
        # Si des articles ont été extraits lors d'une tentative précédente, on les garde
        if 'articles_temp' in st.session_state and st.session_state.articles_temp:
            articles = st.session_state.articles_temp
        else:
            articles = []
        
        # Sauvegarde en base
        if st.button("💾 Sauvegarder les données extraites (articles seulement)"):
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

        # Aperçu du texte complet
        with st.expander("📄 Aperçu du texte extrait (premiers 2000 caractères)"):
            st.text_area("Texte du PDF", text[:2000], height=300)

    except Exception as e:
        st.error(f"❌ Erreur : {type(e).__name__} – {e}")
        st.exception(e)

# =========================
# AFFICHAGE DES DONNÉES SAUVEGARDÉES
# =========================
if st.session_state.json_data:
    d = st.session_state.json_data
    st.subheader("📦 Données sauvegardées")
    st.markdown(f"""
    <div class="pdf-card">
        <div class="info-row"><div class="info-label">📦 Articles</div><div class="info-value">{len(d.get("articles", []))} article(s)</div></div>
    </div>
    """, unsafe_allow_html=True)
    if d.get("articles"):
        st.dataframe(pd.DataFrame(d["articles"]), use_container_width=True)

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
# CHAT ASSISTANT (recherche textuelle simple)
# =========================
st.divider()
st.subheader("💬 Assistant PDF (recherche textuelle)")
q = st.chat_input("Posez une question sur le document actuel")
if q:
    if st.session_state.pdf_text:
        if q.lower() in st.session_state.pdf_text.lower():
            st.chat_message("assistant").write("Oui, cette information apparaît dans le document.")
        else:
            st.chat_message("assistant").write("Je n'ai pas trouvé cette information dans le PDF.")
    else:
        st.chat_message("assistant").write("Aucun PDF chargé. Téléchargez d'abord un document.")
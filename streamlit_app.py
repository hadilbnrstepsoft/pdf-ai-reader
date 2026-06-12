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
# EXTRACTION TEXTE PDF
# =========================
def extract_text(file_bytes):
    if not file_bytes:
        raise ValueError("Fichier vide")
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    full_text = ""
    for page in doc:
        full_text += page.get_text()
    return full_text

# =========================
# EXTRACTION DES ARTICLES (format tableau)
# =========================
def extract_articles_from_text(text):
    """
    Extrait les articles d'une facture ou bon de commande.
    Cherche les lignes contenant 'Pos.' puis extrait les données structurées.
    Exemple de ligne : "1  MA0R00004  10.000,0 kg  1,29  12.900,00  LDPE 150 E natur"
    """
    lines = text.splitlines()
    articles = []
    # On cherche la ligne contenant les en-têtes (Pos., Artikelnummer, Menge, etc.)
    header_index = -1
    for i, line in enumerate(lines):
        if "Pos." in line and "Artikelnummer" in line and "Menge" in line:
            header_index = i
            break
    
    if header_index == -1:
        # Fallback : chercher des motifs numériques sur les lignes suivantes
        # On va juste chercher des lignes qui commencent par un nombre et contiennent 'kg' ou 'EUR'
        pattern = re.compile(r'^(\d+)\s+(\S+)\s+([\d\.,]+\s*kg)\s+([\d\.,]+)\s+([\d\.,]+)\s+(.+)', re.IGNORECASE)
        for line in lines:
            match = pattern.match(line)
            if match:
                articles.append({
                    "article_number": match.group(2),
                    "description": match.group(6).strip(),
                    "quantity": match.group(3).replace('kg', '').strip(),
                    "price": match.group(4).replace(',', '.'),
                    "total": match.group(5).replace(',', '.')
                })
        return articles

    # On a trouvé l'en-tête, on parcourt les lignes suivantes
    for i in range(header_index+1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        # On essaie de splitter sur plusieurs espaces
        parts = re.split(r'\s{2,}', line)
        if len(parts) >= 6:
            # Format: Pos. Artikelnummer Menge Preis Gesamtpreis Bezeichnung
            # parts[0] = Pos (on ignore)
            artikel_nummer = parts[1]
            menge = parts[2].replace('kg', '').strip()
            preis = parts[3].replace(',', '.')
            gesamt = parts[4].replace(',', '.')
            bezeichnung = parts[5]
            articles.append({
                "article_number": artikel_nummer,
                "description": bezeichnung,
                "quantity": menge,
                "price": preis,
                "total": gesamt
            })
        else:
            # Essayer un autre pattern (ligne sans séparateurs multiples)
            pattern = re.compile(r'^\d+\s+(\S+)\s+([\d\.,]+\s*kg)\s+([\d\.,]+)\s+([\d\.,]+)\s+(.+)')
            match = pattern.match(line)
            if match:
                articles.append({
                    "article_number": match.group(1),
                    "description": match.group(5).strip(),
                    "quantity": match.group(2).replace('kg', '').strip(),
                    "price": match.group(3).replace(',', '.'),
                    "total": match.group(4).replace(',', '.')
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

        # Aperçu du texte pour débogage (optionnel)
        with st.expander("🔍 Aperçu du texte brut (premières lignes)"):
            st.code("\n".join(text.splitlines()[:40]))

        # Extraction des articles
        articles = extract_articles_from_text(text)
        if articles:
            st.subheader("📦 Articles extraits")
            df_articles = pd.DataFrame(articles)
            st.dataframe(df_articles, use_container_width=True)
        else:
            st.info("Aucun article trouvé. Vérifiez le format du PDF (doit contenir des lignes avec 'Pos.' et des valeurs).")

        # Sauvegarde en base
        if st.button("💾 Sauvegarder les articles en base"):
            data = {"articles": articles}
            st.session_state.json_data = data
            save_pdf(st.session_state.user_id, file.name, data)
            st.success("✅ Données sauvegardées")

        # Afficher le JSON extrait (pour info)
        if articles:
            st.subheader("📄 Données JSON extraites")
            st.json({"articles": articles})

    except Exception as e:
        st.error(f"❌ Erreur : {type(e).__name__} – {e}")
        st.exception(e)

# =========================
# AFFICHAGE DES DONNÉES SAUVEGARDÉES
# =========================
if st.session_state.json_data:
    st.subheader("📦 Données sauvegardées (dernier PDF)")
    st.json(st.session_state.json_data)

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
# CHAT ASSISTANT (recherche améliorée)
# =========================
st.divider()
st.subheader("💬 Assistant PDF (recherche dans le texte)")
if st.session_state.pdf_text:
    st.info("Vous pouvez poser des questions sur le contenu du document actuel.")
    q = st.chat_input("Votre question")
    if q:
        # Recherche simple par mots-clés
        text_lower = st.session_state.pdf_text.lower()
        q_lower = q.lower()
        if q_lower in text_lower:
            # Extraire le contexte autour de la réponse
            idx = text_lower.find(q_lower)
            start = max(0, idx-100)
            end = min(len(text_lower), idx+200)
            snippet = st.session_state.pdf_text[start:end]
            st.chat_message("assistant").write(f"Oui, j'ai trouvé :\n\n...{snippet}...")
        else:
            # Proposer des mots clés alternatifs
            words = q_lower.split()
            found = []
            for word in words:
                if word in text_lower and len(word) > 3:
                    found.append(word)
            if found:
                st.chat_message("assistant").write(f"Je n'ai pas trouvé exactement '{q}', mais voici des mots présents : {', '.join(found)}. Essayez avec ces termes.")
            else:
                st.chat_message("assistant").write("Désolé, je n'ai pas trouvé cette information dans le document.")
else:
    st.info("Téléchargez un PDF pour pouvoir poser des questions.")
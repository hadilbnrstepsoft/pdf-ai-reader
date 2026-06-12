import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="PDF SaaS", layout="wide")

# =========================
# SESSION STATE
# =========================
if "users" not in st.session_state:
    st.session_state.users = {}  # fake DB

if "user" not in st.session_state:
    st.session_state.user = None

# =========================
# REGISTER
# =========================
def register_page():

    st.title("🆕 Create Account")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Create account"):

        if email in st.session_state.users:
            st.error("User already exists")
        else:
            st.session_state.users[email] = password
            st.success("Account created ✔ You can login now")

# =========================
# LOGIN
# =========================
def login_page():

    st.title("🔐 Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Login"):

            if email in st.session_state.users and st.session_state.users[email] == password:
                st.session_state.user = email
                st.rerun()
            else:
                st.error("Invalid credentials")

    with col2:
        if st.button("Create account"):
            st.session_state.page = "register"

# =========================
# PDF PAGE (YOUR APP)
# =========================
def pdf_page():

    st.title("📄 PDF AI SaaS")

    st.success(f"Welcome {st.session_state.user} ✔")

    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()

    st.divider()

    # 👉 PDF UPLOAD SECTION
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

    if uploaded_file:
        st.write("📄 PDF uploaded successfully")
        st.write("👉 Here you will connect your AI extraction logic")

# =========================
# ROUTING SYSTEM
# =========================
if st.session_state.user:
    pdf_page()

else:

    if "page" not in st.session_state:
        st.session_state.page = "login"

    if st.session_state.page == "login":
        login_page()

    elif st.session_state.page == "register":
        register_page()
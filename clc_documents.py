"""
CLC Document Library
Leadership resources & Policies (DfE / LBU / CLC)
Backed by Supabase Storage + documents table
"""

import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import uuid
import os

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CLC Document Library",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── STYLING ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { font-family: 'Inter', sans-serif; }
  .stApp { background: #f8fafc; }

  .stButton>button {
    background: #1e293b !important; color: white !important;
    border: none !important; border-radius: 6px !important;
    padding: 0.45rem 1.1rem !important; font-weight: 600 !important;
    transition: all 0.15s !important;
  }
  .stButton>button:hover { background: #0f172a !important; }
  button[kind="primary"] { background: #2563eb !important; }
  button[kind="primary"]:hover { background: #1d4ed8 !important; }

  .doc-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  }
  .doc-icon { font-size: 1.6rem; flex-shrink: 0; }
  .doc-info { flex: 1; min-width: 0; }
  .doc-title { font-weight: 600; font-size: 0.95rem; color: #0f172a; }
  .doc-meta  { font-size: 0.78rem; color: #64748b; margin-top: 2px; }

  .section-banner {
    background: linear-gradient(135deg, #1e293b, #334155);
    color: white;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.25rem;
  }
  .section-banner h2 { margin: 0; font-size: 1.15rem; font-weight: 700; }
  .section-banner p  { margin: 0.2rem 0 0; font-size: 0.83rem; opacity: 0.75; }

  .upload-area {
    background: white;
    border: 2px dashed #cbd5e1;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
  }

  .stTabs [data-baseweb="tab-list"] { gap: 4px; }
  .stTabs [data-baseweb="tab"] {
    font-weight: 600 !important;
    border-radius: 6px 6px 0 0 !important;
  }
  [data-testid="stFileUploader"] label { font-weight: 500; }
</style>
""", unsafe_allow_html=True)

# ── SUPABASE ───────────────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client | None:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.warning(f"Supabase not connected: {e}")
        return None

supabase: Client | None = init_supabase()

BUCKET = "clc-documents"

# ── POLICY SECTIONS ────────────────────────────────────────────────────────────
SECTIONS = {
    "policy_dfe": {
        "label":    "DfE Policies",
        "icon":     "📘",
        "colour":   "#1d4ed8",
        "desc":     "Department for Education policies and directives",
        "tab_icon": "📘",
    },
    "policy_lbu": {
        "label":    "LBU Policies",
        "icon":     "📗",
        "colour":   "#15803d",
        "desc":     "Learning and Behaviour Unit policies and procedures",
        "tab_icon": "📗",
    },
    "policy_clc": {
        "label":    "CLC Policies",
        "icon":     "📙",
        "colour":   "#b45309",
        "desc":     "Cowandilla Learning Centre policies and procedures",
        "tab_icon": "📙",
    },
}

# ── DB HELPERS ─────────────────────────────────────────────────────────────────
def load_docs(section: str) -> list:
    """Load document records for a section from Supabase."""
    if not supabase:
        return st.session_state.get(f"local_docs_{section}", [])
    try:
        resp = (
            supabase.table("clc_documents")
            .select("*")
            .eq("section", section)
            .order("uploaded_at", desc=True)
            .execute()
        )
        return resp.data or []
    except Exception as e:
        st.error(f"Could not load documents: {e}")
        return []


def save_doc_record(section: str, title: str, filename: str,
                    storage_path: str, uploaded_by: str, file_size: int) -> bool:
    """Save document metadata to the database."""
    record = {
        "id":            str(uuid.uuid4()),
        "section":       section,
        "title":         title.strip(),
        "filename":      filename,
        "storage_path":  storage_path,
        "uploaded_by":   uploaded_by,
        "uploaded_at":   datetime.now().isoformat(),
        "file_size_kb":  round(file_size / 1024, 1),
    }
    if supabase:
        try:
            supabase.table("clc_documents").insert(record).execute()
            return True
        except Exception as e:
            st.error(f"Could not save record: {e}")
            return False
    else:
        # Local fallback
        key = f"local_docs_{section}"
        if key not in st.session_state:
            st.session_state[key] = []
        st.session_state[key].insert(0, record)
        return True


def delete_doc(doc: dict) -> bool:
    """Delete document from storage and database."""
    if supabase:
        try:
            supabase.storage.from_(BUCKET).remove([doc["storage_path"]])
            supabase.table("clc_documents").delete().eq("id", doc["id"]).execute()
            return True
        except Exception as e:
            st.error(f"Delete failed: {e}")
            return False
    return False


def get_download_url(storage_path: str) -> str | None:
    """Get a signed download URL (valid 1 hour)."""
    if not supabase:
        return None
    try:
        resp = supabase.storage.from_(BUCKET).create_signed_url(storage_path, 3600)
        return resp.get("signedURL") or resp.get("signed_url")
    except Exception:
        return None


# ── AUTH (simple admin check) ──────────────────────────────────────────────────
def check_admin() -> bool:
    """Returns True if current session is admin-authenticated."""
    return st.session_state.get("is_admin", False)


def render_admin_login():
    with st.expander("🔐 Admin Login", expanded=False):
        pwd = st.text_input("Admin password", type="password", key="admin_pwd_input")
        if st.button("Login as Admin", key="admin_login_btn"):
            try:
                admin_pass = st.secrets.get("admin_password", "CLC2026admin")
            except Exception:
                admin_pass = "CLC2026admin"
            if pwd == admin_pass:
                st.session_state.is_admin = True
                st.success("✅ Admin access granted")
                st.rerun()
            else:
                st.error("Incorrect password")


# ── SECTION RENDERER ───────────────────────────────────────────────────────────
def render_admin_inline(section_key: str):
    """Compact inline admin login/logout bar shown at top of each section."""
    if check_admin():
        col1, col2 = st.columns([5, 1])
        with col1:
            st.success("🔐 Admin mode — upload panel is open below")
        with col2:
            if st.button("Logout", key=f"admin_logout_{section_key}"):
                st.session_state.is_admin = False
                st.rerun()
    else:
        with st.expander("🔐 Admin Login — click here to upload documents", expanded=False):
            pwd = st.text_input("Admin password", type="password", key=f"admin_pwd_{section_key}")
            if st.button("Login", key=f"admin_login_{section_key}", type="primary"):
                try:
                    admin_pass = st.secrets.get("admin_password", "CLC2026admin")
                except Exception:
                    admin_pass = "CLC2026admin"
                if pwd == admin_pass:
                    st.session_state.is_admin = True
                    st.success("✅ Logged in")
                    st.rerun()
                else:
                    st.error("Incorrect password")


def render_section(section_key: str):
    cfg = SECTIONS[section_key]

    st.markdown(f"""
    <div class="section-banner">
      <h2>{cfg['icon']} {cfg['label']}</h2>
      <p>{cfg['desc']}</p>
    </div>
    """, unsafe_allow_html=True)

    # Inline admin login/logout
    render_admin_inline(section_key)
    st.markdown("")

    docs = load_docs(section_key)

    # ── UPLOAD (admin only) ────────────────────────────────────────────────────
    if check_admin():
        with st.expander("➕ Upload New Document", expanded=True):
            with st.container():
                doc_title = st.text_input(
                    "Document Title *",
                    placeholder="e.g. Student Behaviour Support Policy 2026",
                    key=f"title_{section_key}"
                )
                uploaded_file = st.file_uploader(
                    "Choose file",
                    type=["pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "png", "jpg", "jpeg", "txt"],
                    key=f"upload_{section_key}",
                    help="Accepted: PDF, Word, Excel, PowerPoint, images, text"
                )
                uploader_name = st.text_input(
                    "Your name",
                    placeholder="e.g. Candice Cooper",
                    key=f"uploader_{section_key}"
                )

                if st.button("📤 Upload Document", key=f"upload_btn_{section_key}", type="primary"):
                    if not doc_title:
                        st.warning("Please enter a document title.")
                    elif not uploaded_file:
                        st.warning("Please select a file.")
                    else:
                        file_ext    = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else "bin"
                        safe_name   = uploaded_file.name.replace(" ", "_")
                        storage_path = f"{section_key}/{uuid.uuid4().hex[:8]}_{safe_name}"
                        file_bytes  = uploaded_file.read()

                        upload_ok = True
                        if supabase:
                            try:
                                supabase.storage.from_(BUCKET).upload(
                                    storage_path,
                                    file_bytes,
                                    {"content-type": uploaded_file.type or "application/octet-stream"}
                                )
                            except Exception as e:
                                st.error(f"Storage upload failed: {e}")
                                upload_ok = False

                        if upload_ok:
                            saved = save_doc_record(
                                section_key,
                                doc_title,
                                uploaded_file.name,
                                storage_path,
                                uploader_name or "Admin",
                                len(file_bytes)
                            )
                            if saved:
                                st.success(f"✅ '{doc_title}' uploaded successfully!")
                                st.rerun()

    # ── DOCUMENT LIST ──────────────────────────────────────────────────────────
    if not docs:
        st.info("No documents uploaded yet." + (" Use the upload panel above to add the first one." if check_admin() else ""))
        return

    st.markdown(f"**{len(docs)} document{'s' if len(docs) != 1 else ''}**")

    for doc in docs:
        ext = doc.get("filename", "").rsplit(".", 1)[-1].lower() if "." in doc.get("filename", "") else ""
        icon = {
            "pdf": "📕", "docx": "📝", "doc": "📝",
            "xlsx": "📊", "xls": "📊", "pptx": "📊", "ppt": "📊",
            "png": "🖼️", "jpg": "🖼️", "jpeg": "🖼️", "txt": "📄"
        }.get(ext, "📄")

        try:
            ts = datetime.fromisoformat(doc["uploaded_at"]).strftime("%d %b %Y")
        except Exception:
            ts = doc.get("uploaded_at", "")[:10]

        size_str = f"{doc.get('file_size_kb', '?')} KB" if doc.get("file_size_kb") else ""
        by_str   = f"Uploaded by {doc['uploaded_by']} · " if doc.get("uploaded_by") else ""

        col_info, col_btn = st.columns([5, 2])
        with col_info:
            st.markdown(f"""
            <div class="doc-card">
              <div class="doc-icon">{icon}</div>
              <div class="doc-info">
                <div class="doc-title">{doc['title']}</div>
                <div class="doc-meta">{by_str}{ts}{' · ' + size_str if size_str else ''}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        with col_btn:
            st.write("")  # vertical align spacer
            url = get_download_url(doc.get("storage_path", ""))
            if url:
                st.link_button("⬇ Download", url, use_container_width=True)
            else:
                st.caption("No download link")
            if check_admin():
                if st.button("🗑️ Delete", key=f"del_{doc['id']}", use_container_width=True):
                    st.session_state[f"confirm_del_{doc['id']}"] = True
                    st.rerun()
                if st.session_state.get(f"confirm_del_{doc['id']}"):
                    st.warning(f"Delete '{doc['title']}'?")
                    cy, cn = st.columns(2)
                    with cy:
                        if st.button("Yes", key=f"yes_del_{doc['id']}", type="primary"):
                            if delete_doc(doc):
                                st.session_state[f"confirm_del_{doc['id']}"] = False
                                st.success("Deleted")
                                st.rerun()
                    with cn:
                        if st.button("No", key=f"no_del_{doc['id']}"):
                            st.session_state[f"confirm_del_{doc['id']}"] = False
                            st.rerun()


# ── MAIN ───────────────────────────────────────────────────────────────────────
def main():
    st.markdown("""
    <div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);
                color:white;border-radius:12px;padding:1.25rem 1.5rem;
                margin-bottom:1.5rem;">
      <h1 style="margin:0;font-size:1.4rem;font-weight:700;">📄 CLC Policies</h1>
      <p style="margin:0.3rem 0 0;opacity:0.7;font-size:0.85rem;">
        DfE, LBU &amp; CLC policies and procedures
      </p>
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 📄 CLC Policies")
        st.caption("Cowandilla Learning Centre")
        st.markdown("---")
        if check_admin():
            st.success("✅ Admin mode active")
            if st.button("Logout Admin", key="sidebar_logout"):
                st.session_state.is_admin = False
                st.rerun()
        else:
            st.info("Log in as admin on any tab to upload documents.")

    # Deep-link: ?section=policy_dfe / policy_lbu / policy_clc
    params = st.query_params
    default_section = params.get("section", "policy_dfe")
    policy_keys = ["policy_dfe", "policy_lbu", "policy_clc"]
    default_idx = policy_keys.index(default_section) if default_section in policy_keys else 0

    tabs = st.tabs(["📘 DfE Policies", "📗 LBU Policies", "📙 CLC Policies"])

    for i, key in enumerate(policy_keys):
        with tabs[i]:
            render_section(key)


if __name__ == "__main__":
    main()

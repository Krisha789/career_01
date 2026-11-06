
import io
import os
import sqlite3
import time
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st
from docx import Document
from google import genai

MODEL = "gemini-3.8-flash"   
FALLBACK_MODELS = ["gemini-flash-latest"]   # used if the main model is busy
DB_FILE = "career.db"

st.set_page_config(page_title="CareerCraft AI", page_icon="🧭", layout="wide")

# ---------------------------------------------------------------- 1. DATABASE
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS history (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               created TEXT, name TEXT, role TEXT, content_type TEXT, output TEXT)"""
    )
    return conn


def save(name, role, content_type, output):
    with db() as conn:
        conn.execute(
            "INSERT INTO history (created, name, role, content_type, output) VALUES (?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M"), name, role, content_type, output),
        )


def load_history():
    with db() as conn:
        return conn.execute(
            "SELECT id, created, name, role, content_type, output FROM history ORDER BY id DESC LIMIT 100"
        ).fetchall()


def delete_item(item_id):
    with db() as conn:
        conn.execute("DELETE FROM history WHERE id = ?", (item_id,))


def clear_history():
    with db() as conn:
        conn.execute("DELETE FROM history")

# ---------------------------------------------------------------- 2. PROMPTS
# Each content type has its own task instruction. The user's details are
# inserted into a common template -> this is what makes the output "personalized".
TASKS = {
    "Resume Summary": "Write a 3-4 line professional resume summary.",
    "Cover Letter": "Write a one-page cover letter (about 250 words) for this role.",
    "LinkedIn Bio": "Write a LinkedIn 'About' section (about 120 words) in first person.",
    "Skill Roadmap": "Create a 90-day learning roadmap with weekly goals and free resources to reach this role.",
    "Interview Prep": "List 8 likely interview questions for this role with short sample answers.",
    "Career Paths": "Suggest 3 suitable career paths with required skills, entry roles and growth outlook.",
}

# Icon + one-line description for each content type (used on Home and in the form)
TASK_INFO = {
    "Resume Summary": ("📝", "A tight 3-4 line summary for the top of your resume."),
    "Cover Letter": ("✉️", "A one-page letter written for the exact role you want."),
    "LinkedIn Bio": ("💼", "A first-person 'About' section that sounds like you."),
    "Skill Roadmap": ("🗺️", "A 90-day plan with weekly goals and free resources."),
    "Interview Prep": ("🎤", "Eight likely questions with sample answers."),
    "Career Paths": ("🧭", "Three paths that fit your skills, with growth outlook."),
}


def build_prompt(profile, content_type):
    return f"""You are an expert career coach.
{TASKS[content_type]}

Candidate profile:
- Name: {profile['name']}
- Education: {profile['education']}
- Skills: {profile['skills']}
- Interests: {profile['interests']}
- Experience level: {profile['level']}
- Target role: {profile['role']}

Tone: {profile['tone']}.
Use only the details given; do not invent employers, degrees or achievements.
Format the answer in clean Markdown."""

# ---------------------------------------------------------------- 3. AI CALL
def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.getenv("GEMINI_API_KEY") or st.session_state.get("typed_key", "")


@st.cache_data(ttl=600, show_spinner=False)
def list_models(api_key):
    """Ask Google which Gemini models this key can use for text generation."""
    try:
        client = genai.Client(api_key=api_key)
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" in actions and "gemini" in m.name:
                names.append(m.name.replace("models/", ""))
        return sorted(set(names))
    except Exception:
        return []


def generate(prompt, api_key, chosen):
    """Call Gemini. If the model is busy (503), retry, then try other models."""
    client = genai.Client(api_key=api_key)
    others = [m for m in list_models(api_key) if "flash" in m and m != chosen][:4]
    last_error = None
    for model in [chosen] + others + FALLBACK_MODELS:
        for attempt in range(3):
            try:
                return client.models.generate_content(model=model, contents=prompt).text
            except Exception as e:
                last_error = e
                if "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e):
                    time.sleep(2 * (attempt + 1))   # wait 2s, 4s, 6s then retry
                else:
                    break   # other errors (bad key, wrong model): try next model
    raise last_error

# ---------------------------------------------------------------- 4. EXPORT
def to_docx(name, role, results):
    doc = Document()
    doc.add_heading(f"Career Content for {name}", 0)
    doc.add_paragraph(f"Target role: {role}")
    for title, text in results.items():
        doc.add_heading(title, 1)
        for line in text.splitlines():
            if line.strip():
                doc.add_paragraph(line.replace("**", "").lstrip("#*- ").strip())
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- 5a. IMAGES
# Illustrations are drawn as SVG inside the code, so no image files are needed.
import base64


def svg_img(svg, cls="", alt=""):
    b64 = base64.b64encode(svg.encode()).decode()
    return f'<img class="{cls}" alt="{alt}" src="data:image/svg+xml;base64,{b64}"/>'


HERO_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 420 320'>
<circle cx='320' cy='70' r='46' fill='#F2A93B' opacity='.95'/>
<circle cx='70' cy='60' r='7' fill='#14B8A6'/><circle cx='110' cy='28' r='4' fill='#fff' opacity='.7'/>
<circle cx='380' cy='170' r='5' fill='#fff' opacity='.6'/>
<rect x='40' y='238' width='86' height='52' rx='6' fill='#1F8F83'/>
<rect x='126' y='198' width='86' height='92' rx='6' fill='#14B8A6'/>
<rect x='212' y='156' width='86' height='134' rx='6' fill='#5EEAD4'/>
<rect x='298' y='110' width='86' height='180' rx='6' fill='#F6F4EF'/>
<rect x='26' y='290' width='372' height='8' rx='4' fill='#0B1826'/>
<line x1='341' y1='110' x2='341' y2='52' stroke='#F6F4EF' stroke-width='5' stroke-linecap='round'/>
<path d='M341 54 L383 68 L341 84 Z' fill='#F2A93B'/>
<circle cx='256' cy='112' r='15' fill='#F6F4EF'/><rect x='241' y='128' width='30' height='28' rx='12' fill='#F6F4EF'/>
<path d='M70 214 L156 176 L242 134 L330 94' stroke='#fff' stroke-width='3' stroke-dasharray='2 9' stroke-linecap='round' fill='none' opacity='.75'/>
</svg>"""

DESK_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 200'>
<rect width='300' height='200' rx='18' fill='#E6F4F1'/>
<circle cx='245' cy='48' r='26' fill='#F2A93B'/>
<rect x='70' y='58' width='160' height='98' rx='9' fill='#16263A'/>
<rect x='78' y='66' width='144' height='82' rx='4' fill='#fff'/>
<rect x='88' y='78' width='60' height='8' rx='4' fill='#0E8F80'/>
<rect x='88' y='94' width='110' height='6' rx='3' fill='#C9D3DF'/>
<rect x='88' y='107' width='96' height='6' rx='3' fill='#C9D3DF'/>
<rect x='88' y='120' width='104' height='6' rx='3' fill='#C9D3DF'/>
<rect x='170' y='124' width='42' height='16' rx='5' fill='#F2A93B'/>
<path d='M48 160 H252 L240 172 H60 Z' fill='#16263A'/>
<rect x='36' y='176' width='228' height='8' rx='4' fill='#0E8F80'/>
<g transform='translate(34 120)'><rect x='0' y='14' width='22' height='26' rx='4' fill='#0E8F80'/>
<path d='M11 14 C4 0 -2 6 4 -2 M11 14 C14 -2 22 4 18 -4' stroke='#0E8F80' stroke-width='4' fill='none' stroke-linecap='round'/></g>
</svg>"""

EMPTY_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 160'>
<rect width='240' height='160' rx='16' fill='#EFEBE0'/>
<rect x='56' y='34' width='128' height='96' rx='8' fill='#fff' stroke='#DDD8CC' stroke-width='2'/>
<rect x='70' y='52' width='60' height='8' rx='4' fill='#0E8F80'/>
<rect x='70' y='72' width='100' height='6' rx='3' fill='#DDD8CC'/>
<rect x='70' y='86' width='84' height='6' rx='3' fill='#DDD8CC'/>
<rect x='70' y='100' width='92' height='6' rx='3' fill='#DDD8CC'/>
<circle cx='184' cy='34' r='16' fill='#F2A93B'/><path d='M177 34 l5 5 l9 -10' stroke='#16263A' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/>
</svg>"""

_ICON_GLYPHS = {
    "Resume Summary": "<rect x='15' y='11' width='18' height='26' rx='3' fill='none' stroke='#fff' stroke-width='3'/><path d='M20 19h8M20 25h8M20 31h5' stroke='#fff' stroke-width='3' stroke-linecap='round'/>",
    "Cover Letter": "<rect x='11' y='15' width='26' height='19' rx='3' fill='none' stroke='#fff' stroke-width='3'/><path d='M12 17l12 10 12-10' fill='none' stroke='#fff' stroke-width='3' stroke-linejoin='round'/>",
    "LinkedIn Bio": "<circle cx='24' cy='19' r='6' fill='none' stroke='#fff' stroke-width='3'/><path d='M13 37c1-8 7-11 11-11s10 3 11 11' fill='none' stroke='#fff' stroke-width='3' stroke-linecap='round'/>",
    "Skill Roadmap": "<circle cx='14' cy='35' r='4' fill='#fff'/><circle cx='34' cy='13' r='4' fill='#fff'/><path d='M14 31c0-9 20-3 20-14' fill='none' stroke='#fff' stroke-width='3' stroke-dasharray='1 5' stroke-linecap='round'/>",
    "Interview Prep": "<path d='M12 14h24v16H24l-8 7v-7h-4z' fill='none' stroke='#fff' stroke-width='3' stroke-linejoin='round'/><path d='M19 22h10' stroke='#fff' stroke-width='3' stroke-linecap='round'/>",
    "Career Paths": "<path d='M24 38V12M24 14h12l-3 5 3 5H24' fill='none' stroke='#fff' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/>",
}
_ICON_COLORS = {"Resume Summary": "#0E8F80", "Cover Letter": "#D9822B", "LinkedIn Bio": "#2D6CDF",
                "Skill Roadmap": "#7A4FD6", "Interview Prep": "#D4456B", "Career Paths": "#16263A"}


def type_icon(t):
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'><rect width='48' height='48' rx='12' "
           f"fill='{_ICON_COLORS[t]}'/>{_ICON_GLYPHS[t]}</svg>")
    return svg_img(svg, "ico", t)

# ---------------------------------------------------------------- 5. STYLE
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=DM+Sans:wght@400;500;700&display=swap');

:root { --ink:#16263A; --paper:#F6F4EF; --teal:#0E8F80; --amber:#F2A93B; --line:#CFC9BA; --muted:#44546A; }

/* --- force a light, high-contrast page even if the browser/OS is in dark mode --- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background:var(--paper) !important; }
.stApp, .stApp p, .stApp li, .stApp span, .stApp label, .stApp div { color:var(--ink); }
html, body, [class*="css"], .stApp { font-family:'DM Sans', sans-serif; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { font-family:'Fraunces', Georgia, serif !important; color:var(--ink) !important;
        letter-spacing:-.01em; font-weight:700 !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, .stApp label p { color:var(--ink) !important; font-weight:700 !important; font-size:.98rem !important; }
.stCaption, [data-testid="stCaptionContainer"] { color:var(--muted) !important; }
.block-container { padding-top:2rem; max-width:1100px; }
#MainMenu, footer { visibility:hidden; }

/* input boxes: white background, dark text */
.stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
    background:#fff !important; color:var(--ink) !important; border:1px solid var(--line) !important; border-radius:10px !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder { color:#7A8798 !important; opacity:1; }
div[data-baseweb="select"] span, div[data-baseweb="select"] div { color:var(--ink) !important; }
div[data-baseweb="tag"] { background:#D7EFEA !important; } div[data-baseweb="tag"] span { color:var(--ink) !important; }
ul[role="listbox"], div[data-baseweb="popover"] li { background:#fff !important; color:var(--ink) !important; }

/* hero */
.hero { background:var(--ink); border-radius:22px; padding:2.4rem 2.6rem; margin-bottom:1.6rem;
        border-bottom:6px solid var(--amber); display:flex; align-items:center; gap:1.5rem; }
.hero-text { flex:1 1 55%; }
.hero-img { flex:1 1 40%; max-width:400px; }
.hero-img img { width:100%; height:auto; display:block; }
.stApp .hero h1 { color:#FFFFFF !important; font-size:2.8rem; line-height:1.1; margin:0 0 .8rem; padding:0; }
.stApp .hero p { color:#DCE4EE !important; font-size:1.1rem; margin:0; }
.page-head { display:flex; align-items:center; gap:1.4rem; background:#fff; border:1px solid var(--line);
             border-radius:18px; padding:1rem 1.4rem; margin-bottom:1.2rem; }
.page-head img { width:150px; height:auto; flex:none; border-radius:12px; }
.page-head h1 { font-size:2rem; margin:0 0 .2rem; padding:0; }
.page-head p { margin:0; color:var(--muted) !important; }

/* content-type cards */
.card { background:#fff; border:1px solid var(--line); border-radius:14px; padding:1rem 1.1rem; min-height:130px; margin-bottom:.8rem;
        display:flex; gap:.9rem; align-items:flex-start; }
.card .ico { width:48px; height:48px; flex:none; }
.card b { font-family:'Fraunces', serif; font-size:1.08rem; color:var(--ink) !important; }
.card span { display:block; color:var(--muted) !important; font-size:.93rem; margin-top:.25rem; }

/* steps */
.step { display:flex; gap:.9rem; align-items:flex-start; margin:.7rem 0; }
.step i { flex:none; width:2rem; height:2rem; border-radius:50%; background:var(--amber); color:var(--ink) !important;
          font-style:normal; font-weight:700; display:flex; align-items:center; justify-content:center; }
.step p { margin:.2rem 0 0; }
.empty { text-align:center; padding:1.5rem 0; } .empty img { width:240px; max-width:80%; }

/* form + buttons */
div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.4rem; }
.stButton > button, .stDownloadButton > button, div[data-testid="stFormSubmitButton"] > button { border-radius:10px; font-weight:700; }
.stApp button[kind="primary"], .stApp button[kind="primaryFormSubmit"] { background:var(--teal) !important; border:none !important; }
.stApp button[kind="primary"] *, .stApp button[kind="primaryFormSubmit"] * { color:#fff !important; }
.stApp button[kind="primary"]:hover, .stApp button[kind="primaryFormSubmit"]:hover { background:#0B7569 !important; }
.stApp button[kind="secondary"] { background:#fff !important; border:1px solid var(--line) !important; }
.stApp button[kind="secondary"] * { color:var(--ink) !important; }
button[data-baseweb="tab"] p { color:var(--ink) !important; font-weight:500; }
[data-testid="stExpander"] { background:#fff; border:1px solid var(--line); border-radius:12px; }
[data-testid="stExpander"] summary p { color:var(--ink) !important; font-weight:700; }


/* --- dropdowns (Model, Tone, Experience level...): always white box, dark readable text --- */
div[data-baseweb="select"], div[data-baseweb="select"] > div, div[data-baseweb="select"] > div > div,
div[data-baseweb="select"] input { background:#FFFFFF !important; color:#16263A !important;
        -webkit-text-fill-color:#16263A !important; opacity:1 !important; }
div[data-baseweb="select"] svg { fill:#16263A !important; color:#16263A !important; }
div[data-baseweb="select"] > div { border:1.5px solid #8A97A8 !important; min-height:2.6rem; }
div[data-baseweb="select"] [class*="singleValue"], div[data-baseweb="select"] div[value],
div[data-baseweb="select"] span { color:#16263A !important; -webkit-text-fill-color:#16263A !important; font-weight:500; }
div[data-baseweb="popover"], div[data-baseweb="popover"] > div, div[data-baseweb="menu"],
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li, div[data-baseweb="popover"] li * {
        background:#FFFFFF !important; color:#16263A !important; -webkit-text-fill-color:#16263A !important; }
div[data-baseweb="popover"] li:hover, div[data-baseweb="popover"] li[aria-selected="true"] { background:#D7EFEA !important; }
section[data-testid="stSidebar"] div[data-baseweb="select"] * { color:#16263A !important; }
/* sidebar slider text */
section[data-testid="stSidebar"] [data-testid="stSlider"] * { color:#16263A !important; }

/* --- metrics + chart cards --- */
[data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:14px; padding:.9rem 1.1rem; }
[data-testid="stMetricLabel"] p { color:var(--muted) !important; font-weight:500 !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color:var(--ink) !important; font-family:'Fraunces',serif !important; }
[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border-color:var(--line) !important; border-radius:14px; }

/* sidebar */
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div { background:#E9E4D6 !important; }
section[data-testid="stSidebar"] * { color:var(--ink); }
section[data-testid="stSidebar"] .stTextInput input { color:var(--ink) !important; }
@media (max-width:760px) { .hero { flex-direction:column; padding:1.6rem 1.3rem; } .stApp .hero h1 { font-size:2.1rem; }
        .page-head { flex-direction:column; align-items:flex-start; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- 6. SIDEBAR (shared by all pages)
with st.sidebar:
    st.markdown("### 🧭 CareerCraft AI")
    st.caption("Settings")
    st.text_input("Gemini API key", type="password", key="typed_key",
                  help="Paste the key and press Enter. Get a free key at aistudio.google.com")
    if get_api_key():
        st.success("API key loaded")
    else:
        st.info("Add your free Gemini key to start.")
    tone = st.select_slider("Tone", ["Friendly", "Professional", "Confident", "Formal"], value="Professional")
    available = list_models(get_api_key()) if get_api_key() else []
    choices = available or [MODEL]
    # default to a lighter "flash-lite" model if present (usually less busy)
    default = next((i for i, m in enumerate(choices) if "flash-lite" in m), 0)
    model_choice = st.selectbox("Model", choices, index=default,
                                help="If you get a 'high demand' error, pick a different model.")
    st.caption("AI can make mistakes. Review and edit before using.")

# ---------------------------------------------------------------- 7. PAGES
def page_home():
    st.markdown(
        f"""<div class="hero"><div class="hero-text"><h1>Your next job application, written around you.</h1>
        <p>Tell us your skills and the role you want. Get a resume summary, cover letter,
        90-day roadmap and interview prep in under a minute.</p></div>
        <div class="hero-img">{svg_img(HERO_SVG, alt="Steps leading up to a career goal")}</div></div>""",
        unsafe_allow_html=True,
    )
    if st.button("Start creating", type="primary"):
        st.switch_page(gen_page)

    st.markdown("## What you can create")
    items = list(TASK_INFO.items())
    for row in range(0, len(items), 3):
        cols = st.columns(3)
        for col, (title, (icon, desc)) in zip(cols, items[row:row + 3]):
            col.markdown(f'<div class="card">{type_icon(title)}<div><b>{title}</b><span>{desc}</span></div></div>',
                         unsafe_allow_html=True)

    st.markdown("## How it works")
    st.markdown(
        """<div class="step"><i>1</i><p><b>Fill your profile.</b> Name, education, skills and target role.</p></div>
        <div class="step"><i>2</i><p><b>Pick what you need.</b> Choose one or several content types and a tone.</p></div>
        <div class="step"><i>3</i><p><b>Review and download.</b> Edit the result, copy it or export everything to Word.</p></div>""",
        unsafe_allow_html=True,
    )


def page_generate():
    st.markdown(
        f"""<div class="page-head">{svg_img(DESK_SVG, alt="Laptop on a desk")}
        <div><h1>Create your content</h1>
        <p>Fields marked * are required. The more detail you add, the better the result.</p></div></div>""",
        unsafe_allow_html=True,
    )

    with st.form("profile"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name *")
        role = c2.text_input("Target role *", placeholder="e.g. Data Analyst")
        education = c1.text_input("Education", placeholder="B.Tech CSE, 2026")
        level = c2.selectbox("Experience level", ["Student / Fresher", "0-2 years", "2-5 years", "5+ years"])
        skills = st.text_area("Skills *", placeholder="Python, SQL, Excel, Power BI")
        interests = st.text_input("Interests", placeholder="AI, finance, open source")
        types = st.multiselect("What should I generate? *", list(TASKS), default=["Resume Summary", "Skill Roadmap"],
                               format_func=lambda t: f"{TASK_INFO[t][0]} {t}")
        submitted = st.form_submit_button("Generate content", type="primary", use_container_width=True)

    if submitted:
        if not (name and role and skills and types):
            st.warning("Fill in your name, target role and skills, and pick at least one content type.")
        elif not get_api_key():
            st.error("Add your Gemini API key in the sidebar first.")
        else:
            profile = dict(name=name, role=role, education=education or "Not given", level=level,
                           skills=skills, interests=interests or "Not given", tone=tone)
            results = {}
            bar = st.progress(0.0, text="Starting...")
            for i, t in enumerate(types):
                bar.progress(i / len(types), text=f"Writing {t} ({i + 1} of {len(types)})...")
                try:
                    results[t] = generate(build_prompt(profile, t), get_api_key(), model_choice)
                    save(name, role, t, results[t])
                except Exception as e:
                    results[t] = f"⚠️ Could not generate: {e}"
            bar.progress(1.0, text="Done")
            time.sleep(0.4)
            bar.empty()
            st.session_state["results"] = (name, role, results)

    if "results" in st.session_state:
        n, r, results = st.session_state["results"]
        st.markdown(f"## Content for {n}")
        st.caption(f"Target role: {r}")
        for t, tab in zip(results, st.tabs([f"{TASK_INFO[k][0]} {k}" for k in results])):
            with tab:
                st.markdown(results[t])
                with st.expander("Copy as text"):
                    st.code(results[t], language="markdown")
        st.download_button("⬇️ Download all as Word (.docx)", to_docx(n, r, results),
                           file_name=f"{n.replace(' ', '_')}_career_content.docx",
                           type="primary")


def page_history():
    st.markdown("# History")
    rows = load_history()
    if not rows:
        st.markdown(f'<div class="empty">{svg_img(EMPTY_SVG, alt="Empty history")}</div>', unsafe_allow_html=True)
        st.info("Nothing saved yet. Create your first piece on the Create page.")
        return

    f1, f2, f3 = st.columns([2, 2, 1])
    search = f1.text_input("Search", placeholder="Name or role", label_visibility="collapsed")
    kind = f2.selectbox("Type", ["All types"] + list(TASKS), label_visibility="collapsed")
    if f3.button("Clear all", use_container_width=True):
        clear_history()
        st.rerun()

    shown = [r for r in rows
             if (kind == "All types" or r[4] == kind)
             and (not search or search.lower() in f"{r[2]} {r[3]}".lower())]
    st.caption(f"{len(shown)} saved item(s)")
    if not shown:
        st.info("No items match your search.")

    for item_id, created, hname, hrole, htype, out in shown:
        icon = TASK_INFO.get(htype, ("📄",))[0]
        with st.expander(f"{icon} {htype} for {hname} ({hrole}), {created}"):
            st.markdown(out)
            b1, b2, _ = st.columns([1, 1, 3])
            b1.download_button("Download .txt", out, file_name=f"{htype.replace(' ', '_')}_{item_id}.txt",
                               key=f"dl{item_id}")
            if b2.button("Delete", key=f"del{item_id}"):
                delete_item(item_id)
                st.rerun()


def chart_style(chart, height=260):
    return (chart.properties(height=height, background="#FFFFFF")
            .configure_axis(labelColor="#16263A", titleColor="#16263A", gridColor="#E6E2D6",
                            domainColor="#8A97A8", tickColor="#8A97A8", labelFontSize=12, titleFontSize=12)
            .configure_view(strokeWidth=0))


def page_dashboard():
    st.markdown("# Dashboard")
    with db() as conn:
        rows = conn.execute("SELECT created, name, role, content_type, output FROM history").fetchall()
    if not rows:
        st.markdown(f'<div class="empty">{svg_img(EMPTY_SVG, alt="No data yet")}</div>', unsafe_allow_html=True)
        st.info("No data yet. Create some content and your charts will appear here.")
        return

    df = pd.DataFrame(rows, columns=["created", "name", "role", "type", "output"])
    df["day"] = pd.to_datetime(df["created"].str[:10])
    df["words"] = df["output"].str.split().str.len()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pieces created", len(df))
    m2.metric("People", df["name"].nunique())
    m3.metric("Target roles", df["role"].str.lower().nunique())
    m4.metric("Avg. length", f"{int(df['words'].mean())} words")
    st.write("")

    palette = alt.Scale(domain=list(_ICON_COLORS), range=list(_ICON_COLORS.values()))

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("#### What you create most")
            by_type = df.groupby("type").size().reset_index(name="count")
            ch = alt.Chart(by_type).mark_bar(cornerRadiusEnd=6).encode(
                y=alt.Y("type:N", sort="-x", title=None), x=alt.X("count:Q", title="Pieces", axis=alt.Axis(tickMinStep=1)),
                color=alt.Color("type:N", scale=palette, legend=None), tooltip=["type", "count"])
            st.altair_chart(chart_style(ch), use_container_width=True, theme=None)
    with c2:
        with st.container(border=True):
            st.markdown("#### Activity by day")
            by_day = df.groupby("day").size().reset_index(name="count")
            ch = alt.Chart(by_day).mark_area(line={"color": "#0E8F80", "strokeWidth": 3}, color="#BFE6E0",
                                             point={"color": "#0E8F80", "size": 70}).encode(
                x=alt.X("day:T", title=None, axis=alt.Axis(format="%d %b")),
                y=alt.Y("count:Q", title="Pieces", axis=alt.Axis(tickMinStep=1)),
                tooltip=[alt.Tooltip("day:T", format="%d %b %Y"), "count"])
            st.altair_chart(chart_style(ch), use_container_width=True, theme=None)

    c3, c4 = st.columns(2)
    with c3:
        with st.container(border=True):
            st.markdown("#### Most targeted roles")
            df["role_clean"] = df["role"].str.strip().str.title()
            roles = df.groupby("role_clean").size().reset_index(name="count").nlargest(8, "count")
            ch = alt.Chart(roles).mark_bar(cornerRadiusEnd=6, color="#F2A93B").encode(
                y=alt.Y("role_clean:N", sort="-x", title=None), x=alt.X("count:Q", title="Pieces", axis=alt.Axis(tickMinStep=1)),
                tooltip=["role_clean", "count"])
            st.altair_chart(chart_style(ch), use_container_width=True, theme=None)
    with c4:
        with st.container(border=True):
            st.markdown("#### Share of content types")
            ch = alt.Chart(by_type).mark_arc(innerRadius=60, outerRadius=105, stroke="#fff", strokeWidth=2).encode(
                theta="count:Q", color=alt.Color("type:N", scale=palette,
                                                 legend=alt.Legend(title=None, labelColor="#16263A", labelFontSize=12)),
                tooltip=["type", "count"])
            st.altair_chart(chart_style(ch), use_container_width=True, theme=None)

# ---------------------------------------------------------------- 8. NAVIGATION
home_page = st.Page(page_home, title="Home", icon="🏠", url_path="home", default=True)
gen_page = st.Page(page_generate, title="Create", icon="✨", url_path="create")
dash_page = st.Page(page_dashboard, title="Dashboard", icon="📊", url_path="dashboard")
hist_page = st.Page(page_history, title="History", icon="🕘", url_path="history")

pg = st.navigation([home_page, gen_page, dash_page, hist_page])
pg.run()

import csv
import html
import io
import math
import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import streamlit as st


# =============================================================================
# Page setup
# =============================================================================
st.set_page_config(
    page_title="Simple Local SEO Report",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        :root {
            --bg: #f6f8fb;
            --card: #ffffff;
            --ink: #102033;
            --muted: #667085;
            --line: #dce5ef;
            --blue: #174c78;
            --blue2: #0f3658;
            --soft-blue: #e9f3ff;
            --green: #0f7a55;
            --soft-green: #eaf8f1;
            --orange: #b45309;
            --soft-orange: #fff5e6;
            --red: #b42318;
            --soft-red: #fff0ef;
        }

        .stApp {
            background: var(--bg) !important;
            color: var(--ink) !important;
        }

        [data-testid="stHeader"] {
            background: transparent !important;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2.2rem;
            padding-bottom: 4rem;
        }

        /* Keep the sidebar readable even if Streamlit is in dark mode. */
        [data-testid="stSidebar"] {
            background: #ffffff !important;
            border-right: 1px solid var(--line) !important;
        }
        [data-testid="stSidebar"] *:not(svg):not(path) {
            color: var(--ink) !important;
        }
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background: #ffffff !important;
            color: var(--ink) !important;
            border-color: #cbd5e1 !important;
        }

        h1, h2, h3, p, label, span {
            color: inherit;
        }

        .topbar {
            background: linear-gradient(135deg, var(--blue2), var(--blue));
            color: white;
            border-radius: 24px;
            padding: 30px 32px;
            margin-bottom: 20px;
            box-shadow: 0 18px 45px rgba(15,54,88,.14);
        }
        .topbar h1 {
            color: white;
            font-size: 36px;
            line-height: 1.05;
            letter-spacing: -0.04em;
            margin: 0 0 10px 0;
            font-weight: 850;
        }
        .topbar p {
            color: rgba(255,255,255,.86);
            font-size: 16px;
            line-height: 1.55;
            margin: 0;
            max-width: 920px;
        }

        .tiny {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.45;
        }

        .section {
            margin-top: 28px;
            margin-bottom: 12px;
        }
        .section h2 {
            color: var(--ink);
            font-size: 25px;
            line-height: 1.15;
            letter-spacing: -0.03em;
            margin: 0 0 6px 0;
            font-weight: 850;
        }
        .section p {
            color: var(--muted);
            margin: 0;
            font-size: 14px;
            line-height: 1.5;
        }

        .quick-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
            margin: 15px 0 8px 0;
        }
        @media (max-width: 900px) {
            .quick-grid { grid-template-columns: 1fr; }
        }
        .quick-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 18px 18px 16px 18px;
            box-shadow: 0 10px 26px rgba(16, 32, 51, .055);
            min-height: 172px;
        }
        .quick-card .number {
            width: 32px;
            height: 32px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: var(--soft-blue);
            color: var(--blue);
            font-weight: 850;
            margin-bottom: 12px;
        }
        .quick-card h3 {
            color: var(--ink);
            font-size: 17px;
            line-height: 1.22;
            margin: 0 0 8px 0;
            font-weight: 850;
        }
        .quick-card p {
            color: #475467;
            margin: 0;
            font-size: 14px;
            line-height: 1.45;
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: 800;
            white-space: nowrap;
            border: 1px solid transparent;
        }
        .pill-blue { background: var(--soft-blue); color: var(--blue); border-color: #cfe6ff; }
        .pill-green { background: var(--soft-green); color: var(--green); border-color: #cbefd9; }
        .pill-orange { background: var(--soft-orange); color: var(--orange); border-color: #fed7aa; }
        .pill-red { background: var(--soft-red); color: var(--red); border-color: #fecaca; }
        .pill-gray { background: #f2f4f7; color: #475467; border-color: #e4e7ec; }

        .metric-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin: 14px 0 4px 0;
        }
        @media (max-width: 900px) {
            .metric-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        .mini-metric {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 15px 16px;
            box-shadow: 0 8px 20px rgba(16, 32, 51, .04);
        }
        .mini-metric .label {
            color: var(--muted);
            font-size: 12px;
            font-weight: 750;
            text-transform: uppercase;
            letter-spacing: .04em;
            margin-bottom: 4px;
        }
        .mini-metric .value {
            color: var(--ink);
            font-size: 24px;
            font-weight: 900;
            letter-spacing: -.03em;
        }

        .search-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 16px 18px;
            margin-bottom: 10px;
            box-shadow: 0 8px 20px rgba(16, 32, 51, .04);
        }
        .search-head {
            display: grid;
            grid-template-columns: 230px minmax(150px, 1fr) 120px;
            gap: 14px;
            align-items: center;
        }
        @media (max-width: 900px) {
            .search-head { grid-template-columns: 1fr; gap: 8px; }
        }
        .search-label {
            color: var(--ink);
            font-weight: 850;
            font-size: 15px;
        }
        .bar-track {
            height: 13px;
            background: #eef3f8;
            border-radius: 999px;
            overflow: hidden;
            border: 1px solid #e5edf5;
        }
        .bar-fill {
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, #5aaeea, #174c78);
        }
        .search-volume {
            color: var(--ink);
            text-align: right;
            font-weight: 850;
            font-size: 15px;
        }
        @media (max-width: 900px) {
            .search-volume { text-align: left; }
        }
        .examples {
            color: var(--muted);
            font-size: 13px;
            margin-top: 8px;
            line-height: 1.45;
        }

        .page-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 22px;
            overflow: hidden;
            box-shadow: 0 10px 26px rgba(16, 32, 51, .055);
            margin-bottom: 16px;
        }
        .page-header {
            background: var(--blue);
            color: white;
            padding: 14px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
        }
        .page-header strong {
            color: white;
            font-size: 16px;
            line-height: 1.25;
        }
        .page-body {
            padding: 18px;
        }
        .url {
            color: var(--muted);
            font-size: 13px;
            word-break: break-all;
            margin-bottom: 8px;
        }
        .title-line {
            color: var(--blue2);
            font-weight: 850;
            font-size: 18px;
            margin-bottom: 6px;
            line-height: 1.25;
        }
        .desc {
            color: #475467;
            font-size: 14px;
            line-height: 1.5;
            margin-bottom: 12px;
        }
        .badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0 12px 0;
        }
        .keyword-list {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
        }
        @media (max-width: 900px) {
            .keyword-list { grid-template-columns: 1fr; }
        }
        .kw-item {
            border: 1px solid #e8eef5;
            border-radius: 14px;
            padding: 9px 11px;
            background: #fbfdff;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
        }
        .kw-item .kw {
            color: var(--ink);
            font-size: 13px;
            font-weight: 750;
            line-height: 1.25;
        }
        .kw-item .vol {
            color: var(--blue);
            font-size: 13px;
            font-weight: 900;
            white-space: nowrap;
        }

        .empty-box {
            background: #ffffff;
            border: 1px dashed #b9c7d6;
            border-radius: 20px;
            padding: 24px;
            color: #475467;
        }

        .footer-note {
            margin-top: 26px;
            color: var(--muted);
            font-size: 12px;
            line-height: 1.45;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Helpers
# =============================================================================
def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def short_text(value, limit=150) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def clean_cell(value) -> str:
    value = str(value or "").strip()
    value = value.replace("&amp;", "&")
    if value.startswith('="') and value.endswith('"'):
        value = value[2:-1]
    if value.startswith("="):
        value = value[1:]
    value = value.strip('"')
    return value.strip()


def to_int(value) -> int:
    value = clean_cell(value).replace(",", "")
    try:
        return int(float(value))
    except Exception:
        return 0


def to_float(value) -> float:
    value = clean_cell(value).replace("$", "").replace(",", "")
    try:
        return float(value)
    except Exception:
        return 0.0


def split_terms(value: str):
    return [t.strip().lower() for t in str(value or "").split(",") if t.strip()]


def contains_any(text, terms) -> bool:
    text = f" {str(text or '').lower()} "
    return any(term and term in text for term in terms)


def parse_base_url(project_name: str) -> str:
    match = re.search(r"https?://[^\s,]+", str(project_name or ""))
    if match:
        return match.group(0).rstrip("/") + "/"
    return ""


def full_url(base_url: str, url: str) -> str:
    url = clean_cell(url)
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if base_url:
        return urljoin(base_url, url)
    return url


def token_set(text):
    return {t for t in re.findall(r"[a-z0-9']+", str(text or "").lower()) if len(t) > 2}


def phrase_aligned(row) -> bool:
    keyword = str(row.get("Keyword", "")).lower().strip()
    title = str(row.get("Title", "")).lower()
    h1 = str(row.get("H1", "")).lower()
    url = str(row.get("URL", "")).lower().replace("-", " ").replace("/", " ")
    desc = str(row.get("Description", "")).lower()

    explicit_title = str(row.get("inTitle", "")).strip().lower() not in {"", "0", "no", "false", "none", "-"}
    explicit_url = str(row.get("inURL", "")).strip().lower() not in {"", "0", "no", "false", "none", "-"}
    if explicit_title or explicit_url:
        return True

    page_text = " ".join([title, h1, url, desc])
    if keyword and keyword in page_text:
        return True

    kw_tokens = token_set(keyword)
    page_tokens = token_set(page_text)
    if not kw_tokens:
        return False
    overlap = len(kw_tokens & page_tokens) / max(len(kw_tokens), 1)
    return overlap >= 0.55


def length_pill(label, length, low, high):
    if length < low:
        return f'<span class="pill pill-orange">{esc(label)} short · {length}</span>'
    if length > high:
        return f'<span class="pill pill-orange">{esc(label)} long · {length}</span>'
    return f'<span class="pill pill-green">{esc(label)} good · {length}</span>'


@st.cache_data(show_spinner=False)
def parse_audit_csv(raw_bytes):
    if hasattr(raw_bytes, "getvalue"):
        raw_bytes = raw_bytes.getvalue()
    if isinstance(raw_bytes, str):
        raw_bytes = raw_bytes.encode("utf-8")

    text = raw_bytes.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))

    project_name = ""
    pages = []
    keywords = []
    current_page = None
    reading_keywords = False
    page_id = 0

    for raw_row in rows:
        row = [clean_cell(c) for c in raw_row]
        if not row or not any(row):
            reading_keywords = False
            continue

        first = row[0]
        first_lower = first.lower()

        if first_lower == "project name" and len(row) > 1:
            project_name = row[1]
            continue

        if first_lower == "group":
            current_page = None
            reading_keywords = False
            continue

        is_page_row = (
            not reading_keywords
            and len(row) >= 5
            and (str(row[2]).startswith("/") or str(row[2]).startswith("http"))
        )
        if is_page_row:
            page_id += 1
            current_page = {
                "Page ID": page_id,
                "Group": row[0],
                "Title": row[1],
                "URL": row[2],
                "Description": row[3] if len(row) > 3 else "",
                "H1": row[4] if len(row) > 4 else "",
            }
            pages.append(current_page)
            continue

        if first_lower == "keyword":
            reading_keywords = True
            continue

        if reading_keywords and current_page:
            keyword = first.strip()
            if not keyword:
                continue
            keywords.append(
                {
                    "Page ID": current_page["Page ID"],
                    "Group": current_page["Group"],
                    "Title": current_page["Title"],
                    "URL": current_page["URL"],
                    "Description": current_page["Description"],
                    "H1": current_page["H1"],
                    "Keyword": keyword,
                    "Volume": to_int(row[1]) if len(row) > 1 else 0,
                    "CPC": to_float(row[2]) if len(row) > 2 else 0.0,
                    "inTitle": row[3] if len(row) > 3 else "",
                    "inURL": row[4] if len(row) > 4 else "",
                    "Rank": row[5] if len(row) > 5 else "",
                }
            )

    return project_name, pd.DataFrame(pages), pd.DataFrame(keywords)


def classify_customer_search(keyword: str, brand_terms) -> str:
    kw = str(keyword or "").lower()
    if contains_any(kw, brand_terms):
        return "Brand searches"
    if any(t in kw for t in ["menu", "special", "happy hour", "price", "prices", "order", "online ordering"]):
        return "Menu & specials"
    if any(t in kw for t in ["near me", "nearby", "restaurant", "restaurants", "bar", "bars", "pub", "grill", "loves park", "rockford", "machesney", "franklin", "cool springs"]):
        return "Nearby restaurants & bars"
    if any(t in kw for t in ["burger", "pizza", "sandwich", "fish fry", "wings", "beer", "brunch", "lunch", "dinner", "food", "drink", "drinks"]):
        return "Food & drinks"
    if any(t in kw for t in ["event", "events", "party", "parties", "catering", "private", "banquet", "birthday", "room", "rehearsal"]):
        return "Events & private parties"
    if any(t in kw for t in ["hour", "hours", "open", "closed", "address", "phone", "contact", "directions", "location"]):
        return "Hours & contact"
    if any(t in kw for t in ["review", "reviews", "photo", "photos", "pictures"]):
        return "Reviews & photos"
    return "Other searches"


def action_for(row) -> str:
    if row.get("Is noise", False):
        return "Ignore"
    if row.get("Is brand", False):
        return "Protect brand page"
    if row.get("Aligned", False):
        return "Already covered"
    bucket = row.get("Customer search", "")
    if bucket == "Menu & specials":
        return "Improve menu page"
    if bucket == "Nearby restaurants & bars":
        return "Add local wording"
    if bucket == "Events & private parties":
        return "Add event/private party info"
    if bucket == "Hours & contact":
        return "Fix contact/hours info"
    if bucket == "Food & drinks":
        return "Add food/drink wording"
    return "Add this phrase clearly"


def enrich_keywords(keywords_df, brand_terms, noise_terms):
    if keywords_df.empty:
        return keywords_df.copy()
    df = keywords_df.copy()
    df["Keyword lower"] = df["Keyword"].astype(str).str.lower()
    df["Is brand"] = df["Keyword lower"].apply(lambda x: contains_any(x, brand_terms))
    df["Is noise"] = df["Keyword lower"].apply(lambda x: contains_any(x, noise_terms))
    df["Customer search"] = df["Keyword"].apply(lambda x: classify_customer_search(x, brand_terms))
    df["Aligned"] = df.apply(phrase_aligned, axis=1)
    df["Action"] = df.apply(action_for, axis=1)
    df["Needs work"] = (~df["Aligned"]) & (~df["Is brand"]) & (~df["Is noise"])
    df["Priority"] = (
        df["Volume"].clip(lower=0).apply(lambda x: math.sqrt(x))
        * (1 + df["CPC"].clip(lower=0).clip(upper=5) / 6)
        * df["Needs work"].apply(lambda x: 1.5 if x else 0.65)
        * df["Is noise"].apply(lambda x: 0.05 if x else 1.0)
    )
    return df


def page_summary(pages_df, kw_df):
    if pages_df.empty:
        return pd.DataFrame()
    if kw_df.empty:
        df = pages_df.copy()
        df["Good volume"] = 0
        df["Gap volume"] = 0
        df["Brand volume"] = 0
        df["Keywords"] = 0
        return df

    agg = kw_df.groupby("Page ID").agg(
        **{
            "Good volume": ("Volume", lambda s: int(s[kw_df.loc[s.index, "Is noise"].eq(False)].sum())),
            "Gap volume": ("Volume", lambda s: int(s[kw_df.loc[s.index, "Needs work"].eq(True)].sum())),
            "Brand volume": ("Volume", lambda s: int(s[kw_df.loc[s.index, "Is brand"].eq(True)].sum())),
            "Keywords": ("Keyword", "count"),
        }
    ).reset_index()
    return pages_df.merge(agg, on="Page ID", how="left").fillna({"Good volume": 0, "Gap volume": 0, "Brand volume": 0, "Keywords": 0})


def fmt_num(value) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except Exception:
        return "0"


def first_value(df, col, default=""):
    if df.empty or col not in df:
        return default
    value = df.iloc[0][col]
    return default if pd.isna(value) else value


def find_local_csvs(folder, recursive=False, limit=300):
    folder_path = Path(str(folder or ".")).expanduser()
    if not folder_path.exists() or not folder_path.is_dir():
        return []
    pattern = "**/*.csv" if recursive else "*.csv"
    files = sorted(folder_path.glob(pattern), key=lambda p: p.name.lower())
    return files[:limit]


def load_csv_source():
    st.sidebar.title("CSV file")
    source = st.sidebar.radio(
        "Choose source",
        ["Upload CSV", "Open CSV from local folder"],
        label_visibility="collapsed",
    )

    raw_bytes = None
    filename = None

    if source == "Upload CSV":
        uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
        if uploaded is not None:
            raw_bytes = uploaded.getvalue()
            filename = uploaded.name
    else:
        folder = st.sidebar.text_input("Folder path", value=".")
        recursive = st.sidebar.checkbox("Include subfolders", value=False)
        files = find_local_csvs(folder, recursive=recursive)
        if files:
            labels = [str(p) for p in files]
            selected = st.sidebar.selectbox("CSV file", labels)
            if selected:
                path = Path(selected)
                raw_bytes = path.read_bytes()
                filename = path.name
        else:
            st.sidebar.info("No CSV files found in that folder.")

    return raw_bytes, filename


def render_metric_row(pages_df, kw_df, visible_kw):
    html_out = f"""
    <div class="metric-row">
        <div class="mini-metric"><div class="label">Pages</div><div class="value">{fmt_num(len(pages_df))}</div></div>
        <div class="mini-metric"><div class="label">Keywords</div><div class="value">{fmt_num(len(visible_kw))}</div></div>
        <div class="mini-metric"><div class="label">Searches / month</div><div class="value">{fmt_num(visible_kw['Volume'].sum() if not visible_kw.empty else 0)}</div></div>
        <div class="mini-metric"><div class="label">Need attention</div><div class="value">{fmt_num(visible_kw['Needs work'].sum() if 'Needs work' in visible_kw else 0)}</div></div>
    </div>
    """
    st.markdown(html_out, unsafe_allow_html=True)


def render_quick_cards(summary_df, visible_kw):
    work_kw = visible_kw[visible_kw["Needs work"]].sort_values(["Volume", "Priority"], ascending=False) if not visible_kw.empty else pd.DataFrame()
    top_page = summary_df.sort_values("Gap volume", ascending=False).head(1) if not summary_df.empty else pd.DataFrame()
    top_bucket = (
        visible_kw[~visible_kw["Is brand"]]
        .groupby("Customer search")["Volume"]
        .sum()
        .sort_values(ascending=False)
        .head(1)
        if not visible_kw.empty else pd.Series(dtype=int)
    )

    page_name = first_value(top_page, "Group", "No page found")
    page_gap = first_value(top_page, "Gap volume", 0)
    phrase = first_value(work_kw, "Keyword", "No obvious missing keyword")
    phrase_vol = first_value(work_kw, "Volume", 0)
    phrase_page = first_value(work_kw, "Group", "")
    bucket_name = top_bucket.index[0] if len(top_bucket) else "No clear bucket"
    bucket_vol = top_bucket.iloc[0] if len(top_bucket) else 0

    cards = f"""
    <div class="quick-grid">
        <div class="quick-card">
            <div class="number">1</div>
            <h3>Fix this page first</h3>
            <p><b>{esc(short_text(page_name, 70))}</b></p>
            <p>This page has the biggest group of useful searches that are not clearly covered yet.</p>
            <div style="margin-top:12px;"><span class="pill pill-orange">{fmt_num(page_gap)} searches/mo</span></div>
        </div>
        <div class="quick-card">
            <div class="number">2</div>
            <h3>Add this phrase clearly</h3>
            <p><b>{esc(short_text(phrase, 70))}</b></p>
            <p>Use it naturally in the page title, H1, opening copy, or a short section on <b>{esc(short_text(phrase_page, 55))}</b>.</p>
            <div style="margin-top:12px;"><span class="pill pill-blue">{fmt_num(phrase_vol)} searches/mo</span></div>
        </div>
        <div class="quick-card">
            <div class="number">3</div>
            <h3>Lean into this customer need</h3>
            <p><b>{esc(bucket_name)}</b></p>
            <p>This is the biggest non-brand search pattern. Make sure your site answers it plainly.</p>
            <div style="margin-top:12px;"><span class="pill pill-green">{fmt_num(bucket_vol)} searches/mo</span></div>
        </div>
    </div>
    """
    st.markdown(cards, unsafe_allow_html=True)


def render_customer_searches(visible_kw):
    if visible_kw.empty:
        st.markdown('<div class="empty-box">No keywords to show.</div>', unsafe_allow_html=True)
        return

    bucket_order = [
        "Nearby restaurants & bars",
        "Menu & specials",
        "Food & drinks",
        "Events & private parties",
        "Hours & contact",
        "Reviews & photos",
        "Brand searches",
        "Other searches",
    ]
    grouped = visible_kw.groupby("Customer search").agg(
        Volume=("Volume", "sum"),
        Keywords=("Keyword", "count"),
    ).reset_index()
    grouped["sort"] = grouped["Customer search"].apply(lambda x: bucket_order.index(x) if x in bucket_order else 999)
    grouped = grouped.sort_values(["sort", "Volume"], ascending=[True, False])
    max_vol = max(float(grouped["Volume"].max()), 1.0)

    html_rows = []
    for _, row in grouped.iterrows():
        bucket = row["Customer search"]
        kws = visible_kw[visible_kw["Customer search"] == bucket].sort_values("Volume", ascending=False).head(4)
        examples = ", ".join(kws["Keyword"].astype(str).tolist())
        width = max(3, min(100, row["Volume"] / max_vol * 100))
        html_rows.append(
            f"""
            <div class="search-card">
                <div class="search-head">
                    <div class="search-label">{esc(bucket)}</div>
                    <div class="bar-track"><div class="bar-fill" style="width:{width:.1f}%"></div></div>
                    <div class="search-volume">{fmt_num(row['Volume'])}/mo</div>
                </div>
                <div class="examples">Examples: {esc(examples) if examples else '—'}</div>
            </div>
            """
        )
    st.markdown("\n".join(html_rows), unsafe_allow_html=True)


def page_status_pills(page, page_kw):
    title = str(page.get("Title", ""))
    desc = str(page.get("Description", ""))
    h1 = str(page.get("H1", ""))
    gap = int(page.get("Gap volume", 0) or 0)

    pills = [
        length_pill("Title", len(title), 25, 65),
        length_pill("Meta", len(desc), 70, 165),
        f'<span class="pill pill-green">H1 present</span>' if h1.strip() else f'<span class="pill pill-orange">H1 missing</span>',
    ]
    if gap > 0:
        pills.append(f'<span class="pill pill-orange">{fmt_num(gap)} searches not clearly covered</span>')
    else:
        pills.append(f'<span class="pill pill-green">Good keyword match</span>')
    return "".join(pills)


def render_page_cards(summary_df, visible_kw, base_url, max_pages=8):
    if summary_df.empty:
        st.markdown('<div class="empty-box">No pages found in this CSV.</div>', unsafe_allow_html=True)
        return

    summary_df = summary_df.copy()
    summary_df["sort_gap"] = summary_df["Gap volume"].astype(float)
    summary_df["sort_good"] = summary_df["Good volume"].astype(float)
    pages_to_show = summary_df.sort_values(["sort_gap", "sort_good"], ascending=False).head(max_pages)

    for _, page in pages_to_show.iterrows():
        page_kw = visible_kw[visible_kw["Page ID"] == page["Page ID"]].sort_values("Volume", ascending=False).head(8)
        url = full_url(base_url, page.get("URL", ""))
        action = "Fix first" if int(page.get("Gap volume", 0) or 0) > 0 else "Looks okay"
        action_class = "pill-orange" if action == "Fix first" else "pill-green"

        kw_html = []
        if page_kw.empty:
            kw_html.append('<div class="tiny">No visible keywords for this page after cleanup.</div>')
        else:
            for _, kw in page_kw.iterrows():
                kw_label = kw["Keyword"]
                vol = kw["Volume"]
                needs = bool(kw.get("Needs work", False))
                icon = "⚠️ " if needs else ""
                kw_html.append(
                    f"""
                    <div class="kw-item">
                        <div class="kw">{icon}{esc(short_text(kw_label, 60))}</div>
                        <div class="vol">{fmt_num(vol)}</div>
                    </div>
                    """
                )

        card = f"""
        <div class="page-card">
            <div class="page-header">
                <strong>{esc(short_text(page.get('Group', ''), 95))}</strong>
                <span class="pill {action_class}">{action}</span>
            </div>
            <div class="page-body">
                <div class="url">{esc(url)}</div>
                <div class="title-line">{esc(short_text(page.get('Title', ''), 110))}</div>
                <div class="desc">{esc(short_text(page.get('Description', ''), 220))}</div>
                <div class="badge-row">{page_status_pills(page, page_kw)}</div>
                <div class="keyword-list">{''.join(kw_html)}</div>
            </div>
        </div>
        """
        st.markdown(card, unsafe_allow_html=True)


def render_downloads(visible_kw, summary_df):
    with st.expander("Downloads / raw data", expanded=False):
        st.download_button(
            "Download cleaned keyword list",
            data=visible_kw.drop(columns=[c for c in ["Keyword lower"] if c in visible_kw.columns]).to_csv(index=False),
            file_name="cleaned_keywords.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.download_button(
            "Download page summary",
            data=summary_df.to_csv(index=False),
            file_name="page_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.dataframe(
            visible_kw[["Keyword", "Volume", "CPC", "Customer search", "Group", "Action"]].sort_values("Volume", ascending=False),
            use_container_width=True,
            hide_index=True,
        )


# =============================================================================
# App
# =============================================================================
raw_bytes, filename = load_csv_source()

with st.sidebar.expander("Cleanup", expanded=False):
    brand_text = st.text_area(
        "Brand terms",
        value="fozzy, fozzys, fozzy's, jax, jax pub",
        help="Comma-separated. These are searches from people already looking for the business.",
    )
    noise_text = st.text_area(
        "Competitor / junk terms",
        value="fuzzy, fuzzy's, foxys, foxy, weezy, boozies, fitzy, nunzio, woody, shazzy, hozy, gozzys, fazzi",
        help="Comma-separated. These are terms you probably do not want counted as real opportunity.",
    )
    hide_noise = st.checkbox("Hide competitor / junk terms", value=True)
    min_volume = st.slider("Minimum search volume", min_value=0, max_value=1000, value=0, step=10)
    max_pages = st.slider("Page cards to show", min_value=3, max_value=20, value=8, step=1)

brand_terms = split_terms(brand_text)
noise_terms = split_terms(noise_text)

if raw_bytes is None:
    st.markdown(
        """
        <div class="topbar">
            <h1>Simple Local SEO Report</h1>
            <p>Pick a CSV in the sidebar. The report will show only the basics: what to fix first, what customers search for, and which keywords belong on each page.</p>
        </div>
        <div class="empty-box">No CSV loaded yet.</div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

project_name, pages_df, keywords_df = parse_audit_csv(raw_bytes)
base_url = parse_base_url(project_name)

if keywords_df.empty or pages_df.empty:
    st.error("I could not find pages and keywords in this CSV. Make sure it uses the audit format with Group and Keyword sections.")
    st.stop()

enriched = enrich_keywords(keywords_df, brand_terms, noise_terms)
visible_kw = enriched.copy()
if hide_noise:
    visible_kw = visible_kw[~visible_kw["Is noise"]]
if min_volume:
    visible_kw = visible_kw[visible_kw["Volume"] >= min_volume]

summary_df = page_summary(pages_df, visible_kw)

project_label = project_name or filename or "Loaded CSV"
st.markdown(
    f"""
    <div class="topbar">
        <h1>Simple Local SEO Report</h1>
        <p><b>{esc(short_text(project_label, 110))}</b><br>This version avoids vanity charts. It answers the three things a local business owner actually needs to know.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_metric_row(pages_df, enriched, visible_kw)

st.markdown(
    """
    <div class="section">
        <h2>1. What should I fix first?</h2>
        <p>Three simple next steps. Start here before looking at the full keyword list.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
render_quick_cards(summary_df, visible_kw)

st.markdown(
    """
    <div class="section">
        <h2>2. What are people searching for?</h2>
        <p>Plain-English customer needs, not SEO jargon. The examples tell you what wording customers actually use.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
render_customer_searches(visible_kw)

st.markdown(
    """
    <div class="section">
        <h2>3. Which pages need which keywords?</h2>
        <p>Each card shows the page, basic title/meta checks, and the top keywords assigned to it. ⚠️ means the page does not clearly cover that phrase yet.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
render_page_cards(summary_df, visible_kw, base_url, max_pages=max_pages)

render_downloads(visible_kw, summary_df)

st.markdown(
    """
    <div class="footer-note">
        Note: This report uses the CSV's assigned keywords and search volume. It does not replace Google Search Console, but it is enough to decide what copy and pages to clean up first.
    </div>
    """,
    unsafe_allow_html=True,
)

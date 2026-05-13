import csv
import html
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st


# ==========================================================
# Page setup
# ==========================================================
st.set_page_config(
    page_title="SEO CSV Viewer",
    page_icon="📄",
    layout="wide",
)


# Tiny CSS only. No theme overrides, no broken dark/light fighting.
st.markdown(
    """
    <style>
    .small-muted { opacity: .68; font-size: .9rem; }
    .page-title { font-size: 1.05rem; font-weight: 700; margin-bottom: .15rem; }
    .url-pill {
        display: inline-block;
        padding: .18rem .5rem;
        border: 1px solid rgba(128,128,128,.28);
        border-radius: 999px;
        font-size: .82rem;
        opacity: .85;
        margin: .15rem 0 .45rem 0;
    }
    .label { font-size: .78rem; opacity: .62; text-transform: uppercase; letter-spacing: .04em; }
    .text-line { margin-bottom: .45rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==========================================================
# Helpers
# ==========================================================
def clean_cell(value: Any) -> str:
    """Clean cells exported as =\"123\" or =\"\" while preserving normal text."""
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    s = s.replace("&amp;", "&")
    return s.strip()


def to_int(value: Any) -> int:
    s = clean_cell(value)
    s = re.sub(r"[^0-9-]", "", s)
    try:
        return int(s)
    except Exception:
        return 0


def to_float(value: Any) -> float:
    s = clean_cell(value)
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return 0.0


def safe_text(value: Any) -> str:
    return html.escape(clean_cell(value))


@st.cache_data(show_spinner=False)
def parse_audit_csv_bytes(file_bytes: bytes) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """
    Parse the grouped SEO audit CSV format:

    Project Name,...
    Total Groups,...

    Group,Title,URL,DESC,H1,
    <group row>
    Keyword,Volume,CPC,inTITLE,inURL,<keyword-count>,
    <keyword rows>
    """
    text = file_bytes.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))

    metadata: Dict[str, str] = {}
    groups: List[Dict[str, Any]] = []
    i = 0

    while i < len(rows):
        row = rows[i]
        if not row or not any(clean_cell(c) for c in row):
            i += 1
            continue

        first = clean_cell(row[0])

        # Top metadata rows before the grouped report starts.
        if first != "Group" and len(row) > 1 and first and first != "Keyword":
            metadata[first] = clean_cell(row[1])
            i += 1
            continue

        if first == "Group":
            headers = [clean_cell(c) for c in row]
            page_row = rows[i + 1] if i + 1 < len(rows) else []

            group = {
                "group": clean_cell(page_row[0]) if len(page_row) > 0 else "",
                "title": clean_cell(page_row[1]) if len(page_row) > 1 else "",
                "url": clean_cell(page_row[2]) if len(page_row) > 2 else "",
                "description": clean_cell(page_row[3]) if len(page_row) > 3 else "",
                "h1": clean_cell(page_row[4]) if len(page_row) > 4 else "",
                "keyword_count_from_file": None,
                "keywords": [],
                "raw_group_headers": headers,
            }

            i += 2

            # Find the keyword header for this group.
            while i < len(rows):
                r = rows[i]
                if r and clean_cell(r[0]) == "Keyword":
                    if len(r) > 5 and clean_cell(r[5]).isdigit():
                        group["keyword_count_from_file"] = int(clean_cell(r[5]))
                    i += 1
                    break
                if r and clean_cell(r[0]) == "Group":
                    break
                i += 1

            # Read keyword rows until the next group.
            while i < len(rows):
                r = rows[i]
                if r and clean_cell(r[0]) == "Group":
                    break
                if r and any(clean_cell(c) for c in r):
                    kw = {
                        "Keyword": clean_cell(r[0]) if len(r) > 0 else "",
                        "Volume": to_int(r[1]) if len(r) > 1 else 0,
                        "CPC": to_float(r[2]) if len(r) > 2 else 0.0,
                        "inTITLE": clean_cell(r[3]) if len(r) > 3 else "",
                        "inURL": clean_cell(r[4]) if len(r) > 4 else "",
                    }
                    if kw["Keyword"]:
                        group["keywords"].append(kw)
                i += 1

            groups.append(group)
            continue

        i += 1

    return metadata, groups


def group_to_keywords_df(groups: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for idx, group in enumerate(groups, start=1):
        for kw in group["keywords"]:
            rows.append(
                {
                    "Page #": idx,
                    "Group": group["group"],
                    "Title": group["title"],
                    "URL": group["url"],
                    "Keyword": kw["Keyword"],
                    "Volume": kw["Volume"],
                    "CPC": kw["CPC"],
                    "inTITLE": kw["inTITLE"],
                    "inURL": kw["inURL"],
                }
            )
    return pd.DataFrame(rows)


def page_summary_df(groups: List[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for idx, group in enumerate(groups, start=1):
        kws = group["keywords"]
        total_volume = sum(k["Volume"] for k in kws)
        top_keyword = max(kws, key=lambda k: k["Volume"], default={"Keyword": "", "Volume": 0})
        rows.append(
            {
                "#": idx,
                "Group": group["group"],
                "URL": group["url"],
                "Keywords": len(kws),
                "Total Volume": total_volume,
                "Top Keyword": top_keyword.get("Keyword", ""),
                "Top Keyword Volume": top_keyword.get("Volume", 0),
            }
        )
    return pd.DataFrame(rows)


def load_local_csv_bytes(folder: str, filename: str) -> bytes:
    path = Path(folder).expanduser().resolve() / filename
    return path.read_bytes()


def find_csv_files(folder: str, include_subfolders: bool) -> List[str]:
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return []
    pattern = "**/*.csv" if include_subfolders else "*.csv"
    files = sorted(root.glob(pattern), key=lambda p: str(p).lower())
    return [str(p.relative_to(root)) for p in files]


def render_text_field(label: str, value: str) -> None:
    st.markdown(
        f"<div class='label'>{html.escape(label)}</div>"
        f"<div class='text-line'>{safe_text(value) or '—'}</div>",
        unsafe_allow_html=True,
    )


def render_group_card(group: Dict[str, Any], number: int, rows_to_show: int, sort_keywords: str) -> None:
    keywords = pd.DataFrame(group["keywords"])
    if not keywords.empty:
        if sort_keywords == "Highest volume first":
            keywords = keywords.sort_values("Volume", ascending=False)
        elif sort_keywords == "Highest CPC first":
            keywords = keywords.sort_values("CPC", ascending=False)
        keywords = keywords.head(rows_to_show)

    with st.container(border=True):
        title = group["group"] or group["title"] or f"Page {number}"
        st.markdown(f"<div class='page-title'>{number}. {safe_text(title)}</div>", unsafe_allow_html=True)
        st.markdown(f"<span class='url-pill'>{safe_text(group['url']) or 'No URL'}</span>", unsafe_allow_html=True)

        left, right = st.columns([2, 1])
        with left:
            render_text_field("Title", group["title"])
            render_text_field("H1", group["h1"])
            render_text_field("Description", group["description"])
        with right:
            st.metric("Keywords", f"{len(group['keywords']):,}")
            st.metric("Total Volume", f"{sum(k['Volume'] for k in group['keywords']):,}")
            if group.get("keyword_count_from_file") is not None:
                st.caption(f"Keyword count in file header: {group['keyword_count_from_file']:,}")

        st.dataframe(
            keywords,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Volume": st.column_config.NumberColumn("Volume", format="%d"),
                "CPC": st.column_config.NumberColumn("CPC", format="$%.2f"),
            },
        )


# ==========================================================
# Sidebar: CSV source
# ==========================================================
st.sidebar.title("CSV file")
source = st.sidebar.radio("Choose source", ["Upload CSV", "Open CSV from local folder"], horizontal=False)

file_bytes = None
source_name = None

if source == "Upload CSV":
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        source_name = uploaded.name
else:
    folder = st.sidebar.text_input("Folder path", value=str(Path.cwd()))
    include_subfolders = st.sidebar.checkbox("Include subfolders", value=False)
    csv_files = find_csv_files(folder, include_subfolders)
    if not csv_files:
        st.sidebar.info("No CSV files found in that folder.")
    else:
        selected_file = st.sidebar.selectbox("Select CSV", csv_files)
        if selected_file:
            try:
                file_bytes = load_local_csv_bytes(folder, selected_file)
                source_name = selected_file
            except Exception as exc:
                st.sidebar.error(f"Could not open file: {exc}")


# ==========================================================
# Main app
# ==========================================================
st.title("SEO CSV Viewer")
st.caption("A clean view of the data in your SEO audit CSV. No extra scoring, no invented recommendations.")

if file_bytes is None:
    st.info("Upload a CSV or choose one from a local folder to begin.")
    st.stop()

try:
    metadata, groups = parse_audit_csv_bytes(file_bytes)
except Exception as exc:
    st.error(f"Could not parse this CSV: {exc}")
    st.stop()

if not groups:
    st.warning("No grouped SEO data was found in this CSV.")
    st.stop()

all_keywords = group_to_keywords_df(groups)
pages = page_summary_df(groups)

# Header summary
st.subheader(source_name or "Loaded CSV")
if metadata:
    meta_text = "  ·  ".join(f"{k}: {v}" for k, v in metadata.items() if v)
    if meta_text:
        st.caption(meta_text)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pages", f"{len(groups):,}")
c2.metric("Keywords", f"{len(all_keywords):,}")
c3.metric("Total Volume", f"{int(all_keywords['Volume'].sum()):,}" if not all_keywords.empty else "0")
c4.metric("Avg CPC", f"${all_keywords['CPC'].mean():.2f}" if not all_keywords.empty else "$0.00")

st.divider()

# Simple controls
left, middle, right = st.columns([2, 1, 1])
with left:
    search = st.text_input("Search keyword, page, URL, title, H1, or description", value="")
with middle:
    sort_pages = st.selectbox("Sort pages", ["CSV order", "Highest total volume", "Most keywords"], index=0)
with right:
    rows_to_show = st.number_input("Rows per page", min_value=5, max_value=200, value=20, step=5)

sort_keywords = st.radio(
    "Keyword order inside each page",
    ["CSV order", "Highest volume first", "Highest CPC first"],
    horizontal=True,
)

# Filter groups by search text.
visible_groups = groups
if search.strip():
    q = search.strip().lower()
    filtered = []
    for g in groups:
        haystack = " ".join(
            [
                g.get("group", ""),
                g.get("title", ""),
                g.get("url", ""),
                g.get("description", ""),
                g.get("h1", ""),
                " ".join(k.get("Keyword", "") for k in g.get("keywords", [])),
            ]
        ).lower()
        if q in haystack:
            filtered.append(g)
    visible_groups = filtered

if sort_pages == "Highest total volume":
    visible_groups = sorted(visible_groups, key=lambda g: sum(k["Volume"] for k in g["keywords"]), reverse=True)
elif sort_pages == "Most keywords":
    visible_groups = sorted(visible_groups, key=lambda g: len(g["keywords"]), reverse=True)

# Overview table: actual CSV groups summarized.
st.subheader("Pages in this file")
st.dataframe(
    pages,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Total Volume": st.column_config.NumberColumn("Total Volume", format="%d"),
        "Top Keyword Volume": st.column_config.NumberColumn("Top Keyword Volume", format="%d"),
    },
)

st.divider()

st.subheader("Page details")
if not visible_groups:
    st.warning("No pages match your search.")
else:
    for idx, group in enumerate(visible_groups, start=1):
        original_number = groups.index(group) + 1
        render_group_card(group, original_number, int(rows_to_show), sort_keywords)

with st.expander("All keywords as one table"):
    keyword_view = all_keywords.copy()
    if search.strip():
        q = search.strip().lower()
        mask = keyword_view.astype(str).apply(lambda col: col.str.lower().str.contains(q, na=False)).any(axis=1)
        keyword_view = keyword_view[mask]
    st.dataframe(
        keyword_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Volume": st.column_config.NumberColumn("Volume", format="%d"),
            "CPC": st.column_config.NumberColumn("CPC", format="$%.2f"),
        },
    )
    st.download_button(
        "Download visible keywords as CSV",
        data=keyword_view.to_csv(index=False).encode("utf-8"),
        file_name="seo_keywords_view.csv",
        mime="text/csv",
    )

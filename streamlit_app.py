import csv
import html
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st


st.set_page_config(
    page_title="SEO CSV Report",
    page_icon="📄",
    layout="wide",
)


# -----------------------------
# Helpers
# -----------------------------
def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith('="') and text.endswith('"'):
        text = text[2:-1]
    return html.unescape(text).strip()


def esc(value: Any) -> str:
    return html.escape(clean_cell(value), quote=True)


def to_int(value: Any) -> int:
    text = clean_cell(value)
    text = re.sub(r"[^0-9-]", "", text)
    try:
        return int(text)
    except Exception:
        return 0


def to_float(value: Any) -> float:
    text = clean_cell(value)
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text)
    except Exception:
        return 0.0


def pretty_int(value: Any) -> str:
    return f"{to_int(value):,}"


def pretty_money(value: Any) -> str:
    return f"${to_float(value):.2f}"


def yes_no(value: Any) -> str:
    text = clean_cell(value).lower()
    if text in {"", "-", "0", "no", "false", "n"}:
        return "—"
    return "✓"


def length_class(current: int, limit: int) -> str:
    if current == 0:
        return "muted"
    if current > limit:
        return "bad"
    return "good"


# -----------------------------
# CSV parser
# -----------------------------
@st.cache_data(show_spinner=False)
def parse_grouped_csv(file_bytes: bytes) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
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

        if first not in {"Group", "Keyword"} and len(row) > 1:
            metadata[first] = clean_cell(row[1])
            i += 1
            continue

        if first != "Group":
            i += 1
            continue

        group_headers = [clean_cell(c) for c in row]
        page_row = rows[i + 1] if i + 1 < len(rows) else []
        page_data: Dict[str, str] = {}

        for col_index, header in enumerate(group_headers):
            if header:
                page_data[header] = clean_cell(page_row[col_index]) if col_index < len(page_row) else ""

        group: Dict[str, Any] = {
            "group": page_data.get("Group", ""),
            "title": page_data.get("Title", ""),
            "url": page_data.get("URL", ""),
            "description": page_data.get("DESC", page_data.get("Description", "")),
            "h1": page_data.get("H1", ""),
            "page_data": page_data,
            "keyword_headers": [],
            "keyword_count_from_file": None,
            "keywords": [],
        }

        i += 2

        # Find keyword header row for this group.
        while i < len(rows):
            current = rows[i]
            if current and clean_cell(current[0]) == "Keyword":
                headers: List[str] = []
                for item in current:
                    value = clean_cell(item)
                    if not value:
                        continue
                    if value.isdigit():
                        group["keyword_count_from_file"] = int(value)
                    else:
                        headers.append(value)
                group["keyword_headers"] = headers or ["Keyword", "Volume", "CPC", "inTITLE", "inURL"]
                i += 1
                break
            if current and clean_cell(current[0]) == "Group":
                break
            i += 1

        headers = group["keyword_headers"] or ["Keyword", "Volume", "CPC", "inTITLE", "inURL"]

        while i < len(rows):
            current = rows[i]
            if current and clean_cell(current[0]) == "Group":
                break
            if current and any(clean_cell(c) for c in current):
                keyword: Dict[str, Any] = {}
                for col_index, header in enumerate(headers):
                    keyword[header] = clean_cell(current[col_index]) if col_index < len(current) else ""
                if clean_cell(keyword.get("Keyword")):
                    keyword["Volume_num"] = to_int(keyword.get("Volume"))
                    keyword["CPC_num"] = to_float(keyword.get("CPC"))
                    group["keywords"].append(keyword)
            i += 1

        groups.append(group)

    return metadata, groups


# -----------------------------
# File loading
# -----------------------------
def get_csv_bytes() -> Tuple[bytes | None, str]:
    st.sidebar.header("CSV file")
    source = st.sidebar.radio(
        "Choose source",
        ["Upload CSV", "Open CSV from local folder"],
        label_visibility="collapsed",
    )

    if source == "Upload CSV":
        uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
        if uploaded is None:
            return None, ""
        return uploaded.getvalue(), uploaded.name

    folder = st.sidebar.text_input("Folder path", value=".")
    include_subfolders = st.sidebar.checkbox("Include subfolders", value=False)

    folder_path = Path(folder).expanduser()
    if not folder_path.exists() or not folder_path.is_dir():
        st.sidebar.error("Folder not found.")
        return None, ""

    pattern = "**/*.csv" if include_subfolders else "*.csv"
    files = sorted(folder_path.glob(pattern), key=lambda p: str(p).lower())
    if not files:
        st.sidebar.warning("No CSV files found in this folder.")
        return None, ""

    labels = [str(p.relative_to(folder_path)) for p in files]
    selected = st.sidebar.selectbox("CSV file", labels)
    selected_path = files[labels.index(selected)]

    try:
        return selected_path.read_bytes(), selected_path.name
    except Exception as exc:
        st.sidebar.error(f"Could not read this file: {exc}")
        return None, ""


# -----------------------------
# Rendering
# -----------------------------
def keyword_visible(keyword: Dict[str, Any], hide_zero_cpc: bool, hide_under_50: bool) -> bool:
    if hide_zero_cpc and to_float(keyword.get("CPC", keyword.get("CPC_num", 0))) <= 0:
        return False
    if hide_under_50 and to_int(keyword.get("Volume", keyword.get("Volume_num", 0))) < 50:
        return False
    return True


def metric_pill(label: str, current: int, limit: int) -> str:
    klass = length_class(current, limit)
    return f'<div class="metric-pill {klass}"><span>{html.escape(label)}</span><strong>{current}/{limit}</strong></div>'


def keyword_table(group: Dict[str, Any], keywords: List[Dict[str, Any]]) -> str:
    available = group.get("keyword_headers") or ["Keyword", "Volume", "CPC", "inTITLE", "inURL"]
    preferred = ["Keyword", "Volume", "CPC", "inTITLE", "inURL", "TR", "UR", "Rank"]
    columns = [col for col in preferred if col in available]
    columns += [col for col in available if col not in columns and col and not col.isdigit()]

    if not columns:
        columns = ["Keyword", "Volume", "CPC"]

    header_html = "".join(f"<th>{esc(col)}</th>" for col in columns)

    if not keywords:
        return (
            '<table class="keyword-table">'
            f'<thead><tr>{header_html}</tr></thead>'
            f'<tbody><tr><td class="empty" colspan="{len(columns)}">No keywords match the current filters.</td></tr></tbody>'
            '</table>'
        )

    rows = []
    for keyword in keywords:
        cells = []
        for col in columns:
            value = keyword.get(col, "")
            col_key = col.lower()
            if col_key == "volume":
                cells.append(f'<td class="num volume">{pretty_int(value)}</td>')
            elif col_key == "cpc":
                cpc = to_float(value)
                css_class = "cpc-zero" if cpc <= 0 else "cpc-positive"
                cells.append(f'<td class="num {css_class}">{pretty_money(value)}</td>')
            elif col_key in {"intitle", "inurl"}:
                cells.append(f'<td class="center">{yes_no(value)}</td>')
            elif col_key in {"rank", "tr", "ur"}:
                cells.append(f'<td class="num">{esc(value) if clean_cell(value) else "—"}</td>')
            else:
                cells.append(f'<td>{esc(value)}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")

    return '<table class="keyword-table"><thead><tr>' + header_html + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def report_card(index: int, group: Dict[str, Any], keywords: List[Dict[str, Any]]) -> str:
    group_name = group.get("group") or group.get("title") or group.get("url") or f"Page {index}"
    title = group.get("title", "")
    url = group.get("url", "")
    description = group.get("description", "")
    h1 = group.get("h1", "")

    title_len = len(clean_cell(title))
    desc_len = len(clean_cell(description))
    total_volume = sum(to_int(k.get("Volume", k.get("Volume_num", 0))) for k in keywords)

    return (
        '<section class="page-card">'
        '<div class="card-title-bar">'
        f'<div class="card-title-text">{index}. {esc(group_name)}</div>'
        '</div>'
        '<div class="page-info">'
        '<div class="h1-row">'
        '<span class="h1-badge">H1</span>'
        f'<span class="h1-value">{esc(h1) if h1 else "—"}</span>'
        '</div>'
        '<div class="snippet-and-meta">'
        '<div class="snippet-box">'
        f'<div class="url-line">{esc(url) if url else "No URL in file"}</div>'
        f'<h3>{esc(title) if title else "No title in file"}</h3>'
        f'<p>{esc(description) if description else "No meta description in file"}</p>'
        '</div>'
        '<div class="meta-box">'
        '<div class="meta-label">Meta Title Length</div>'
        '<div class="metric-row">'
        f'{metric_pill("70", title_len, 70)}'
        f'{metric_pill("78", title_len, 78)}'
        '</div>'
        '<div class="meta-label spaced">Meta Description Length</div>'
        '<div class="metric-row">'
        f'{metric_pill("300", desc_len, 300)}'
        f'{metric_pill("120", desc_len, 120)}'
        '</div>'
        f'<div class="page-summary">{len(keywords):,} keywords · {total_volume:,} searches/mo</div>'
        '</div>'
        '</div>'
        '</div>'
        '<div class="table-box">'
        f'{keyword_table(group, keywords)}'
        '</div>'
        '</section>'
    )


def render_css() -> None:
    st.markdown(
        """
<style>
:root {
    --report-blue: #1f4f7e;
    --report-blue-dark: #173f66;
    --line: #dbe5f0;
    --soft-bg: #eef3f8;
    --text: #142536;
    --muted: #6c7c8e;
}
.stApp { background: var(--soft-bg); }
.block-container { max-width: 1860px; padding-top: 2rem; padding-bottom: 4rem; }
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e5ebf2; }
.report-header {
    display: flex;
    justify-content: space-between;
    align-items: end;
    gap: 1.5rem;
    margin-bottom: 1.25rem;
}
.report-header h1 {
    margin: 0;
    color: var(--text);
    font-size: 1.9rem;
    letter-spacing: -0.03em;
}
.report-subtitle {
    margin-top: .35rem;
    color: var(--muted);
    font-size: .9rem;
}
.summary-pills {
    display: flex;
    flex-wrap: wrap;
    gap: .5rem;
    justify-content: flex-end;
}
.summary-pill {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 999px;
    padding: .55rem .8rem;
    color: #536579;
    box-shadow: 0 1px 6px rgba(20, 38, 55, .05);
    font-size: .85rem;
    white-space: nowrap;
}
.summary-pill strong { color: var(--report-blue); }
.report-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.5rem;
    align-items: start;
}
.page-card {
    background: #ffffff;
    border: 1px solid #cbd9e8;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 10px 28px rgba(31, 79, 126, .09);
}
.card-title-bar {
    background: var(--report-blue);
    color: #ffffff;
    padding: .9rem 1.1rem;
}
.card-title-text {
    font-weight: 800;
    font-size: 1rem;
    line-height: 1.25;
}
.page-info {
    background: var(--report-blue);
    padding: 0 .55rem .65rem;
}
.h1-row {
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr);
    gap: .55rem;
    margin-bottom: .55rem;
}
.h1-badge {
    background: var(--report-blue-dark);
    color: #ffffff;
    border: 1px solid rgba(255,255,255,.25);
    border-radius: 8px;
    min-height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
}
.h1-value {
    background: #ffffff;
    color: var(--text);
    border-radius: 8px;
    min-height: 40px;
    display: flex;
    align-items: center;
    padding: 0 .9rem;
    font-weight: 700;
    border: 1px solid var(--line);
    overflow: hidden;
    text-overflow: ellipsis;
}
.snippet-and-meta {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 205px;
    gap: .55rem;
}
.snippet-box, .meta-box {
    background: #ffffff;
    border: 1px solid var(--line);
    border-radius: 9px;
}
.snippet-box {
    min-height: 128px;
    padding: 1rem 1.1rem;
}
.url-line {
    color: var(--muted);
    font-size: .76rem;
    margin-bottom: .5rem;
    word-break: break-word;
}
.snippet-box h3 {
    margin: 0 0 .4rem;
    color: var(--report-blue);
    font-size: 1.05rem;
    line-height: 1.25;
}
.snippet-box p {
    margin: 0;
    color: var(--text);
    font-size: .84rem;
    line-height: 1.45;
}
.meta-box {
    padding: .85rem;
}
.meta-label {
    color: var(--muted);
    font-size: .75rem;
    margin-bottom: .4rem;
}
.meta-label.spaced { margin-top: .75rem; }
.metric-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: .45rem;
}
.metric-pill {
    border-radius: 8px;
    color: #ffffff;
    text-align: center;
    padding: .4rem .3rem;
    background: #657d98;
}
.metric-pill.good { background: var(--report-blue); }
.metric-pill.bad { background: #d94f61; }
.metric-pill.muted { background: #657d98; }
.metric-pill span {
    display: block;
    font-size: .65rem;
    opacity: .8;
}
.metric-pill strong {
    font-size: .8rem;
}
.page-summary {
    margin-top: .75rem;
    padding-top: .65rem;
    border-top: 1px solid #e7edf4;
    color: var(--muted);
    font-size: .78rem;
}
.table-box { padding: .65rem; background: #ffffff; overflow-x: auto; }
.keyword-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: .82rem;
    color: var(--text);
}
.keyword-table th {
    background: var(--report-blue);
    color: #ffffff;
    text-align: left;
    padding: .72rem .85rem;
    font-weight: 800;
    white-space: nowrap;
}
.keyword-table th:first-child { border-top-left-radius: 9px; }
.keyword-table th:last-child { border-top-right-radius: 9px; }
.keyword-table td {
    padding: .62rem .85rem;
    border-bottom: 1px solid #e8eef5;
    vertical-align: middle;
}
.keyword-table tbody tr:nth-child(even) td { background: #f7f9fc; }
.keyword-table tbody tr:hover td { background: #edf5ff; }
.keyword-table .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.keyword-table .center { text-align: center; color: var(--muted); }
.keyword-table .volume { color: #24a46b; font-weight: 800; }
.keyword-table .cpc-zero { color: #e05262; font-weight: 800; }
.keyword-table .cpc-positive { color: #f08a24; font-weight: 800; }
.keyword-table .empty { text-align: center; color: var(--muted); padding: 1.3rem !important; }
@media (max-width: 1200px) {
    .report-grid { grid-template-columns: 1fr; }
    .report-header { align-items: flex-start; flex-direction: column; }
    .summary-pills { justify-content: flex-start; }
}
@media (max-width: 720px) {
    .snippet-and-meta { grid-template-columns: 1fr; }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_report(metadata: Dict[str, str], groups: List[Dict[str, Any]], filtered: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]], file_name: str) -> None:
    render_css()

    project = metadata.get("Project Name", "SEO CSV Report").replace("AUDIT  - ", "")
    total_pages = len(groups)
    total_keywords_raw = sum(len(group.get("keywords", [])) for group in groups)
    total_keywords_shown = sum(len(keywords) for _, keywords in filtered)
    total_volume_shown = sum(to_int(keyword.get("Volume", keyword.get("Volume_num", 0))) for _, keywords in filtered for keyword in keywords)

    header = (
        '<div class="report-header">'
        '<div>'
        '<h1>SEO CSV Report</h1>'
        f'<div class="report-subtitle">{esc(project)} · {esc(file_name)}</div>'
        '</div>'
        '<div class="summary-pills">'
        f'<div class="summary-pill"><strong>{total_pages:,}</strong> pages</div>'
        f'<div class="summary-pill"><strong>{total_keywords_shown:,}</strong> keywords shown</div>'
        f'<div class="summary-pill"><strong>{total_keywords_raw:,}</strong> keywords in file</div>'
        f'<div class="summary-pill"><strong>{total_volume_shown:,}</strong> searches/mo shown</div>'
        '</div>'
        '</div>'
    )

    cards = ''.join(report_card(i, group, keywords) for i, (group, keywords) in enumerate(filtered, start=1))
    st.markdown(header + '<div class="report-grid">' + cards + '</div>', unsafe_allow_html=True)


# -----------------------------
# App
# -----------------------------
csv_bytes, file_name = get_csv_bytes()

st.sidebar.header("Filters")
hide_zero_cpc = st.sidebar.checkbox("Hide CPC = $0", value=False)
hide_under_50 = st.sidebar.checkbox("Hide searches under 50/mo", value=False)

if csv_bytes is None:
    st.info("Choose a CSV file to view the report.")
    st.stop()

try:
    metadata, groups = parse_grouped_csv(csv_bytes)
except Exception as exc:
    st.error(f"Could not parse this CSV: {exc}")
    st.stop()

if not groups:
    st.warning("No page groups were found in this CSV.")
    st.stop()

filtered_groups: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
for group in groups:
    keywords = [
        keyword
        for keyword in group.get("keywords", [])
        if keyword_visible(keyword, hide_zero_cpc=hide_zero_cpc, hide_under_50=hide_under_50)
    ]
    filtered_groups.append((group, keywords))

render_report(metadata, groups, filtered_groups, file_name)

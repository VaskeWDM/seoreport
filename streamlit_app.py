import csv
import html
import io
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st


# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------
st.set_page_config(
    page_title="SEO One-Page Report",
    page_icon="📋",
    layout="wide",
)


# ------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------
def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith('="') and s.endswith('"'):
        s = s[2:-1]
    s = s.replace("&amp;", "&")
    return s.strip()


def safe(value: Any) -> str:
    return html.escape(clean_cell(value))


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


def pretty_int(value: Any) -> str:
    return f"{to_int(value):,}"


def pretty_money(value: Any) -> str:
    return f"${to_float(value):.2f}"


def is_numberish(value: Any) -> bool:
    s = clean_cell(value)
    return bool(re.fullmatch(r"[0-9,.\-$]+", s)) if s else False


def yes_no(value: Any) -> str:
    s = clean_cell(value).lower()
    if not s or s in {"-", "0", "no", "false", "n"}:
        return "—"
    return "✓"


def metric_class(current: int, limit: int) -> str:
    if current == 0:
        return "muted"
    if current > limit:
        return "bad"
    if current >= int(limit * 0.55):
        return "good"
    return "muted"


# ------------------------------------------------------------
# Parser
# ------------------------------------------------------------
@st.cache_data(show_spinner=False)
def parse_grouped_csv(file_bytes: bytes) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """
    Parses the grouped SEO CSV layout:

    Project Name,...
    Total Groups,...

    Group,Title,URL,DESC,H1,
    <page row>
    Keyword,Volume,CPC,inTITLE,inURL,<count>
    <keyword rows>

    It also supports extra keyword columns if future exports include them.
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

        # Metadata before grouped sections.
        if first not in {"Group", "Keyword"} and len(row) > 1:
            metadata[first] = clean_cell(row[1])
            i += 1
            continue

        if first != "Group":
            i += 1
            continue

        group_header = [clean_cell(c) for c in row]
        page_row = rows[i + 1] if i + 1 < len(rows) else []

        page_data: Dict[str, str] = {}
        for col_index, header in enumerate(group_header):
            if not header:
                continue
            page_data[header] = clean_cell(page_row[col_index]) if col_index < len(page_row) else ""

        group = {
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

        # Find the keyword header row.
        while i < len(rows):
            r = rows[i]
            if r and clean_cell(r[0]) == "Keyword":
                raw_headers = [clean_cell(c) for c in r]
                headers: List[str] = []
                for h in raw_headers:
                    # Some exports put a keyword count as the final cell of the header row.
                    if h and not h.isdigit():
                        headers.append(h)
                    elif h.isdigit():
                        group["keyword_count_from_file"] = int(h)
                group["keyword_headers"] = headers
                i += 1
                break
            if r and clean_cell(r[0]) == "Group":
                break
            i += 1

        headers = group["keyword_headers"] or ["Keyword", "Volume", "CPC", "inTITLE", "inURL"]

        # Read keywords until next group.
        while i < len(rows):
            r = rows[i]
            if r and clean_cell(r[0]) == "Group":
                break
            if r and any(clean_cell(c) for c in r):
                kw: Dict[str, Any] = {}
                for col_index, header in enumerate(headers):
                    kw[header] = clean_cell(r[col_index]) if col_index < len(r) else ""

                if clean_cell(kw.get("Keyword", "")):
                    kw["Volume_num"] = to_int(kw.get("Volume", 0))
                    kw["CPC_num"] = to_float(kw.get("CPC", 0))
                    group["keywords"].append(kw)
            i += 1

        groups.append(group)

    return metadata, groups


# ------------------------------------------------------------
# Load CSV
# ------------------------------------------------------------
def get_csv_bytes() -> Tuple[bytes | None, str]:
    st.sidebar.header("CSV file")
    source = st.sidebar.radio(
        "Choose source",
        ["Upload CSV", "Open CSV from local folder"],
        label_visibility="collapsed",
    )

    if source == "Upload CSV":
        uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
        if not uploaded:
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
        st.sidebar.warning("No CSV files found in that folder.")
        return None, ""

    labels = [str(p.relative_to(folder_path)) for p in files]
    selected_label = st.sidebar.selectbox("CSV file", labels)
    selected_path = files[labels.index(selected_label)]

    try:
        return selected_path.read_bytes(), selected_path.name
    except Exception as exc:
        st.sidebar.error(f"Could not read file: {exc}")
        return None, ""


# ------------------------------------------------------------
# Filtering and rendering
# ------------------------------------------------------------
def keyword_passes_filters(kw: Dict[str, Any], hide_zero_cpc: bool, hide_under_50: bool) -> bool:
    if hide_zero_cpc and to_float(kw.get("CPC", kw.get("CPC_num", 0))) <= 0:
        return False
    if hide_under_50 and to_int(kw.get("Volume", kw.get("Volume_num", 0))) < 50:
        return False
    return True


def render_length_box(label: str, current: int, limit: int) -> str:
    klass = metric_class(current, limit)
    return f"""
        <div class=\"mini-stat {klass}\">
            <span class=\"mini-label\">{label}</span>
            <strong>{current}/{limit}</strong>
        </div>
    """


def render_keyword_table(group: Dict[str, Any], keywords: List[Dict[str, Any]]) -> str:
    available_headers = group.get("keyword_headers") or ["Keyword", "Volume", "CPC", "inTITLE", "inURL"]
    preferred = ["Keyword", "Volume", "CPC", "inTITLE", "inURL", "TR", "UR", "Rank"]

    columns: List[str] = [c for c in preferred if c in available_headers]
    for c in available_headers:
        if c not in columns and c and not c.isdigit():
            columns.append(c)

    if not columns:
        columns = ["Keyword", "Volume", "CPC"]

    header_cells = "".join(f"<th>{safe(c)}</th>" for c in columns)

    if not keywords:
        return f"""
            <table class=\"kw-table\">
                <thead><tr>{header_cells}</tr></thead>
                <tbody><tr><td colspan=\"{len(columns)}\" class=\"empty-row\">No keywords match the current filters.</td></tr></tbody>
            </table>
        """

    rows_html = []
    for kw in keywords:
        cells = []
        for col in columns:
            raw = kw.get(col, "")
            col_lower = col.lower()
            if col_lower == "volume":
                cells.append(f"<td class=\"num volume\">{pretty_int(raw)}</td>")
            elif col_lower == "cpc":
                cpc = to_float(raw)
                cpc_class = "cpc-zero" if cpc <= 0 else "cpc-positive"
                cells.append(f"<td class=\"num {cpc_class}\">{pretty_money(raw)}</td>")
            elif col_lower in {"intitle", "inurl"}:
                cells.append(f"<td class=\"center\">{yes_no(raw)}</td>")
            elif col_lower in {"rank", "tr", "ur"} and is_numberish(raw):
                cells.append(f"<td class=\"num\">{safe(raw)}</td>")
            else:
                cells.append(f"<td>{safe(raw)}</td>")
        rows_html.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
        <table class=\"kw-table\">
            <thead><tr>{header_cells}</tr></thead>
            <tbody>{''.join(rows_html)}</tbody>
        </table>
    """


def render_card(index: int, group: Dict[str, Any], keywords: List[Dict[str, Any]]) -> str:
    group_name = group.get("group", "") or group.get("title", "") or group.get("url", "") or f"Page {index}"
    title = group.get("title", "")
    url = group.get("url", "")
    desc = group.get("description", "")
    h1 = group.get("h1", "")

    title_len = len(clean_cell(title))
    desc_len = len(clean_cell(desc))
    keyword_count = len(keywords)
    total_volume = sum(to_int(k.get("Volume", k.get("Volume_num", 0))) for k in keywords)

    table_html = render_keyword_table(group, keywords)

    return f"""
    <section class=\"report-card\">
        <div class=\"card-top\">
            <div class=\"card-title\">
                <span class=\"fake-check\"></span>
                <span>{index}. {safe(group_name)}</span>
            </div>
            <div class=\"fake-actions\" aria-hidden=\"true\">
                <span>⚙</span><span>▣</span><span>👁</span><span>☁</span><span>⌘</span>
            </div>
        </div>

        <div class=\"page-panel\">
            <div class=\"h1-row\">
                <span class=\"h1-badge\">H1</span>
                <span class=\"h1-text\">{safe(h1) if h1 else '—'}</span>
                <span class=\"connect-pill\">CONNECT GROUP⌄</span>
            </div>

            <div class=\"body-grid\">
                <div class=\"snippet-box\">
                    <div class=\"url-line\">{safe(url) if url else 'No URL in file'}</div>
                    <h3>{safe(title) if title else 'No title in file'}</h3>
                    <p>{safe(desc) if desc else 'No meta description in file'}</p>
                </div>

                <div class=\"meta-box\">
                    <div class=\"meta-label\">Meta Title Length</div>
                    <div class=\"stat-row\">
                        {render_length_box('Desktop', title_len, 70)}
                        {render_length_box('Mobile', title_len, 78)}
                    </div>
                    <div class=\"meta-label second\">Meta Description Length</div>
                    <div class=\"stat-row\">
                        {render_length_box('Desktop', desc_len, 300)}
                        {render_length_box('Mobile', desc_len, 120)}
                    </div>
                    <div class=\"tiny-summary\">{keyword_count:,} keywords · {total_volume:,} searches/mo</div>
                </div>
            </div>
        </div>

        <div class=\"table-wrap\">
            {table_html}
        </div>
    </section>
    """


def render_report(metadata: Dict[str, str], groups: List[Dict[str, Any]], filtered_groups: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]], file_name: str) -> None:
    total_pages = len(groups)
    total_keywords_raw = sum(len(g.get("keywords", [])) for g in groups)
    total_keywords_filtered = sum(len(kws) for _, kws in filtered_groups)
    total_volume_filtered = sum(to_int(k.get("Volume", k.get("Volume_num", 0))) for _, kws in filtered_groups for k in kws)

    project = metadata.get("Project Name", "SEO CSV Report")
    project = project.replace("AUDIT  - ", "")

    css = """
    <style>
        .block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1900px; }
        .report-shell { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #102033; }
        .report-hero { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin: 0 0 22px 0; }
        .report-hero h1 { margin: 0; font-size: 30px; line-height: 1.15; color:#102033; letter-spacing:-.03em; }
        .report-hero .sub { margin-top: 6px; color:#66758a; font-size: 14px; }
        .summary-pills { display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
        .summary-pill { background:#ffffff; border:1px solid #dce5ef; border-radius:999px; padding:9px 13px; box-shadow:0 1px 5px rgba(15, 35, 60, .05); font-size:13px; color:#506176; }
        .summary-pill strong { color:#173f66; }
        .report-grid { column-count: 2; column-gap: 28px; }
        .report-card { break-inside: avoid; display:inline-block; width:100%; margin:0 0 28px; background:#ffffff; border:1px solid #d8e4f0; border-radius:13px; overflow:hidden; box-shadow:0 10px 28px rgba(22, 55, 88, .08); }
        .card-top { background:#1f4f7e; color:#fff; padding:13px 18px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
        .card-title { display:flex; align-items:center; gap:12px; font-weight:800; font-size:16px; line-height:1.2; }
        .fake-check { width:20px; height:20px; border-radius:5px; background:#fff; box-shadow: inset 0 0 0 1px rgba(0,0,0,.18); flex:0 0 auto; }
        .fake-actions { display:flex; gap:7px; white-space:nowrap; }
        .fake-actions span { width:28px; height:28px; border-radius:8px; display:inline-flex; align-items:center; justify-content:center; background:#173f66; color:#fff; font-size:12px; border:1px solid rgba(255,255,255,.2); }
        .page-panel { background:#1f4f7e; padding:0 9px 10px; }
        .h1-row { display:grid; grid-template-columns: 44px 1fr 185px; gap:9px; align-items:center; margin-bottom:9px; }
        .h1-badge { background:#1f4f7e; color:#fff; border-radius:7px; height:38px; display:flex; align-items:center; justify-content:center; font-weight:800; border:1px solid rgba(255,255,255,.35); }
        .h1-text, .connect-pill { background:#fff; color:#263749; min-height:38px; border-radius:9px; display:flex; align-items:center; padding:0 14px; font-weight:700; border:1px solid #d9e4ef; overflow:hidden; text-overflow:ellipsis; }
        .connect-pill { justify-content:center; color:#8796a6; font-weight:800; letter-spacing:.02em; }
        .body-grid { display:grid; grid-template-columns: 1fr 205px; gap:9px; align-items:stretch; }
        .snippet-box, .meta-box { background:#fff; border-radius:9px; border:1px solid #d9e4ef; }
        .snippet-box { padding:15px 18px; min-height:126px; }
        .url-line { color:#6e7e91; font-size:12px; margin-bottom:9px; word-break:break-word; }
        .snippet-box h3 { margin:0 0 6px; color:#1f4f7e; font-size:17px; line-height:1.25; }
        .snippet-box p { margin:0; color:#1a2938; font-size:13px; line-height:1.45; }
        .meta-box { padding:13px; }
        .meta-label { color:#69798d; font-size:12px; margin-bottom:7px; }
        .meta-label.second { margin-top:12px; }
        .stat-row { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
        .mini-stat { background:#1f4f7e; color:#fff; border-radius:9px; padding:8px 9px; text-align:center; }
        .mini-stat.bad { background:#d8485e; }
        .mini-stat.good { background:#1f4f7e; }
        .mini-stat.muted { background:#5f7893; }
        .mini-label { display:block; font-size:10px; opacity:.8; margin-bottom:2px; }
        .mini-stat strong { font-size:13px; }
        .tiny-summary { margin-top:12px; padding-top:10px; border-top:1px solid #e7edf3; color:#68798d; font-size:12px; }
        .table-wrap { padding:12px 10px 14px; background:#fff; }
        .kw-table { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; color:#203243; overflow:hidden; border-radius:9px; }
        .kw-table thead th { background:#1f4f7e; color:#fff; padding:11px 12px; text-align:left; font-weight:800; white-space:nowrap; }
        .kw-table thead th:first-child { border-top-left-radius:9px; }
        .kw-table thead th:last-child { border-top-right-radius:9px; }
        .kw-table tbody td { padding:10px 12px; border-bottom:1px solid #e8eef5; vertical-align:middle; }
        .kw-table tbody tr:nth-child(odd) td { background:#ffffff; }
        .kw-table tbody tr:nth-child(even) td { background:#f7f9fc; }
        .kw-table tbody tr:hover td { background:#edf5ff; }
        .kw-table .num { text-align:right; white-space:nowrap; font-variant-numeric: tabular-nums; }
        .kw-table .center { text-align:center; color:#66758a; }
        .kw-table .volume { color:#22a467; font-weight:800; }
        .kw-table .cpc-zero { color:#e04f5f; font-weight:800; }
        .kw-table .cpc-positive { color:#f28b24; font-weight:800; }
        .empty-row { text-align:center; color:#75859a; padding:22px !important; }
        @media (max-width: 1200px) {
            .report-grid { column-count: 1; }
            .report-hero { align-items:flex-start; flex-direction:column; }
            .summary-pills { justify-content:flex-start; }
        }
        @media (max-width: 760px) {
            .h1-row, .body-grid { grid-template-columns: 1fr; }
            .connect-pill { min-height:38px; }
            .fake-actions { display:none; }
            .table-wrap { overflow-x:auto; }
        }
    </style>
    """

    cards = "".join(render_card(i, group, kws) for i, (group, kws) in enumerate(filtered_groups, start=1))

    html_report = f"""
    {css}
    <div class=\"report-shell\">
        <div class=\"report-hero\">
            <div>
                <h1>SEO CSV Report</h1>
                <div class=\"sub\">{safe(project)} · {safe(file_name)}</div>
            </div>
            <div class=\"summary-pills\">
                <div class=\"summary-pill\"><strong>{total_pages:,}</strong> pages</div>
                <div class=\"summary-pill\"><strong>{total_keywords_filtered:,}</strong> keywords shown</div>
                <div class=\"summary-pill\"><strong>{total_keywords_raw:,}</strong> keywords in file</div>
                <div class=\"summary-pill\"><strong>{total_volume_filtered:,}</strong> searches/mo shown</div>
            </div>
        </div>
        <main class=\"report-grid\">{cards}</main>
    </div>
    """

    st.markdown(html_report, unsafe_allow_html=True)


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
csv_bytes, file_name = get_csv_bytes()

st.sidebar.header("Filters")
hide_zero_cpc = st.sidebar.checkbox("Hide CPC = $0", value=False)
hide_under_50 = st.sidebar.checkbox("Hide searches under 50/mo", value=False)

if not csv_bytes:
    st.info("Choose a CSV file to view the one-page report.")
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
        kw for kw in group.get("keywords", [])
        if keyword_passes_filters(kw, hide_zero_cpc=hide_zero_cpc, hide_under_50=hide_under_50)
    ]
    filtered_groups.append((group, keywords))

render_report(metadata, groups, filtered_groups, file_name)

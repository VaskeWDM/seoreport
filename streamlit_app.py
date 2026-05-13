import csv
import io
import math
import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import plotly.express as px
import streamlit as st


# =============================================================================
# Page setup
# =============================================================================
st.set_page_config(
    page_title="Local SEO Report",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --blue: #214f7d;
            --blue-2: #173e63;
            --bg: #f3f6fb;
            --card: #ffffff;
            --muted: #667085;
            --line: #e4e9f2;
            --good: #12805c;
            --warn: #b54708;
            --bad: #b42318;
        }

        .stApp {
            background: var(--bg);
        }

        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--line);
        }

        .hero {
            background: linear-gradient(135deg, #173e63 0%, #245c91 100%);
            color: white;
            padding: 28px 30px;
            border-radius: 22px;
            margin-bottom: 18px;
            box-shadow: 0 14px 35px rgba(23, 62, 99, .16);
        }

        .hero h1 {
            font-size: 34px;
            line-height: 1.05;
            margin: 0 0 8px 0;
            font-weight: 800;
        }

        .hero p {
            color: rgba(255,255,255,.84);
            font-size: 16px;
            margin: 0;
            max-width: 980px;
        }

        .section-title {
            margin: 28px 0 8px 0;
            color: #101828;
            font-size: 23px;
            font-weight: 800;
            letter-spacing: -0.01em;
        }

        .section-help {
            color: var(--muted);
            margin-top: -4px;
            margin-bottom: 16px;
            font-size: 14px;
        }

        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 16px 18px;
            box-shadow: 0 10px 22px rgba(16, 24, 40, .045);
        }

        div[data-testid="stMetric"] label {
            color: var(--muted) !important;
        }

        .action-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 18px 20px;
            margin-bottom: 12px;
            box-shadow: 0 10px 22px rgba(16, 24, 40, .045);
        }

        .action-card .topline {
            display: flex;
            justify-content: space-between;
            gap: 14px;
            align-items: center;
            margin-bottom: 8px;
        }

        .action-card h3 {
            margin: 0;
            color: #101828;
            font-size: 18px;
            line-height: 1.25;
        }

        .action-card p {
            color: #475467;
            margin: 6px 0 0 0;
            font-size: 14px;
        }

        .pill {
            display: inline-block;
            border-radius: 999px;
            padding: 5px 10px;
            font-size: 12px;
            font-weight: 750;
            white-space: nowrap;
            border: 1px solid transparent;
        }

        .pill-blue { background:#e8f2fd; color:#184e7e; border-color:#cbe3fb; }
        .pill-green { background:#eafaf4; color:#067647; border-color:#c8f1df; }
        .pill-orange { background:#fff4e5; color:#b54708; border-color:#fedf89; }
        .pill-red { background:#fef3f2; color:#b42318; border-color:#fecdca; }
        .pill-gray { background:#f2f4f7; color:#344054; border-color:#e4e7ec; }

        .page-card {
            background: #ffffff;
            border: 1px solid var(--line);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 10px 22px rgba(16, 24, 40, .045);
            margin-bottom: 18px;
        }

        .page-card-header {
            background: var(--blue);
            color: white;
            padding: 14px 18px;
            display: flex;
            justify-content: space-between;
            gap: 14px;
            align-items: center;
        }

        .page-card-header .name {
            font-weight: 800;
            font-size: 16px;
            line-height: 1.2;
        }

        .page-card-body {
            padding: 18px;
        }

        .url-line {
            color: #667085;
            font-size: 13px;
            margin-bottom: 8px;
            word-break: break-all;
        }

        .meta-title {
            color: #173e63;
            font-weight: 800;
            font-size: 17px;
            margin-bottom: 6px;
        }

        .desc {
            color: #344054;
            font-size: 14px;
            line-height: 1.45;
            margin-bottom: 12px;
        }

        .mini-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 12px;
        }

        .mini-box {
            border: 1px solid var(--line);
            background: #f8fafc;
            border-radius: 14px;
            padding: 10px 12px;
        }

        .mini-label {
            color: #667085;
            font-size: 12px;
            margin-bottom: 3px;
        }

        .mini-value {
            color: #101828;
            font-size: 16px;
            font-weight: 800;
        }

        .small-note {
            color: #667085;
            font-size: 13px;
        }

        .clean-table-title {
            color: #101828;
            font-weight: 800;
            margin: 16px 0 8px 0;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border-radius: 999px;
            padding: 10px 16px;
            border: 1px solid var(--line);
        }

        .stTabs [aria-selected="true"] {
            background: #e8f2fd !important;
            color: #184e7e !important;
            border-color: #cbe3fb !important;
        }

        @media (max-width: 900px) {
            .mini-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .hero h1 { font-size: 27px; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# Helpers
# =============================================================================
def clean_cell(value):
    if value is None:
        return ""
    value = str(value).replace("&amp;", "&").strip()
    if value.startswith('="') and value.endswith('"'):
        value = value[2:-1]
    value = value.replace('="', '').replace('"', '').replace('=', '').strip()
    return value


def to_int(value):
    text = clean_cell(value).replace(',', '').replace('$', '')
    try:
        return int(float(text))
    except Exception:
        return 0


def to_float(value):
    text = clean_cell(value).replace(',', '').replace('$', '')
    try:
        return float(text)
    except Exception:
        return 0.0


def compact_number(value):
    value = float(value or 0)
    if value >= 1_000_000:
        return f"{value/1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value/1_000:.1f}k"
    return f"{value:,.0f}"


def short_text(value, limit=165):
    value = clean_cell(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def slug_label(url, title, group):
    if clean_cell(group):
        label = clean_cell(group)
    elif clean_cell(title):
        label = clean_cell(title)
    elif clean_cell(url):
        label = clean_cell(url)
    else:
        label = "Untitled page"
    label = re.sub(r"\s+", " ", label).strip()
    return short_text(label, 72)


def parse_base_url(project_name):
    match = re.search(r"https?://[^\s,]+", project_name or "")
    if match:
        return match.group(0).rstrip('/') + '/'
    return ""


def full_url(base_url, url):
    url = clean_cell(url)
    if not url:
        return ""
    if url.startswith('http://') or url.startswith('https://'):
        return url
    if base_url:
        return urljoin(base_url, url)
    return url


def contains_any(text, terms):
    text = f" {str(text).lower()} "
    return any(term.strip().lower() and term.strip().lower() in text for term in terms)


def token_set(text):
    return {t for t in re.findall(r"[a-z0-9']+", str(text).lower()) if len(t) > 2}


def is_kw_aligned(row):
    keyword = str(row.get('Keyword', '')).lower()
    title = str(row.get('Title', '')).lower()
    h1 = str(row.get('H1', '')).lower()
    url = str(row.get('URL', '')).lower().replace('-', ' ').replace('/', ' ')
    desc = str(row.get('Description', '')).lower()

    explicit_title = str(row.get('inTitle', '')).strip().lower() not in {'', '0', 'no', 'false', 'none', '-'}
    explicit_url = str(row.get('inURL', '')).strip().lower() not in {'', '0', 'no', 'false', 'none', '-'}
    if explicit_title or explicit_url:
        return True

    if keyword and (keyword in title or keyword in h1 or keyword in url or keyword in desc):
        return True

    kw_tokens = token_set(keyword)
    page_tokens = token_set(" ".join([title, h1, url, desc]))
    if not kw_tokens:
        return False

    # For longer phrases, matching the important words is enough to say the page is directionally aligned.
    overlap = len(kw_tokens & page_tokens) / max(len(kw_tokens), 1)
    return overlap >= 0.55


def length_status(kind, length):
    if kind == 'title':
        if length < 25:
            return 'Too short', 'pill-orange'
        if length > 65:
            return 'Too long', 'pill-orange'
        return 'Good', 'pill-green'
    if length < 70:
        return 'Too short', 'pill-orange'
    if length > 165:
        return 'Too long', 'pill-orange'
    return 'Good', 'pill-green'


@st.cache_data(show_spinner=False)
def parse_audit_csv(raw_bytes):
    if hasattr(raw_bytes, 'getvalue'):
        raw_bytes = raw_bytes.getvalue()
    if isinstance(raw_bytes, str):
        raw_bytes = raw_bytes.encode('utf-8')

    text = raw_bytes.decode('utf-8-sig', errors='replace')
    rows = list(csv.reader(io.StringIO(text)))

    project_name = ""
    pages = []
    keywords = []
    current_page = None
    reading_keywords = False
    page_id = 0

    for row in rows:
        row = [clean_cell(c) for c in row]
        if not row or not any(row):
            reading_keywords = False
            continue

        first = row[0]
        lower_first = first.lower()

        if lower_first == 'project name' and len(row) > 1:
            project_name = row[1]
            continue

        if lower_first == 'group':
            current_page = None
            reading_keywords = False
            continue

        # Group data row usually follows a "Group,Title,URL,DESC,H1" header.
        if not reading_keywords and len(row) >= 5 and row[2].startswith('/') or (not reading_keywords and len(row) >= 5 and row[2].startswith('http')):
            page_id += 1
            current_page = {
                'Page ID': page_id,
                'Group': row[0],
                'Title': row[1],
                'URL': row[2],
                'Description': row[3] if len(row) > 3 else '',
                'H1': row[4] if len(row) > 4 else '',
            }
            pages.append(current_page)
            continue

        if lower_first == 'keyword':
            reading_keywords = True
            continue

        if reading_keywords and current_page:
            keyword = first
            if not keyword:
                continue
            keywords.append(
                {
                    'Page ID': current_page['Page ID'],
                    'Group': current_page['Group'],
                    'Title': current_page['Title'],
                    'URL': current_page['URL'],
                    'Description': current_page['Description'],
                    'H1': current_page['H1'],
                    'Keyword': keyword,
                    'Volume': to_int(row[1]) if len(row) > 1 else 0,
                    'CPC': to_float(row[2]) if len(row) > 2 else 0.0,
                    'inTitle': row[3] if len(row) > 3 else '',
                    'inURL': row[4] if len(row) > 4 else '',
                    'Rank': row[5] if len(row) > 5 else '',
                }
            )

    pages_df = pd.DataFrame(pages)
    keywords_df = pd.DataFrame(keywords)
    return project_name, pages_df, keywords_df


def classify_need(keyword, brand_terms):
    kw = str(keyword).lower()
    if contains_any(kw, brand_terms):
        return 'Brand name searches'
    if any(t in kw for t in ['menu', 'special', 'happy hour', 'price', 'prices', 'drink', 'food', 'burger', 'pizza', 'sandwich', 'fish fry', 'wings', 'beer', 'brunch', 'lunch', 'dinner']):
        return 'Menu, food & specials'
    if any(t in kw for t in ['near me', 'nearby', 'loves park', 'rockford', 'machesney', 'restaurant', 'restaurants', 'bar', 'bars', 'pub', 'grill']):
        return 'Nearby restaurants & bars'
    if any(t in kw for t in ['event', 'events', 'party', 'parties', 'catering', 'private', 'banquet', 'room', 'birthday', 'rehearsal']):
        return 'Events & private parties'
    if any(t in kw for t in ['hour', 'hours', 'open', 'closed', 'address', 'phone', 'contact', 'directions', 'location']):
        return 'Hours, contact & location'
    if any(t in kw for t in ['review', 'reviews', 'photo', 'photos', 'pictures']):
        return 'Reviews & photos'
    return 'Other searches'


def recommend_keyword_action(row):
    if row.get('Is noise', False):
        return 'Ignore or review manually'
    if row.get('Is brand', False):
        return 'Protect brand page'
    need = row.get('Customer need', '')
    if not row.get('Aligned', False):
        if need == 'Menu, food & specials':
            return 'Improve menu page'
        if need == 'Nearby restaurants & bars':
            return 'Add local wording to page'
        if need == 'Events & private parties':
            return 'Build event/private party section'
        if need == 'Hours, contact & location':
            return 'Fix contact/hours info'
        return 'Add this topic to page'
    return 'Keep / monitor'


def make_enriched_keywords(keywords_df, brand_terms, noise_terms):
    if keywords_df.empty:
        return keywords_df.copy()

    df = keywords_df.copy()
    df['Keyword lower'] = df['Keyword'].astype(str).str.lower()
    df['Is brand'] = df['Keyword lower'].apply(lambda x: contains_any(x, brand_terms))
    df['Is noise'] = df['Keyword lower'].apply(lambda x: contains_any(x, noise_terms))
    df['Customer need'] = df['Keyword'].apply(lambda x: classify_need(x, brand_terms))
    df['Aligned'] = df.apply(is_kw_aligned, axis=1)

    # A plain, directional score. Not meant to look scientific — just to sort work sensibly.
    df['Opportunity score'] = (
        df['Volume'].clip(lower=0).apply(lambda x: math.sqrt(x))
        * (1 + df['CPC'].clip(lower=0).clip(upper=5) / 5)
        * df['Aligned'].apply(lambda x: 0.6 if x else 1.35)
        * df['Is brand'].apply(lambda x: 0.55 if x else 1.0)
        * df['Is noise'].apply(lambda x: 0.05 if x else 1.0)
    ).round(2)
    df['Recommendation'] = df.apply(recommend_keyword_action, axis=1)
    df['Page'] = df.apply(lambda r: slug_label(r['URL'], r['Title'], r['Group']), axis=1)
    return df


def make_page_summary(pages_df, kw_df):
    if pages_df.empty:
        return pd.DataFrame()

    rows = []
    for _, p in pages_df.iterrows():
        kws = kw_df[kw_df['Page ID'] == p['Page ID']].copy() if not kw_df.empty else pd.DataFrame()
        clean = kws[~kws.get('Is noise', False)] if not kws.empty else kws
        growth = clean[~clean.get('Is brand', False)] if not clean.empty else clean
        missed = growth[~growth.get('Aligned', False)] if not growth.empty else growth

        title_len = len(str(p.get('Title', '')))
        desc_len = len(str(p.get('Description', '')))
        title_state, _ = length_status('title', title_len)
        desc_state, _ = length_status('desc', desc_len)

        rows.append(
            {
                'Page ID': p['Page ID'],
                'Page': slug_label(p.get('URL'), p.get('Title'), p.get('Group')),
                'URL': p.get('URL', ''),
                'Title': p.get('Title', ''),
                'H1': p.get('H1', ''),
                'Description': p.get('Description', ''),
                'Useful volume': int(clean['Volume'].sum()) if not clean.empty else 0,
                'Growth volume': int(growth['Volume'].sum()) if not growth.empty else 0,
                'Missed volume': int(missed['Volume'].sum()) if not missed.empty else 0,
                'Keywords': int(len(kws)),
                'Useful keywords': int(len(clean)),
                'Needs title work': title_state != 'Good',
                'Needs description work': desc_state != 'Good',
                'Title length': title_len,
                'Meta description length': desc_len,
                'Attention score': int((missed['Volume'].sum() if not missed.empty else 0) + (200 if title_state != 'Good' else 0) + (150 if desc_state != 'Good' else 0)),
            }
        )
    return pd.DataFrame(rows).sort_values(['Attention score', 'Growth volume'], ascending=False)


def action_summary(kw_df, page_df):
    items = []
    if kw_df.empty:
        return items

    useful = kw_df[~kw_df['Is noise']]
    growth = useful[~useful['Is brand']]
    missed = growth[~growth['Aligned']]

    if not page_df.empty:
        top_page = page_df.sort_values('Attention score', ascending=False).iloc[0]
        if top_page['Attention score'] > 0:
            items.append({
                'title': f"Fix this page first: {top_page['Page']}",
                'pill': f"{compact_number(top_page['Missed volume'])} missed searches/mo",
                'pill_class': 'pill-orange',
                'body': "This page has the biggest gap between what people search and what the page clearly talks about. Start with the title, H1, opening copy, and meta description.",
            })

    if not missed.empty:
        top_kw = missed.sort_values(['Volume', 'CPC'], ascending=False).iloc[0]
        items.append({
            'title': f"Add this phrase clearly: “{top_kw['Keyword']}”",
            'pill': f"{compact_number(top_kw['Volume'])}/mo",
            'pill_class': 'pill-blue',
            'body': f"The keyword is assigned to {top_kw['Page']}, but the page does not clearly match it. Add natural wording, not keyword stuffing.",
        })

    if not useful[useful['Is brand']].empty:
        brand_vol = int(useful[useful['Is brand']]['Volume'].sum())
        items.append({
            'title': "Protect your brand searches",
            'pill': f"{compact_number(brand_vol)}/mo",
            'pill_class': 'pill-green',
            'body': "Make sure the homepage, menu page, contact page, hours, photos, and reviews are clean. These people are already looking for you.",
        })

    noise = kw_df[kw_df['Is noise']]
    if not noise.empty:
        items.append({
            'title': "Do not chase every keyword in the export",
            'pill': f"{len(noise):,} noisy terms",
            'pill_class': 'pill-gray',
            'body': "Some terms appear to be competitors, misspellings, or unrelated places. Keep them out of the main plan unless you confirm they really matter.",
        })

    if len(items) < 4 and not growth.empty:
        top_need = growth.groupby('Customer need', as_index=False)['Volume'].sum().sort_values('Volume', ascending=False).iloc[0]
        items.append({
            'title': f"Lean into: {top_need['Customer need']}",
            'pill': f"{compact_number(top_need['Volume'])}/mo",
            'pill_class': 'pill-blue',
            'body': "This is the biggest non-brand demand bucket. Make sure your site has one strong page or section that answers it clearly.",
        })

    return items[:4]


def render_action_card(item):
    st.markdown(
        f"""
        <div class="action-card">
            <div class="topline">
                <h3>{item['title']}</h3>
                <span class="pill {item['pill_class']}">{item['pill']}</span>
            </div>
            <p>{item['body']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def find_csvs(folder, recursive=False):
    path = Path(folder).expanduser()
    if not path.exists() or not path.is_dir():
        return []
    pattern = '**/*.csv' if recursive else '*.csv'
    files = sorted(path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def read_chosen_file():
    st.sidebar.header("CSV file")
    source = st.sidebar.radio(
        "Choose source",
        ["Upload CSV", "Open CSV from local folder"],
        horizontal=False,
    )

    if source == "Upload CSV":
        uploaded = st.sidebar.file_uploader("Upload audit CSV", type=['csv'])
        if uploaded:
            return uploaded.name, uploaded.getvalue()
        return None, None

    folder = st.sidebar.text_input("Folder path", value=str(Path.cwd()))
    recursive = st.sidebar.checkbox("Include subfolders", value=False)
    files = find_csvs(folder, recursive=recursive)

    if not files:
        st.sidebar.warning("No CSV files found in that folder.")
        return None, None

    def display_path(p):
        try:
            return str(p.relative_to(Path(folder).expanduser()))
        except Exception:
            return str(p)

    chosen = st.sidebar.selectbox("Select CSV", files, format_func=display_path)
    if chosen:
        return chosen.name, chosen.read_bytes()
    return None, None


# =============================================================================
# Sidebar controls
# =============================================================================
file_name, raw = read_chosen_file()

st.sidebar.header("Cleanup")
brand_terms_raw = st.sidebar.text_area(
    "Brand terms",
    value="fozzy, fozzy's, fozzys, fozzies, jax, jax pub",
    help="Keywords containing these terms are treated as people already looking for the business.",
)
noise_terms_raw = st.sidebar.text_area(
    "Competitor / noise terms",
    value="fuzzy, fuzzy's, foxys, foxy, weezy, boozies, fitzy, nunzio, woody, shazzy, hozy, gozzys, fazzi",
    help="Terms containing these words are hidden from the main plan by default.",
)
brand_terms = [t.strip().lower() for t in brand_terms_raw.split(',') if t.strip()]
noise_terms = [t.strip().lower() for t in noise_terms_raw.split(',') if t.strip()]

hide_noise = st.sidebar.checkbox("Hide competitor/noise terms", value=True)
min_volume = st.sidebar.slider("Minimum search volume", 0, 1000, 0, step=10)
keywords_per_page = st.sidebar.slider("Keywords shown per page card", 3, 30, 10)


# =============================================================================
# Empty state
# =============================================================================
if not raw:
    st.markdown(
        """
        <div class="hero">
            <h1>Local SEO Report</h1>
            <p>Open an audit CSV to see a simple, page-by-page report: what to fix first, what customers search for, and which keywords belong on each page.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Choose a CSV from the sidebar to begin.")
    st.stop()


# =============================================================================
# Data preparation
# =============================================================================
project_name, pages_df, kw_df_raw = parse_audit_csv(raw)
base_url = parse_base_url(project_name)
kw_df = make_enriched_keywords(kw_df_raw, brand_terms, noise_terms)

if min_volume > 0 and not kw_df.empty:
    kw_df = kw_df[kw_df['Volume'] >= min_volume].copy()
if hide_noise and not kw_df.empty:
    kw_df = kw_df[~kw_df['Is noise']].copy()

page_df = make_page_summary(pages_df, kw_df)

if kw_df.empty or pages_df.empty:
    st.warning("I could open the CSV, but I could not find usable page/keyword data in it.")
    st.stop()

useful_df = kw_df[~kw_df['Is noise']].copy()
growth_df = useful_df[~useful_df['Is brand']].copy()
brand_df = useful_df[useful_df['Is brand']].copy()
missed_df = growth_df[~growth_df['Aligned']].copy()


# =============================================================================
# Header + Metrics
# =============================================================================
st.markdown(
    f"""
    <div class="hero">
        <h1>Local SEO Report</h1>
        <p>{short_text(project_name or file_name, 150)} — a clean view of what pages need work, what customers are searching for, and what to update next.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Pages", f"{len(pages_df):,}")
m2.metric("Keywords", f"{len(kw_df):,}")
m3.metric("Brand searches", compact_number(brand_df['Volume'].sum() if not brand_df.empty else 0))
m4.metric("Growth searches", compact_number(growth_df['Volume'].sum() if not growth_df.empty else 0))


# =============================================================================
# Tabs / Three questions
# =============================================================================
tab_fix, tab_demand, tab_pages = st.tabs(
    ["1. What should I fix first?", "2. What are customers searching for?", "3. Which keywords go with each page?"]
)

with tab_fix:
    st.markdown('<div class="section-title">What should I fix first?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-help">This is the work queue. It focuses on local/business value, not agency-style vanity charts.</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        for item in action_summary(kw_df, page_df):
            render_action_card(item)

    with right:
        chart_df = page_df[page_df['Attention score'] > 0].head(12).copy()
        if chart_df.empty:
            st.success("No obvious page gaps found after your current filters.")
        else:
            chart_df = chart_df.sort_values('Attention score', ascending=True)
            fig = px.bar(
                chart_df,
                x='Missed volume',
                y='Page',
                orientation='h',
                text=chart_df['Missed volume'].apply(compact_number),
                hover_data={'Growth volume': True, 'Useful keywords': True, 'Attention score': True},
                title="Pages with the biggest keyword gap",
            )
            fig.update_traces(textposition='outside', cliponaxis=False)
            fig.update_layout(
                height=430,
                margin=dict(l=8, r=30, t=48, b=8),
                xaxis_title="searches/month not clearly covered",
                yaxis_title="",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="clean-table-title">Top keyword fixes</div>', unsafe_allow_html=True)
    fix_table = missed_df.sort_values(['Opportunity score', 'Volume'], ascending=False).head(30).copy()
    if fix_table.empty:
        st.info("No obvious keyword/page mismatches after filters.")
    else:
        st.dataframe(
            fix_table[['Keyword', 'Volume', 'CPC', 'Customer need', 'Page', 'Recommendation']].style.format(
                {'Volume': '{:,.0f}', 'CPC': '${:,.2f}'}
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_demand:
    st.markdown('<div class="section-title">What are customers searching for?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-help">This replaces vague “search intent” buckets with plain business language. It shows what customers actually want from the site.</div>',
        unsafe_allow_html=True,
    )

    demand_base = useful_df.copy()
    if hide_noise:
        demand_base = demand_base[~demand_base['Is noise']]

    demand = demand_base.groupby('Customer need', as_index=False).agg(
        Volume=('Volume', 'sum'),
        Keywords=('Keyword', 'count'),
    ).sort_values('Volume', ascending=False)

    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        if demand.empty:
            st.info("No demand data available.")
        else:
            chart_df = demand.sort_values('Volume', ascending=True)
            fig = px.bar(
                chart_df,
                x='Volume',
                y='Customer need',
                orientation='h',
                text=chart_df['Volume'].apply(compact_number),
                title="Customer demand by topic",
            )
            fig.update_traces(textposition='outside', cliponaxis=False)
            fig.update_layout(
                height=430,
                margin=dict(l=8, r=35, t=48, b=8),
                xaxis_title="searches/month",
                yaxis_title="",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown('<div class="clean-table-title">What the chart means</div>', unsafe_allow_html=True)
        st.markdown(
            """
            - **Brand name searches**: people already trying to find you. Make the basic pages clean.
            - **Menu, food & specials**: people deciding what to eat or drink. Your menu page matters most.
            - **Nearby restaurants & bars**: people comparing local options. Your homepage and location wording matter.
            - **Events & private parties**: people looking for a reason to book or contact you.
            """
        )

    st.markdown('<div class="clean-table-title">Top searches by customer topic</div>', unsafe_allow_html=True)
    selected_need = st.selectbox(
        "Choose a topic",
        demand['Customer need'].tolist() if not demand.empty else [],
    )
    topic_table = demand_base[demand_base['Customer need'] == selected_need].sort_values('Volume', ascending=False).head(50)
    st.dataframe(
        topic_table[['Keyword', 'Volume', 'CPC', 'Page', 'Recommendation']].style.format(
            {'Volume': '{:,.0f}', 'CPC': '${:,.2f}'}
        ),
        use_container_width=True,
        hide_index=True,
    )

with tab_pages:
    st.markdown('<div class="section-title">Which keywords go with each page?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-help">This is the clean page-by-page report view. Each card shows the page, basic SEO tag health, and the best assigned keywords.</div>',
        unsafe_allow_html=True,
    )

    sort_mode = st.radio(
        "Sort pages by",
        ["Needs attention", "Highest growth searches", "Original order"],
        horizontal=True,
    )

    if sort_mode == "Highest growth searches":
        pages_to_show = page_df.sort_values('Growth volume', ascending=False)
    elif sort_mode == "Original order":
        pages_to_show = page_df.sort_values('Page ID')
    else:
        pages_to_show = page_df.sort_values(['Attention score', 'Growth volume'], ascending=False)

    for _, page in pages_to_show.iterrows():
        page_keywords = kw_df[kw_df['Page ID'] == page['Page ID']].sort_values(['Opportunity score', 'Volume'], ascending=False)
        p_url = full_url(base_url, page['URL'])
        title_state, title_class = length_status('title', page['Title length'])
        desc_state, desc_class = length_status('desc', page['Meta description length'])

        main_pill = 'Needs work' if page['Attention score'] > 0 else 'Looks okay'
        main_class = 'pill-orange' if page['Attention score'] > 0 else 'pill-green'

        st.markdown(
            f"""
            <div class="page-card">
                <div class="page-card-header">
                    <div class="name">{page['Page']}</div>
                    <span class="pill {main_class}">{main_pill}</span>
                </div>
                <div class="page-card-body">
                    <div class="url-line">{p_url}</div>
                    <div class="meta-title">{short_text(page['Title'], 130) or 'No title found'}</div>
                    <div class="desc">{short_text(page['Description'], 230) or 'No meta description found'}</div>
                    <div class="mini-grid">
                        <div class="mini-box"><div class="mini-label">Growth searches</div><div class="mini-value">{compact_number(page['Growth volume'])}</div></div>
                        <div class="mini-box"><div class="mini-label">Missed searches</div><div class="mini-value">{compact_number(page['Missed volume'])}</div></div>
                        <div class="mini-box"><div class="mini-label">Title</div><div class="mini-value"><span class="pill {title_class}">{page['Title length']} chars · {title_state}</span></div></div>
                        <div class="mini-box"><div class="mini-label">Meta description</div><div class="mini-value"><span class="pill {desc_class}">{page['Meta description length']} chars · {desc_state}</span></div></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        display_cols = ['Keyword', 'Volume', 'CPC', 'Customer need', 'Aligned', 'Recommendation']
        display_df = page_keywords.head(keywords_per_page)[display_cols].copy()
        display_df['Aligned'] = display_df['Aligned'].map({True: 'Yes', False: 'No'})
        st.dataframe(
            display_df.style.format({'Volume': '{:,.0f}', 'CPC': '${:,.2f}'}),
            use_container_width=True,
            hide_index=True,
        )
        st.write("")


# =============================================================================
# Exports
# =============================================================================
st.divider()
export_col1, export_col2, export_col3 = st.columns(3)
with export_col1:
    st.download_button(
        "Download keyword report CSV",
        kw_df.drop(columns=['Keyword lower'], errors='ignore').to_csv(index=False).encode('utf-8'),
        file_name='local-seo-keyword-report.csv',
        mime='text/csv',
        use_container_width=True,
    )
with export_col2:
    st.download_button(
        "Download page report CSV",
        page_df.to_csv(index=False).encode('utf-8'),
        file_name='local-seo-page-report.csv',
        mime='text/csv',
        use_container_width=True,
    )
with export_col3:
    action_rows = pd.DataFrame(action_summary(kw_df, page_df))
    st.download_button(
        "Download action list CSV",
        action_rows.to_csv(index=False).encode('utf-8'),
        file_name='local-seo-action-list.csv',
        mime='text/csv',
        use_container_width=True,
    )

import csv
import html
import io
import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# =============================================================================
# CONFIG
# =============================================================================
st.set_page_config(
    page_title="SEO Opportunity Command Center",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_BRAND_TERMS = "fozzy, fozzys, fozzy's, fozzies"
DEFAULT_NOISE_TERMS = (
    "fuzzy, fuzzies, foxys, foxy, foxiis, weezy, boozies, suzy, "
    "ozzy, fitzy, cedarvale, harvey wallbangers, applebee, backyard grill, "
    "ambiance, spikes, nunzio"
)

CSS = """
<style>
    .block-container { padding-top: 1.4rem; padding-bottom: 4rem; }
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(28,35,55,.95), rgba(18,22,34,.95));
        border: 1px solid rgba(120, 140, 255, .22);
        border-radius: 16px;
        padding: 18px 18px 14px 18px;
        box-shadow: 0 8px 30px rgba(0,0,0,.18);
    }
    div[data-testid="stMetric"] label { color: #AAB4D4 !important; }
    .hero {
        padding: 22px 24px;
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(47,98,255,.22), rgba(93,245,206,.08));
        border: 1px solid rgba(160, 180, 255, .22);
        margin-bottom: 18px;
    }
    .hero h1 { margin: 0; font-size: 2.05rem; letter-spacing: -.03em; }
    .hero p { margin: .35rem 0 0 0; color: #B7C0D9; font-size: 1rem; }
    .section-title {
        font-size: 1.25rem;
        font-weight: 750;
        letter-spacing: -.01em;
        margin-top: 2.1rem;
        margin-bottom: .35rem;
    }
    .small-muted { color: #9aa6c7; font-size: .9rem; }
    .insight-card {
        border: 1px solid rgba(160, 180, 255, .18);
        border-radius: 18px;
        padding: 16px 18px;
        background: rgba(255,255,255,.035);
        min-height: 130px;
    }
    .insight-card h3 { margin-top: 0; font-size: 1.05rem; }
    .insight-card p { color: #BAC5E1; margin-bottom: 0; }
    .priority-high { color: #ffca80; font-weight: 700; }
    .priority-med { color: #9ee7ff; font-weight: 700; }
    .priority-low { color: #b7c0d9; font-weight: 700; }
    .stDownloadButton button, .stButton button {
        border-radius: 12px !important;
        font-weight: 650 !important;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
# PARSING
# =============================================================================
def _clean_number(value) -> float:
    """Clean spreadsheet-style numbers such as =\"40500\" and return a float."""
    if value is None:
        return 0.0
    s = str(value).strip()
    s = s.replace('="', "").replace('"', "")
    s = s.replace(",", "").replace("$", "")
    if s in {"", "-", "—", "nan", "None"}:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _safe_text(value) -> str:
    if value is None:
        return ""
    return html.unescape(str(value)).strip()


@st.cache_data(show_spinner=False)
def parse_audit_csv(file_bytes: bytes) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Parse the sectioned SEO audit CSV format:
    Group,Title,URL,DESC,H1
    <page row>
    Keyword,Volume,CPC,inTITLE,inURL,...
    <keyword rows>

    Also supports a fallback flat CSV with Keyword, Volume, CPC and URL-like columns.
    """
    content = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    meta = {}
    groups = []
    current = None
    state = None

    for row in rows:
        if not row or not any(str(cell).strip() for cell in row):
            continue

        first = str(row[0]).strip()

        if first in {"Project Name", "Total Groups"} and len(row) > 1:
            meta[first] = _safe_text(row[1])
            continue

        if first == "Group":
            if current:
                groups.append(current)
            current = None
            state = "group_data"
            continue

        if state == "group_data":
            current = {
                "group_name": _safe_text(row[0]) if len(row) > 0 else "",
                "title": _safe_text(row[1]) if len(row) > 1 else "",
                "url": _safe_text(row[2]) if len(row) > 2 else "",
                "meta_description": _safe_text(row[3]) if len(row) > 3 else "",
                "h1": _safe_text(row[4]) if len(row) > 4 else "",
                "keywords": [],
            }
            state = "after_group"
            continue

        if first == "Keyword" and current:
            state = "keywords"
            continue

        if state == "keywords" and current:
            kw = _safe_text(row[0])
            if not kw:
                continue
            current["keywords"].append(
                {
                    "keyword": kw,
                    "volume": int(_clean_number(row[1] if len(row) > 1 else 0)),
                    "cpc": float(_clean_number(row[2] if len(row) > 2 else 0)),
                    "source_in_title": _safe_text(row[3] if len(row) > 3 else ""),
                    "source_in_url": _safe_text(row[4] if len(row) > 4 else ""),
                }
            )

    if current:
        groups.append(current)

    keyword_rows = []
    page_rows = []
    for g in groups:
        page_rows.append(
            {
                "url": g["url"],
                "title": g["title"],
                "h1": g["h1"],
                "meta_description": g["meta_description"],
                "group_name": g["group_name"],
            }
        )
        for kw in g["keywords"]:
            keyword_rows.append(
                {
                    "url": g["url"],
                    "page_title": g["title"],
                    "h1": g["h1"],
                    "meta_description": g["meta_description"],
                    "group_name": g["group_name"],
                    **kw,
                }
            )

    if keyword_rows:
        keywords = pd.DataFrame(keyword_rows)
        pages = pd.DataFrame(page_rows).drop_duplicates("url")
        return keywords, pages, meta

    # Fallback for ordinary flat CSVs
    flat = pd.read_csv(io.StringIO(content))
    cols = {c.lower().strip(): c for c in flat.columns}
    kw_col = cols.get("keyword") or cols.get("query") or cols.get("term")
    vol_col = cols.get("volume") or cols.get("search volume") or cols.get("monthly volume")
    cpc_col = cols.get("cpc") or cols.get("cost per click")
    url_col = cols.get("url") or cols.get("page url") or cols.get("page")

    if not kw_col:
        raise ValueError("Could not find a keyword column. Expected a sectioned audit CSV or a flat CSV with a Keyword column.")

    keywords = pd.DataFrame(
        {
            "url": flat[url_col].astype(str) if url_col else "",
            "page_title": "",
            "h1": "",
            "meta_description": "",
            "group_name": "",
            "keyword": flat[kw_col].astype(str),
            "volume": flat[vol_col].map(_clean_number).astype(int) if vol_col else 0,
            "cpc": flat[cpc_col].map(_clean_number).astype(float) if cpc_col else 0.0,
            "source_in_title": "",
            "source_in_url": "",
        }
    )
    pages = (
        keywords[["url", "page_title", "h1", "meta_description", "group_name"]]
        .rename(columns={"page_title": "title"})
        .drop_duplicates("url")
    )
    return keywords, pages, meta


# =============================================================================
# ENRICHMENT
# =============================================================================
def split_terms(raw: str) -> List[str]:
    return [t.strip().lower() for t in re.split(r"[,;\n]+", raw or "") if t.strip()]


def contains_any(text: str, terms: Iterable[str]) -> bool:
    value = str(text or "").lower()
    return any(term and term in value for term in terms)


def word_contains_any(text: str, terms: Iterable[str]) -> bool:
    value = str(text or "").lower()
    for term in terms:
        term = term.strip().lower()
        if not term:
            continue
        # phrase terms should match phrase; one-word terms get word-ish boundary.
        if " " in term or "'" in term:
            if term in value:
                return True
        elif re.search(rf"\b{re.escape(term)}s?\b", value):
            return True
    return False


def intent_bucket(keyword: str) -> str:
    k = keyword.lower()

    if re.search(r"\b(menu|menus|prices|price|specials?|daily specials?)\b", k):
        return "Menu / specials"
    if re.search(r"\b(near me|loves park|rockford|machesney|illinois| il\b|riverside)\b", k):
        return "Local discovery"
    if re.search(r"\b(fish fry|hot dog|hot dogs|sandwich|sandwiches|wings?|burger|pizza|food|apps|appetizers?)\b", k):
        return "Food item"
    if re.search(r"\b(event|events|private|party|banquet|catering|live music|music bingo|singo|bingo|band)\b", k):
        return "Events"
    if re.search(r"\b(hours|open|closed|photos|photo|pictures|address|phone|contact)\b", k):
        return "Info / navigation"
    if re.search(r"\b(job|jobs|hiring|apply|application|career|careers)\b", k):
        return "Hiring"
    return "General"


def action_type(row) -> str:
    if row["is_noise"]:
        return "Review / exclude noise"
    if row["is_brand"]:
        return "Protect brand SERP"
    if row["intent"] == "Menu / specials":
        return "Improve menu page"
    if row["intent"] == "Local discovery":
        return "Optimize local landing page"
    if row["intent"] == "Food item":
        return "Build food-item section"
    if row["intent"] == "Events":
        return "Build events content"
    if row["intent"] == "Hiring":
        return "Improve hiring page"
    return "Keyword review"


def normalize_series(s: pd.Series) -> pd.Series:
    if s.empty:
        return s
    s = s.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)
    if s.max() == s.min():
        return pd.Series(np.where(s.max() > 0, 1.0, 0.0), index=s.index)
    return (s - s.min()) / (s.max() - s.min())


def suggest_title(page_title: str, keyword: str, action: str) -> str:
    kw = keyword.title()
    if action == "Improve menu page":
        return f"{kw} | Fozzy's Bar & Restaurant"
    if action == "Optimize local landing page":
        return f"{kw} | Fozzy's Bar in Loves Park, IL"
    if action == "Build food-item section":
        return f"{kw} in Loves Park & Rockford | Fozzy's"
    if action == "Build events content":
        return f"{kw} at Fozzy's | Events in Loves Park"
    if action == "Protect brand SERP":
        return page_title if page_title else f"{kw} | Official Fozzy's Bar & Restaurant"
    return page_title if page_title else f"{kw} | Fozzy's"


def suggest_meta(keyword: str, intent: str) -> str:
    kw = keyword.lower()
    if intent == "Menu / specials":
        return f"Explore Fozzy's {kw}, daily specials, drinks, and scratch-made favorites in Loves Park, IL."
    if intent == "Local discovery":
        return f"Looking for {kw}? Visit Fozzy's for food, drinks, events, and a lively local bar and restaurant experience."
    if intent == "Food item":
        return f"Craving {kw}? See Fozzy's food options, specials, and reasons locals choose us in Loves Park."
    if intent == "Events":
        return f"Discover {kw} at Fozzy's, including live entertainment, music bingo, private events, and upcoming specials."
    if intent == "Info / navigation":
        return f"Find Fozzy's {kw} details, including location, hours, menu, specials, and contact information."
    return f"Learn more about {kw} at Fozzy's Bar & Restaurant in Loves Park, IL."


def enrich_keywords(df: pd.DataFrame, pages: pd.DataFrame, brand_terms: List[str], noise_terms: List[str]) -> pd.DataFrame:
    out = df.copy()
    out["keyword"] = out["keyword"].fillna("").astype(str)
    out["kw_lower"] = out["keyword"].str.lower()
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype(int)
    out["cpc"] = pd.to_numeric(out["cpc"], errors="coerce").fillna(0.0).astype(float)

    out["intent"] = out["keyword"].map(intent_bucket)
    out["is_brand"] = out["keyword"].map(lambda x: word_contains_any(x, brand_terms))
    out["is_noise"] = out.apply(
        lambda r: (not r["is_brand"]) and word_contains_any(r["keyword"], noise_terms),
        axis=1,
    )

    out["keyword_in_title"] = out.apply(lambda r: contains_any(r["page_title"], [r["keyword"].lower()]), axis=1)
    out["keyword_in_h1"] = out.apply(lambda r: contains_any(r["h1"], [r["keyword"].lower()]), axis=1)
    out["keyword_in_url"] = out.apply(lambda r: contains_any(r["url"], [slugish(r["keyword"])]), axis=1)

    out["missing_onpage_signal"] = ~(out["keyword_in_title"] | out["keyword_in_h1"] | out["keyword_in_url"])

    # Better practical score than raw volume:
    # volume matters, CPC helps commercial value, local/menu/food/events intent helps usefulness,
    # missing on-page coverage boosts actionability, and noise gets heavily penalized.
    vol_score = normalize_series(np.log1p(out["volume"])) * 45
    cpc_score = normalize_series(np.log1p(out["cpc"])) * 20
    intent_bonus = out["intent"].map(
        {
            "Local discovery": 15,
            "Menu / specials": 14,
            "Food item": 13,
            "Events": 10,
            "Info / navigation": 7,
            "Hiring": 5,
            "General": 4,
        }
    ).fillna(4)
    gap_bonus = np.where(out["missing_onpage_signal"], 12, 3)
    brand_bonus = np.where(out["is_brand"], 4, 0)
    noise_penalty = np.where(out["is_noise"], 45, 0)

    out["opportunity_score"] = (vol_score + cpc_score + intent_bonus + gap_bonus + brand_bonus - noise_penalty).clip(0, 100).round(1)
    out["estimated_value"] = (out["volume"] * (out["cpc"].replace(0, 0.05))).round(2)
    out["action"] = out.apply(action_type, axis=1)
    out["priority"] = pd.cut(
        out["opportunity_score"],
        bins=[-1, 35, 65, 100],
        labels=["Low", "Medium", "High"],
    ).astype(str)
    out["recommended_title"] = out.apply(lambda r: suggest_title(r["page_title"], r["keyword"], r["action"]), axis=1)
    out["recommended_meta"] = out.apply(lambda r: suggest_meta(r["keyword"], r["intent"]), axis=1)
    out["reason"] = out.apply(reason_for_row, axis=1)
    return out


def slugish(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def reason_for_row(row) -> str:
    pieces = []
    if row["volume"] >= 1000:
        pieces.append("high volume")
    elif row["volume"] >= 100:
        pieces.append("meaningful volume")
    if row["cpc"] >= 1:
        pieces.append("commercial CPC")
    if row["missing_onpage_signal"]:
        pieces.append("weak title/H1/URL alignment")
    if row["is_noise"]:
        pieces.append("likely competitor/noise term")
    if row["is_brand"]:
        pieces.append("brand demand")
    if not pieces:
        pieces.append("needs manual review")
    return ", ".join(pieces)


def page_summary(enriched: pd.DataFrame, pages: pd.DataFrame) -> pd.DataFrame:
    summary = (
        enriched.assign(non_noise_volume=np.where(~enriched["is_noise"], enriched["volume"], 0),
                        brand_volume=np.where(enriched["is_brand"], enriched["volume"], 0),
                        high_priority_keywords=np.where(enriched["priority"] == "High", 1, 0),
                        missing_onpage_count=np.where(enriched["missing_onpage_signal"], 1, 0))
        .groupby("url", dropna=False)
        .agg(
            keywords=("keyword", "count"),
            total_volume=("volume", "sum"),
            non_noise_volume=("non_noise_volume", "sum"),
            brand_volume=("brand_volume", "sum"),
            avg_cpc=("cpc", "mean"),
            max_cpc=("cpc", "max"),
            avg_score=("opportunity_score", "mean"),
            high_priority_keywords=("high_priority_keywords", "sum"),
            missing_onpage_count=("missing_onpage_count", "sum"),
            top_keyword=("keyword", lambda s: s.iloc[enriched.loc[s.index, "volume"].argmax()] if len(s) else ""),
        )
        .reset_index()
    )
    metadata = pages.rename(columns={"title": "page_title"})
    summary = summary.merge(metadata, on="url", how="left")
    summary["title_length"] = summary["page_title"].fillna("").str.len()
    summary["meta_length"] = summary["meta_description"].fillna("").str.len()
    summary["recommended_focus"] = summary.apply(page_recommendation, axis=1)
    return summary.sort_values(["avg_score", "non_noise_volume"], ascending=False)


def page_recommendation(row) -> str:
    if row["high_priority_keywords"] >= 3 and row["missing_onpage_count"] >= 3:
        return "Rewrite title/H1 and add supporting sections for top terms"
    if row["non_noise_volume"] > 1000:
        return "Prioritize this page; it has real demand after noise filtering"
    if row["brand_volume"] > 1000:
        return "Protect brand terms; improve brand SERP clarity"
    if row["meta_length"] < 120:
        return "Expand meta description for better SERP message"
    return "Monitor / low immediate priority"


def build_action_plan(enriched: pd.DataFrame, max_rows: int = 30) -> pd.DataFrame:
    useful = enriched.copy()
    # Keep high-priority rows first, then rank by score and demand.
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    useful["_priority_rank"] = useful["priority"].map(priority_order).fillna(9)
    useful = useful.sort_values(
        ["_priority_rank", "opportunity_score", "volume", "cpc"],
        ascending=[True, False, False, False],
    )
    useful["rank"] = range(1, len(useful) + 1)

    cols = [
        "rank",
        "priority",
        "opportunity_score",
        "action",
        "url",
        "keyword",
        "intent",
        "volume",
        "cpc",
        "reason",
        "recommended_title",
        "recommended_meta",
    ]
    return useful[cols].head(max_rows)


def make_content_brief(enriched: pd.DataFrame, url: str) -> dict:
    page_df = enriched[enriched["url"] == url].sort_values(["opportunity_score", "volume"], ascending=False)
    if page_df.empty:
        return {}

    non_noise = page_df[~page_df["is_noise"]]
    source = non_noise if not non_noise.empty else page_df

    primary = source.iloc[0]
    secondary = source[source["keyword"] != primary["keyword"]].head(8)

    sections = []
    if (source["intent"] == "Menu / specials").any():
        sections.extend(["Menu highlights", "Daily specials", "Popular food and drink categories"])
    if (source["intent"] == "Local discovery").any():
        sections.extend(["Why locals choose this restaurant", "Location and nearby areas served"])
    if (source["intent"] == "Food item").any():
        sections.extend(["Featured dishes", "Best pairings and specials"])
    if (source["intent"] == "Events").any():
        sections.extend(["Upcoming events", "Private events and entertainment"])
    if not sections:
        sections.extend(["Overview", "Why visit", "Frequently asked questions"])

    questions = []
    for kw in source["keyword"].head(12):
        k = kw.lower()
        if "menu" in k:
            questions.append(f"What is on the {kw}?")
        elif "hours" in k:
            questions.append(f"What are Fozzy's hours?")
        elif "near me" in k or "loves park" in k or "rockford" in k:
            questions.append(f"Is Fozzy's a good option for {kw}?")
        elif "event" in k or "bingo" in k or "music" in k:
            questions.append(f"When is the next {kw} event?")
        elif "fish fry" in k:
            questions.append("Does Fozzy's offer a fish fry?")
    questions = list(dict.fromkeys(questions))[:5]

    return {
        "primary_keyword": primary["keyword"],
        "recommended_title": primary["recommended_title"],
        "recommended_meta": primary["recommended_meta"],
        "secondary_keywords": ", ".join(secondary["keyword"].tolist()),
        "sections": sections,
        "faqs": questions,
    }


# =============================================================================
# UI
# =============================================================================
st.markdown(
    """
    <div class="hero">
        <h1>🎯 SEO Opportunity Command Center</h1>
        <p>Upload your audit CSV, separate real SEO opportunities from noisy keywords, and get a ranked action plan instead of just charts.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("1. Upload")
    uploaded = st.file_uploader("Upload SEO audit CSV", type=["csv"])

    st.header("2. Tune the analysis")
    brand_terms_raw = st.text_area("Brand terms", DEFAULT_BRAND_TERMS, help="Terms that represent the target brand. Used to protect brand demand.")
    noise_terms_raw = st.text_area(
        "Competitor / noise terms",
        DEFAULT_NOISE_TERMS,
        help="Terms to down-rank or exclude when they are likely competitors, misspellings, unrelated brands, or bad-fit keywords.",
    )
    min_volume = st.slider("Minimum keyword volume", 0, 5000, 0, step=10)
    min_cpc = st.slider("Minimum CPC", 0.0, 10.0, 0.0, step=0.05)
    exclude_noise = st.checkbox("Hide competitor/noise keywords", value=False)
    show_rows = st.slider("Rows in action plan", 10, 100, 30, step=5)

    st.header("3. Views")
    chart_theme = st.selectbox("Color view", ["Opportunity score", "Intent", "Action"], index=0)

if not uploaded:
    st.info("Upload the CSV to generate the dashboard. This app expects the sectioned export with Group → page row → Keyword rows, but also handles simple flat keyword CSVs.")
    st.stop()

try:
    raw_keywords, pages, meta = parse_audit_csv(uploaded.getvalue())
except Exception as exc:
    st.error(f"Could not parse the CSV: {exc}")
    st.stop()

brand_terms = split_terms(brand_terms_raw)
noise_terms = split_terms(noise_terms_raw)

enriched = enrich_keywords(raw_keywords, pages, brand_terms, noise_terms)

filtered = enriched[(enriched["volume"] >= min_volume) & (enriched["cpc"] >= min_cpc)].copy()
if exclude_noise:
    filtered = filtered[~filtered["is_noise"]].copy()

if filtered.empty:
    st.warning("No keywords match the current filters.")
    st.stop()

pages_view = page_summary(filtered, pages)
action_plan = build_action_plan(filtered, show_rows)

# -----------------------------------------------------------------------------
# EXECUTIVE SUMMARY
# -----------------------------------------------------------------------------
total_volume = int(filtered["volume"].sum())
non_noise_volume = int(filtered.loc[~filtered["is_noise"], "volume"].sum())
noise_volume = int(filtered.loc[filtered["is_noise"], "volume"].sum())
brand_volume = int(filtered.loc[filtered["is_brand"], "volume"].sum())
high_count = int((filtered["priority"] == "High").sum())
quick_win_count = int(((filtered["priority"] == "High") & (~filtered["is_noise"]) & (filtered["missing_onpage_signal"])).sum())

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Keywords", f"{len(filtered):,}")
m2.metric("Total volume", f"{total_volume:,}")
m3.metric("Useful volume", f"{non_noise_volume:,}", help="Volume after excluding configured competitor/noise terms.")
m4.metric("High-priority terms", f"{high_count:,}")
m5.metric("On-page quick wins", f"{quick_win_count:,}", help="High-priority, non-noise keywords with weak title/H1/URL alignment.")

st.markdown('<div class="section-title">What this data is saying</div>', unsafe_allow_html=True)

top_page = pages_view.iloc[0] if not pages_view.empty else None
top_kw = filtered.sort_values(["opportunity_score", "volume"], ascending=False).iloc[0]
noise_share = noise_volume / total_volume if total_volume else 0

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f"""
        <div class="insight-card">
            <h3>Best page to work on</h3>
            <p><b>{top_page['url'] if top_page is not None else 'N/A'}</b><br>
            {int(top_page['non_noise_volume']) if top_page is not None else 0:,} useful monthly search volume. Recommended move: {top_page['recommended_focus'] if top_page is not None else 'N/A'}.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"""
        <div class="insight-card">
            <h3>Biggest keyword opportunity</h3>
            <p><b>{top_kw['keyword']}</b><br>
            Score {top_kw['opportunity_score']}/100, volume {int(top_kw['volume']):,}, CPC ${top_kw['cpc']:.2f}. Action: {top_kw['action']}.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f"""
        <div class="insight-card">
            <h3>Noise warning</h3>
            <p><b>{noise_share:.0%}</b> of visible volume is marked as competitor/noise by your settings. Do not build your SEO roadmap from raw volume alone.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# ACTION PLAN
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Ranked action plan</div>', unsafe_allow_html=True)
st.caption("This is the main useful output: a prioritized list of what to optimize, build, protect, or ignore.")

st.dataframe(
    action_plan,
    use_container_width=True,
    hide_index=True,
    column_config={
        "rank": st.column_config.NumberColumn("#", width="small"),
        "priority": st.column_config.TextColumn("Priority", width="small"),
        "opportunity_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
        "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
        "volume": st.column_config.NumberColumn("Volume", format="%d"),
        "recommended_meta": st.column_config.TextColumn("Recommended meta", width="large"),
        "recommended_title": st.column_config.TextColumn("Recommended title", width="large"),
    },
)

# -----------------------------------------------------------------------------
# CHARTS
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Opportunity map</div>', unsafe_allow_html=True)

left, right = st.columns([1.05, 1])
with left:
    color_col = {
        "Opportunity score": "opportunity_score",
        "Intent": "intent",
        "Action": "action",
    }[chart_theme]

    scatter = px.scatter(
        filtered,
        x="volume",
        y="cpc",
        size="opportunity_score",
        color=color_col,
        hover_name="keyword",
        hover_data=["url", "intent", "action", "priority", "is_noise"],
        log_x=True if filtered["volume"].max() > 100 else False,
        title="Keyword value map",
    )
    scatter.update_layout(height=480, margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(scatter, use_container_width=True)

with right:
    page_bar = pages_view.sort_values("non_noise_volume", ascending=True).tail(15)
    fig = px.bar(
        page_bar,
        x="non_noise_volume",
        y="url",
        orientation="h",
        color="avg_score",
        hover_data=["keywords", "high_priority_keywords", "recommended_focus"],
        title="Best pages after noise filtering",
    )
    fig.update_layout(height=480, margin=dict(l=10, r=10, t=45, b=10), yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

left2, right2 = st.columns([1, 1])
with left2:
    intent = filtered.groupby("intent", as_index=False).agg(volume=("volume", "sum"), keywords=("keyword", "count"))
    fig_intent = px.treemap(intent, path=["intent"], values="volume", color="keywords", title="Demand by search intent")
    fig_intent.update_layout(height=430, margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(fig_intent, use_container_width=True)

with right2:
    action = filtered.groupby("action", as_index=False).agg(volume=("volume", "sum"), keywords=("keyword", "count"))
    fig_action = px.bar(action.sort_values("volume"), x="volume", y="action", orientation="h", color="keywords", title="Demand by recommended action")
    fig_action.update_layout(height=430, margin=dict(l=10, r=10, t=45, b=10), yaxis_title="")
    st.plotly_chart(fig_action, use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE AUDIT
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Page-level SEO audit</div>', unsafe_allow_html=True)
st.caption("Use this to decide which existing pages should be rewritten before creating new content.")

page_cols = [
    "url",
    "recommended_focus",
    "non_noise_volume",
    "total_volume",
    "keywords",
    "avg_score",
    "high_priority_keywords",
    "missing_onpage_count",
    "top_keyword",
    "page_title",
    "h1",
    "meta_description",
    "title_length",
    "meta_length",
]
st.dataframe(
    pages_view[page_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "avg_score": st.column_config.ProgressColumn("Avg score", min_value=0, max_value=100),
        "non_noise_volume": st.column_config.NumberColumn("Useful volume", format="%d"),
        "total_volume": st.column_config.NumberColumn("Raw volume", format="%d"),
        "title_length": st.column_config.NumberColumn("Title len", format="%d"),
        "meta_length": st.column_config.NumberColumn("Meta len", format="%d"),
    },
)

# -----------------------------------------------------------------------------
# CONTENT BRIEF
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">One-page content brief generator</div>', unsafe_allow_html=True)
st.caption("Pick a URL and get a practical brief based on the best matched keywords.")

url_options = pages_view["url"].tolist()
selected_url = st.selectbox("Choose a page", url_options)
brief = make_content_brief(filtered, selected_url)

if brief:
    b1, b2 = st.columns([1, 1])
    with b1:
        st.subheader("Recommended SEO brief")
        st.write(f"**Primary keyword:** {brief['primary_keyword']}")
        st.write(f"**SEO title:** {brief['recommended_title']}")
        st.write(f"**Meta description:** {brief['recommended_meta']}")
        st.write(f"**Secondary keywords:** {brief['secondary_keywords'] or 'None'}")
    with b2:
        st.subheader("Suggested structure")
        for section in brief["sections"]:
            st.write(f"- {section}")
        if brief["faqs"]:
            st.write("**FAQ ideas**")
            for q in brief["faqs"]:
                st.write(f"- {q}")

# -----------------------------------------------------------------------------
# RAW / EXPORTS
# -----------------------------------------------------------------------------
st.markdown('<div class="section-title">Keyword triage table</div>', unsafe_allow_html=True)

keyword_cols = [
    "priority",
    "opportunity_score",
    "action",
    "keyword",
    "url",
    "intent",
    "volume",
    "cpc",
    "is_brand",
    "is_noise",
    "missing_onpage_signal",
    "reason",
]
st.dataframe(
    filtered.sort_values(["opportunity_score", "volume"], ascending=False)[keyword_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "opportunity_score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
        "volume": st.column_config.NumberColumn("Volume", format="%d"),
        "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
    },
)

d1, d2, d3 = st.columns(3)
with d1:
    st.download_button(
        "Download action plan CSV",
        data=action_plan.to_csv(index=False).encode("utf-8"),
        file_name="seo_action_plan.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d2:
    st.download_button(
        "Download enriched keywords CSV",
        data=filtered.to_csv(index=False).encode("utf-8"),
        file_name="seo_keywords_enriched.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d3:
    st.download_button(
        "Download page audit CSV",
        data=pages_view.to_csv(index=False).encode("utf-8"),
        file_name="seo_page_audit.csv",
        mime="text/csv",
        use_container_width=True,
    )

with st.expander("Scoring notes"):
    st.markdown(
        """
        **Opportunity score** combines log-scaled search volume, CPC, practical intent, missing on-page alignment, and a penalty for configured competitor/noise terms.

        This is intentionally not a pure traffic score. SEO dashboards become useless when they reward huge irrelevant keywords. The goal is to rank work that could actually help the site.
        """
    )

import csv
import html
import io
import math
import re
from pathlib import Path
from typing import Iterable, List, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# =============================================================================
# CONFIG
# =============================================================================
st.set_page_config(
    page_title="Local SEO Action Dashboard",
    page_icon="📍",
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
    .block-container { padding-top: 1.25rem; padding-bottom: 4rem; }
    div[data-testid="stMetric"] {
        background: linear-gradient(180deg, rgba(25,31,48,.98), rgba(16,20,31,.98));
        border: 1px solid rgba(150, 170, 255, .18);
        border-radius: 16px;
        padding: 16px 16px 12px 16px;
        box-shadow: 0 10px 28px rgba(0,0,0,.16);
    }
    div[data-testid="stMetric"] label { color: #AAB4D4 !important; }
    .hero {
        padding: 24px 26px;
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(48,104,255,.20), rgba(87,220,180,.09));
        border: 1px solid rgba(160, 180, 255, .20);
        margin-bottom: 18px;
    }
    .hero h1 { margin: 0; font-size: 2.1rem; letter-spacing: -.035em; }
    .hero p { margin: .45rem 0 0 0; color: #B9C3DA; font-size: 1.02rem; max-width: 980px; }
    .section-title {
        font-size: 1.32rem;
        font-weight: 800;
        letter-spacing: -.015em;
        margin-top: 2rem;
        margin-bottom: .35rem;
    }
    .plain-card {
        border: 1px solid rgba(160, 180, 255, .17);
        border-radius: 18px;
        padding: 17px 18px;
        background: rgba(255,255,255,.035);
        min-height: 132px;
    }
    .plain-card h3 { margin-top: 0; font-size: 1.02rem; }
    .plain-card p { color: #BCC7E0; margin-bottom: 0; }
    .answer-box {
        border-left: 4px solid rgba(100, 190, 255, .92);
        padding: 10px 14px;
        border-radius: 10px;
        background: rgba(100, 190, 255, .07);
        color: #D8E4FF;
        margin: .5rem 0 1rem 0;
    }
    .small-muted { color: #9CA8C4; font-size: .9rem; }
    .stDownloadButton button, .stButton button {
        border-radius: 12px !important;
        font-weight: 650 !important;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
# LOCAL FILE DISCOVERY
# =============================================================================
def app_directory() -> Path:
    """Return the folder where this Streamlit script lives."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd().resolve()


def list_csv_files(folder: str, recursive: bool = False) -> List[Path]:
    """List CSV files from a server-side folder for local Streamlit use."""
    if not folder:
        return []

    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return []

    pattern = "**/*.csv" if recursive else "*.csv"
    files = [p for p in root.glob(pattern) if p.is_file()]
    return sorted(files, key=lambda p: (p.name.lower(), str(p.parent).lower()))[:500]


def read_local_csv_bytes(path: Path) -> bytes:
    return path.read_bytes()


def path_label(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


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

    # Fallback for ordinary flat CSVs.
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
        if " " in term or "'" in term:
            if term in value:
                return True
        elif re.search(rf"\b{re.escape(term)}s?\b", value):
            return True
    return False


def slugish(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def page_name(url: str) -> str:
    """Turn a URL into a friendly page label for charts."""
    url = str(url or "").strip()
    if not url:
        return "Unassigned page"
    parsed = urlparse(url if re.match(r"^https?://", url) else "https://" + url)
    path = parsed.path.strip("/")
    if not path:
        return "Homepage"
    label = path.split("/")[-1].replace("-", " ").replace("_", " ").strip()
    return label.title() if label else "Homepage"


def intent_bucket(keyword: str) -> str:
    k = keyword.lower()

    if re.search(r"\b(menu|menus|prices|price|specials?|daily specials?|happy hour|drinks?|beer|cocktail)\b", k):
        return "Menu / specials"
    if re.search(r"\b(near me|loves park|rockford|machesney|illinois| il\b|riverside|restaurant|restaurants|bar and grill|bar & grill|sports bar|local bar)\b", k):
        return "Local discovery"
    if re.search(r"\b(fish fry|hot dog|hot dogs|sandwich|sandwiches|wings?|burger|pizza|food|apps|appetizers?|tacos?|fries|salad|wrap)\b", k):
        return "Food item"
    if re.search(r"\b(event|events|private|party|banquet|catering|live music|music bingo|singo|bingo|band|trivia|karaoke)\b", k):
        return "Events"
    if re.search(r"\b(hours|open|closed|photos|photo|pictures|address|phone|contact|directions|reviews?)\b", k):
        return "Info / navigation"
    if re.search(r"\b(job|jobs|hiring|apply|application|career|careers)\b", k):
        return "Hiring"
    return "Other"


def customer_need(row) -> str:
    """Plain-language bucket a business owner can understand."""
    if row.get("is_noise", False):
        return "Bad-fit or competitor searches"
    if row.get("is_brand", False):
        return "People searching for us by name"

    intent = row.get("intent", "Other")
    mapping = {
        "Menu / specials": "Menu, prices or specials",
        "Local discovery": "Looking for a place nearby",
        "Food item": "Specific food or drinks",
        "Events": "Events, parties or catering",
        "Info / navigation": "Hours, photos, contact or reviews",
        "Hiring": "Jobs and hiring",
        "Other": "Other searches to review",
    }
    return mapping.get(intent, "Other searches to review")


def owner_action(row) -> str:
    if row.get("is_noise", False):
        return "Ignore or exclude"
    if row.get("is_brand", False):
        return "Make brand info airtight"

    intent = row.get("intent", "Other")
    mapping = {
        "Menu / specials": "Improve menu/specials page",
        "Local discovery": "Improve homepage/local page",
        "Food item": "Add food/drink content",
        "Events": "Add events/private party content",
        "Info / navigation": "Clean up hours/contact/photos",
        "Hiring": "Improve hiring page",
        "Other": "Review keyword manually",
    }
    return mapping.get(intent, "Review keyword manually")


def work_type(row) -> str:
    if row.get("is_noise", False):
        return "Ignore"
    if row.get("is_brand", False) or row.get("intent") == "Info / navigation":
        return "Fix existing info"
    if row.get("intent") in {"Menu / specials", "Local discovery"}:
        return "Fix existing page"
    if row.get("intent") in {"Food item", "Events", "Hiring"}:
        return "Add or expand content"
    return "Review"


def normalize_series(s: pd.Series) -> pd.Series:
    if s.empty:
        return s
    s = s.astype(float).replace([np.inf, -np.inf], np.nan).fillna(0)
    if s.max() == s.min():
        return pd.Series(np.where(s.max() > 0, 1.0, 0.0), index=s.index)
    return (s - s.min()) / (s.max() - s.min())


def suggest_title(page_title: str, keyword: str, action: str) -> str:
    kw = keyword.title()
    if action == "Improve menu/specials page":
        return f"{kw} | Fozzy's Bar & Restaurant"
    if action == "Improve homepage/local page":
        return f"{kw} | Fozzy's Bar in Loves Park, IL"
    if action == "Add food/drink content":
        return f"{kw} in Loves Park & Rockford | Fozzy's"
    if action == "Add events/private party content":
        return f"{kw} at Fozzy's | Events in Loves Park"
    if action == "Make brand info airtight":
        return page_title if page_title else f"{kw} | Official Fozzy's Bar & Restaurant"
    return page_title if page_title else f"{kw} | Fozzy's"


def suggest_meta(keyword: str, need: str) -> str:
    kw = keyword.lower()
    if need == "Menu, prices or specials":
        return f"Explore Fozzy's {kw}, daily specials, drinks, and local favorites in Loves Park, IL."
    if need == "Looking for a place nearby":
        return f"Looking for {kw}? Visit Fozzy's for food, drinks, events, and a lively local bar and restaurant experience."
    if need == "Specific food or drinks":
        return f"Craving {kw}? See Fozzy's food options, specials, and reasons locals choose us in Loves Park."
    if need == "Events, parties or catering":
        return f"Discover {kw} at Fozzy's, including live entertainment, music bingo, private events, and upcoming specials."
    if need == "Hours, photos, contact or reviews":
        return f"Find Fozzy's {kw} details, including location, hours, menu, specials, and contact information."
    return f"Learn more about {kw} at Fozzy's Bar & Restaurant in Loves Park, IL."


def reason_for_row(row) -> str:
    pieces = []
    if row["volume"] >= 1000:
        pieces.append("lots of searches")
    elif row["volume"] >= 100:
        pieces.append("meaningful searches")
    if row["cpc"] >= 1:
        pieces.append("advertisers pay for this")
    if row["missing_onpage_signal"]:
        pieces.append("page does not clearly target it")
    if row["is_noise"]:
        pieces.append("probably not your customer")
    if row["is_brand"]:
        pieces.append("people already know the business")
    if not pieces:
        pieces.append("worth a quick manual check")
    return ", ".join(pieces)


def enrich_keywords(df: pd.DataFrame, pages: pd.DataFrame, brand_terms: List[str], noise_terms: List[str]) -> pd.DataFrame:
    out = df.copy()
    out["keyword"] = out["keyword"].fillna("").astype(str)
    out["kw_lower"] = out["keyword"].str.lower()
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype(int)
    out["cpc"] = pd.to_numeric(out["cpc"], errors="coerce").fillna(0.0).astype(float)

    out["intent"] = out["keyword"].map(intent_bucket)
    out["is_brand"] = out["keyword"].map(lambda x: word_contains_any(x, brand_terms))
    out["is_noise"] = out.apply(lambda r: (not r["is_brand"]) and word_contains_any(r["keyword"], noise_terms), axis=1)

    out["keyword_in_title"] = out.apply(lambda r: contains_any(r["page_title"], [r["keyword"].lower()]), axis=1)
    out["keyword_in_h1"] = out.apply(lambda r: contains_any(r["h1"], [r["keyword"].lower()]), axis=1)
    out["keyword_in_url"] = out.apply(lambda r: contains_any(r["url"], [slugish(r["keyword"])]), axis=1)
    out["missing_onpage_signal"] = ~(out["keyword_in_title"] | out["keyword_in_h1"] | out["keyword_in_url"])

    vol_score = normalize_series(np.log1p(out["volume"])) * 45
    cpc_score = normalize_series(np.log1p(out["cpc"])) * 20
    intent_bonus = out["intent"].map(
        {
            "Local discovery": 16,
            "Menu / specials": 15,
            "Food item": 13,
            "Events": 11,
            "Info / navigation": 8,
            "Hiring": 5,
            "Other": 4,
        }
    ).fillna(4)
    gap_bonus = np.where(out["missing_onpage_signal"], 13, 3)
    brand_bonus = np.where(out["is_brand"], 5, 0)
    noise_penalty = np.where(out["is_noise"], 50, 0)

    out["opportunity_score"] = (vol_score + cpc_score + intent_bonus + gap_bonus + brand_bonus - noise_penalty).clip(0, 100).round(1)
    out["customer_need"] = out.apply(customer_need, axis=1)
    out["owner_action"] = out.apply(owner_action, axis=1)
    out["work_type"] = out.apply(work_type, axis=1)

    # Owner priority is intentionally different from raw opportunity. It favors work that a local owner can actually act on.
    owner_boost = np.where((~out["is_brand"]) & (~out["is_noise"]) & out["missing_onpage_signal"], 12, 0)
    owner_boost += np.where(out["intent"].isin(["Menu / specials", "Local discovery", "Food item", "Events"]), 7, 0)
    owner_penalty = np.where(out["is_noise"], 60, 0) + np.where((out["is_brand"]) & (~out["missing_onpage_signal"]), 18, 0)
    out["owner_priority_score"] = (out["opportunity_score"] + owner_boost - owner_penalty).clip(0, 100).round(1)

    out["estimated_ad_value"] = (out["volume"] * (out["cpc"].replace(0, 0.05))).round(2)
    out["priority"] = pd.cut(out["owner_priority_score"], bins=[-1, 35, 65, 100], labels=["Low", "Medium", "High"]).astype(str)
    out["recommended_title"] = out.apply(lambda r: suggest_title(r["page_title"], r["keyword"], r["owner_action"]), axis=1)
    out["recommended_meta"] = out.apply(lambda r: suggest_meta(r["keyword"], r["customer_need"]), axis=1)
    out["reason"] = out.apply(reason_for_row, axis=1)
    out["page"] = out["url"].map(page_name)
    out["keyword_label"] = out["keyword"].str.slice(0, 55)
    return out


def top_examples(df: pd.DataFrame, n: int = 3) -> str:
    if df.empty:
        return ""
    values = df.sort_values("volume", ascending=False)["keyword"].dropna().astype(str).head(n).tolist()
    return ", ".join(values)


def page_recommendation(row) -> str:
    if row["growth_volume"] >= 1000 and row["quick_wins"] >= 3:
        return "Fix this page first: high non-brand demand and weak keyword coverage"
    if row["growth_volume"] >= 500:
        return "Improve this page: useful customer demand is already mapped here"
    if row["brand_volume"] >= 1000:
        return "Keep brand info clean: name, hours, photos, menu, contact"
    if row["missing_onpage_count"] >= 5:
        return "Rewrite title/H1 or split into a more focused page"
    if row["meta_length"] < 120:
        return "Improve the meta description"
    return "Monitor; not an urgent page"


def page_summary(enriched: pd.DataFrame, pages: pd.DataFrame) -> pd.DataFrame:
    working = enriched.copy()
    working["useful_volume"] = np.where(~working["is_noise"], working["volume"], 0)
    working["growth_volume"] = np.where((~working["is_noise"]) & (~working["is_brand"]), working["volume"], 0)
    working["brand_volume"] = np.where(working["is_brand"], working["volume"], 0)
    working["noise_volume"] = np.where(working["is_noise"], working["volume"], 0)
    working["quick_win"] = np.where((~working["is_noise"]) & (~working["is_brand"]) & working["missing_onpage_signal"] & (working["owner_priority_score"] >= 50), 1, 0)
    working["missing_onpage_count"] = np.where(working["missing_onpage_signal"], 1, 0)

    summary = (
        working.groupby("url", dropna=False)
        .agg(
            page=("page", "first"),
            keywords=("keyword", "count"),
            useful_volume=("useful_volume", "sum"),
            growth_volume=("growth_volume", "sum"),
            brand_volume=("brand_volume", "sum"),
            noise_volume=("noise_volume", "sum"),
            avg_cpc=("cpc", "mean"),
            max_cpc=("cpc", "max"),
            avg_score=("owner_priority_score", "mean"),
            quick_wins=("quick_win", "sum"),
            missing_onpage_count=("missing_onpage_count", "sum"),
            top_keyword=("keyword", lambda s: s.iloc[working.loc[s.index, "volume"].argmax()] if len(s) else ""),
            top_customer_need=("customer_need", lambda s: working.loc[s.index].groupby("customer_need")["volume"].sum().sort_values(ascending=False).index[0] if len(s) else ""),
        )
        .reset_index()
    )
    metadata = pages.rename(columns={"title": "page_title"})
    summary = summary.merge(metadata, on="url", how="left")
    summary["title_length"] = summary["page_title"].fillna("").str.len()
    summary["meta_length"] = summary["meta_description"].fillna("").str.len()
    summary["recommended_focus"] = summary.apply(page_recommendation, axis=1)
    return summary.sort_values(["quick_wins", "growth_volume", "useful_volume"], ascending=False)


def build_action_plan(enriched: pd.DataFrame, max_rows: int = 30, include_brand: bool = False) -> pd.DataFrame:
    useful = enriched[~enriched["is_noise"]].copy()
    if not include_brand:
        useful = useful[~useful["is_brand"]].copy()
    if useful.empty:
        useful = enriched.copy()

    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    useful["_priority_rank"] = useful["priority"].map(priority_order).fillna(9)
    useful = useful.sort_values(["_priority_rank", "owner_priority_score", "volume", "cpc"], ascending=[True, False, False, False])
    useful["rank"] = range(1, len(useful) + 1)

    cols = [
        "rank",
        "priority",
        "owner_priority_score",
        "owner_action",
        "work_type",
        "page",
        "url",
        "keyword",
        "customer_need",
        "volume",
        "cpc",
        "reason",
        "recommended_title",
        "recommended_meta",
    ]
    return useful[cols].head(max_rows)


def demand_by_customer_need(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("customer_need", as_index=False)
        .agg(volume=("volume", "sum"), keywords=("keyword", "count"), examples=("keyword", lambda s: top_examples(df.loc[s.index], 3)))
        .sort_values("volume", ascending=False)
    )
    total = grouped["volume"].sum()
    grouped["share"] = np.where(total > 0, grouped["volume"] / total, 0)
    grouped["label"] = grouped.apply(lambda r: f"{int(r['volume']):,} searches/mo • {r['share']:.0%}", axis=1)
    return grouped


def demand_by_work_type(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("work_type", as_index=False)
        .agg(volume=("volume", "sum"), keywords=("keyword", "count"), examples=("keyword", lambda s: top_examples(df.loc[s.index], 3)))
        .sort_values("volume", ascending=False)
    )
    total = grouped["volume"].sum()
    grouped["share"] = np.where(total > 0, grouped["volume"] / total, 0)
    grouped["label"] = grouped.apply(lambda r: f"{int(r['volume']):,} • {r['share']:.0%}", axis=1)
    return grouped


def make_content_brief(enriched: pd.DataFrame, url: str) -> dict:
    page_df = enriched[enriched["url"] == url].sort_values(["owner_priority_score", "volume"], ascending=False)
    if page_df.empty:
        return {}

    source = page_df[(~page_df["is_noise"]) & (~page_df["is_brand"])]
    if source.empty:
        source = page_df[~page_df["is_noise"]]
    if source.empty:
        source = page_df

    primary = source.iloc[0]
    secondary = source[source["keyword"] != primary["keyword"]].head(8)

    sections = []
    needs = set(source["customer_need"].tolist())
    if "Menu, prices or specials" in needs:
        sections.extend(["Menu highlights", "Daily specials", "Popular food and drink categories"])
    if "Looking for a place nearby" in needs:
        sections.extend(["Why locals choose us", "Areas served", "Location and parking"])
    if "Specific food or drinks" in needs:
        sections.extend(["Featured dishes", "Best-selling items", "Food and drink pairings"])
    if "Events, parties or catering" in needs:
        sections.extend(["Upcoming events", "Private parties", "Live entertainment"])
    if "Hours, photos, contact or reviews" in needs:
        sections.extend(["Hours", "Contact", "Photos", "Reviews"])
    if not sections:
        sections.extend(["Overview", "Why visit", "Frequently asked questions"])

    faqs = []
    for kw in source["keyword"].head(12):
        k = kw.lower()
        if "menu" in k:
            faqs.append(f"What is on the {kw}?")
        elif "hours" in k:
            faqs.append("What are the hours?")
        elif "near me" in k or "loves park" in k or "rockford" in k:
            faqs.append(f"Is this a good place for {kw}?")
        elif "event" in k or "bingo" in k or "music" in k:
            faqs.append(f"When is the next {kw} event?")
        elif "fish fry" in k:
            faqs.append("Do you offer a fish fry?")
    faqs = list(dict.fromkeys(faqs))[:5]

    return {
        "primary_keyword": primary["keyword"],
        "recommended_title": primary["recommended_title"],
        "recommended_meta": primary["recommended_meta"],
        "secondary_keywords": ", ".join(secondary["keyword"].tolist()),
        "sections": sections,
        "faqs": faqs,
    }


def plot_bar(df, x, y, title, color=None, text=None, hover_data=None, height=470):
    fig = px.bar(
        df,
        x=x,
        y=y,
        orientation="h",
        color=color,
        text=text,
        hover_data=hover_data,
        title=title,
    )
    fig.update_yaxes(autorange="reversed", title="")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=50, b=10), xaxis_title="Monthly searches" if x == "volume" else None)
    if text:
        fig.update_traces(textposition="outside", cliponaxis=False)
    return fig


# =============================================================================
# UI
# =============================================================================
st.markdown(
    """
    <div class="hero">
        <h1>📍 Local SEO Action Dashboard</h1>
        <p>Built for a regular local business owner: what should I fix first, what are customers searching for, and which pages need work?</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("1. Choose data source")
    data_source = st.radio("CSV source", ["Upload a CSV", "Open CSV from local folder"], horizontal=False)

    file_bytes = None
    source_name = None

    if data_source == "Upload a CSV":
        uploaded = st.file_uploader("Upload SEO audit CSV", type=["csv"])
        if uploaded is not None:
            file_bytes = uploaded.getvalue()
            source_name = uploaded.name
    else:
        default_dir = str(app_directory())
        local_dir = st.text_input(
            "Folder path",
            value=default_dir,
            help="This reads CSV files from the machine/server running Streamlit.",
        )
        recursive_lookup = st.checkbox("Include subfolders", value=False)
        root = Path(local_dir).expanduser()
        csv_files = list_csv_files(local_dir, recursive=recursive_lookup)

        if not root.exists():
            st.warning("That folder does not exist.")
        elif not csv_files:
            st.info("No CSV files found in that folder.")
        else:
            file_options = {path_label(path, root): path for path in csv_files}
            selected_label = st.selectbox("Available CSV files", list(file_options.keys()))
            selected_path = file_options[selected_label]
            try:
                file_bytes = read_local_csv_bytes(selected_path)
                source_name = str(selected_path)
                st.caption(f"Loaded: {selected_path.name}")
            except Exception as exc:
                st.error(f"Could not read selected file: {exc}")

    st.header("2. Clean up the data")
    brand_terms_raw = st.text_area("Business / brand terms", DEFAULT_BRAND_TERMS)
    noise_terms_raw = st.text_area(
        "Competitor, misspelling, or bad-fit terms",
        DEFAULT_NOISE_TERMS,
        help="These are not deleted. They are labeled so the charts do not trick you into chasing bad traffic.",
    )
    min_volume = st.slider("Minimum monthly searches", 0, 5000, 0, step=10)
    min_cpc = st.slider("Minimum CPC", 0.0, 10.0, 0.0, step=0.05)
    hide_noise = st.checkbox("Hide bad-fit/competitor searches", value=True)
    include_brand_in_opportunity = st.checkbox(
        "Include brand searches in 'what to fix first' charts",
        value=False,
        help="Brand searches matter, but they often overpower growth opportunities. Keep this off when planning new SEO work.",
    )
    show_rows = st.slider("Rows in action plan", 10, 100, 30, step=5)

if not file_bytes:
    st.info("Choose a CSV source to generate the dashboard. You can upload a new file or open an existing CSV from a local folder.")
    st.stop()

st.caption(f"Analyzing source: `{source_name}`")

try:
    raw_keywords, pages, meta = parse_audit_csv(file_bytes)
except Exception as exc:
    st.error(f"Could not parse the CSV: {exc}")
    st.stop()

brand_terms = split_terms(brand_terms_raw)
noise_terms = split_terms(noise_terms_raw)

enriched = enrich_keywords(raw_keywords, pages, brand_terms, noise_terms)

filtered = enriched[(enriched["volume"] >= min_volume) & (enriched["cpc"] >= min_cpc)].copy()
if hide_noise:
    filtered = filtered[~filtered["is_noise"]].copy()

if filtered.empty:
    st.warning("No keywords match the current filters.")
    st.stop()

owner_focus = filtered[~filtered["is_noise"]].copy()
if not include_brand_in_opportunity:
    owner_focus = owner_focus[~owner_focus["is_brand"]].copy()
if owner_focus.empty:
    owner_focus = filtered.copy()

pages_view = page_summary(filtered, pages)
owner_pages_view = page_summary(owner_focus, pages)
action_plan = build_action_plan(filtered, show_rows, include_brand=include_brand_in_opportunity)

# =============================================================================
# SUMMARY
# =============================================================================
total_volume = int(enriched["volume"].sum())
visible_volume = int(filtered["volume"].sum())
noise_volume_all = int(enriched.loc[enriched["is_noise"], "volume"].sum())
brand_volume = int(filtered.loc[filtered["is_brand"], "volume"].sum())
growth_volume = int(filtered.loc[(~filtered["is_noise"]) & (~filtered["is_brand"]), "volume"].sum())
quick_win_count = int(((owner_focus["missing_onpage_signal"]) & (owner_focus["owner_priority_score"] >= 50)).sum())

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Visible searches/mo", f"{visible_volume:,}")
m2.metric("Growth searches", f"{growth_volume:,}", help="Non-brand, non-noise demand. This is usually where new SEO growth comes from.")
m3.metric("Brand searches", f"{brand_volume:,}", help="People already searching for the business by name.")
m4.metric("Quick wins", f"{quick_win_count:,}", help="Useful terms with weak title/H1/URL coverage.")
m5.metric("Noise found", f"{noise_volume_all:,}", help="Bad-fit, competitor, misspelling, or unrelated volume based on your settings.")

best_task = action_plan.iloc[0] if not action_plan.empty else None
best_need = demand_by_customer_need(filtered[~filtered["is_noise"]]).iloc[0]
best_page = owner_pages_view.iloc[0] if not owner_pages_view.empty else None

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        f"""
        <div class="plain-card">
            <h3>1. Do first</h3>
            <p><b>{best_task['owner_action'] if best_task is not None else 'N/A'}</b><br>
            Keyword: {best_task['keyword'] if best_task is not None else 'N/A'}<br>
            Page: {best_task['page'] if best_task is not None else 'N/A'}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f"""
        <div class="plain-card">
            <h3>2. Biggest customer need</h3>
            <p><b>{best_need['customer_need']}</b><br>
            {int(best_need['volume']):,} searches/month<br>
            Examples: {best_need['examples']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f"""
        <div class="plain-card">
            <h3>3. Page to improve</h3>
            <p><b>{best_page['page'] if best_page is not None else 'N/A'}</b><br>
            {int(best_page['growth_volume']) if best_page is not None else 0:,} growth searches/month<br>
            {best_page['recommended_focus'] if best_page is not None else ''}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# =============================================================================
# OWNER QUESTIONS
# =============================================================================
tabs = st.tabs([
    "1) What should I fix first?",
    "2) What are customers searching for?",
    "3) Which pages need work?",
    "Action plan + exports",
])

with tabs[0]:
    st.markdown('<div class="section-title">Question 1: What should I fix first?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="answer-box">This chart ranks the work a local owner can actually do: improve a page, add a section, clean up business info, or review a bad keyword. It does not reward raw volume alone.</div>',
        unsafe_allow_html=True,
    )

    top_tasks = action_plan.head(15).copy()
    top_tasks["task"] = top_tasks.apply(lambda r: f"{r['keyword']}  →  {r['page']}", axis=1)
    fig_tasks = px.bar(
        top_tasks.sort_values("owner_priority_score", ascending=True),
        x="owner_priority_score",
        y="task",
        color="work_type",
        text="owner_action",
        hover_data=["volume", "cpc", "customer_need", "reason", "url"],
        title="Top SEO jobs to do first",
        labels={"owner_priority_score": "Priority score", "task": "Keyword → page", "work_type": "Work type"},
    )
    fig_tasks.update_layout(height=560, margin=dict(l=10, r=10, t=50, b=10))
    fig_tasks.update_traces(textposition="inside")
    st.plotly_chart(fig_tasks, use_container_width=True)

    st.subheader("Why these are first")
    st.dataframe(
        top_tasks[["rank", "priority", "owner_action", "keyword", "page", "volume", "cpc", "reason", "recommended_title"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "rank": st.column_config.NumberColumn("#", width="small"),
            "owner_action": st.column_config.TextColumn("Do this", width="medium"),
            "volume": st.column_config.NumberColumn("Searches/mo", format="%d"),
            "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
        },
    )

    work = demand_by_work_type(owner_focus)
    fig_work = plot_bar(
        work.sort_values("volume", ascending=True),
        x="volume",
        y="work_type",
        title="How much demand each type of work affects",
        color="work_type",
        text="label",
        hover_data=["keywords", "examples"],
        height=390,
    )
    st.plotly_chart(fig_work, use_container_width=True)

with tabs[1]:
    st.markdown('<div class="section-title">Question 2: What are customers actually searching for?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="answer-box">This replaces the confusing “search intent” treemap. Each bar is written in plain business language: what the customer probably wanted when they searched.</div>',
        unsafe_allow_html=True,
    )

    customer_df = demand_by_customer_need(filtered[~filtered["is_noise"]])
    fig_need = plot_bar(
        customer_df.sort_values("volume", ascending=True),
        x="volume",
        y="customer_need",
        title="Customer demand by plain-language need",
        color="customer_need",
        text="label",
        hover_data=["keywords", "examples"],
        height=500,
    )
    st.plotly_chart(fig_need, use_container_width=True)

    st.subheader("Examples inside each bucket")
    st.dataframe(
        customer_df[["customer_need", "volume", "share", "keywords", "examples"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "customer_need": st.column_config.TextColumn("Customer was looking for...", width="medium"),
            "volume": st.column_config.NumberColumn("Searches/mo", format="%d"),
            "share": st.column_config.ProgressColumn("Share", min_value=0, max_value=1, format="%.0%%"),
            "examples": st.column_config.TextColumn("Example searches", width="large"),
        },
    )

    brand_df = filtered[(filtered["is_brand"]) & (~filtered["is_noise"])].sort_values("volume", ascending=False).head(12)
    if not brand_df.empty:
        st.subheader("Brand searches: people already looking for you")
        st.caption("This is not usually new growth, but it matters because these people are close to visiting or calling.")
        st.dataframe(
            brand_df[["keyword", "volume", "cpc", "page", "owner_action", "reason"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "volume": st.column_config.NumberColumn("Searches/mo", format="%d"),
                "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
            },
        )

with tabs[2]:
    st.markdown('<div class="section-title">Question 3: Which pages need work?</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="answer-box">This looks at existing URLs and asks: where is useful demand already mapped, and where does the page fail to clearly target those searches?</div>',
        unsafe_allow_html=True,
    )

    page_chart = owner_pages_view.head(15).copy()
    fig_pages = px.bar(
        page_chart.sort_values("growth_volume", ascending=True),
        x="growth_volume",
        y="page",
        color="quick_wins",
        text="recommended_focus",
        hover_data=["url", "top_keyword", "top_customer_need", "keywords", "missing_onpage_count", "useful_volume", "brand_volume"],
        title="Pages with the most growth demand",
        labels={"growth_volume": "Non-brand searches/month", "quick_wins": "Quick wins", "page": "Page"},
    )
    fig_pages.update_layout(height=540, margin=dict(l=10, r=10, t=50, b=10))
    fig_pages.update_traces(textposition="inside")
    st.plotly_chart(fig_pages, use_container_width=True)

    st.subheader("Page diagnosis")
    page_cols = [
        "page",
        "recommended_focus",
        "growth_volume",
        "useful_volume",
        "brand_volume",
        "quick_wins",
        "missing_onpage_count",
        "top_customer_need",
        "top_keyword",
        "page_title",
        "h1",
        "meta_description",
        "url",
    ]
    st.dataframe(
        owner_pages_view[page_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "growth_volume": st.column_config.NumberColumn("Growth searches", format="%d"),
            "useful_volume": st.column_config.NumberColumn("Useful searches", format="%d"),
            "brand_volume": st.column_config.NumberColumn("Brand searches", format="%d"),
            "quick_wins": st.column_config.NumberColumn("Quick wins", format="%d"),
            "missing_onpage_count": st.column_config.NumberColumn("Weak matches", format="%d"),
            "recommended_focus": st.column_config.TextColumn("Recommended move", width="large"),
        },
    )

    st.subheader("One-page content brief")
    url_options = owner_pages_view["url"].tolist()
    selected_url = st.selectbox("Choose a page", url_options)
    brief = make_content_brief(filtered, selected_url)

    if brief:
        b1, b2 = st.columns([1, 1])
        with b1:
            st.write(f"**Primary keyword:** {brief['primary_keyword']}")
            st.write(f"**SEO title:** {brief['recommended_title']}")
            st.write(f"**Meta description:** {brief['recommended_meta']}")
            st.write(f"**Secondary keywords:** {brief['secondary_keywords'] or 'None'}")
        with b2:
            st.write("**Suggested sections**")
            for section in brief["sections"]:
                st.write(f"- {section}")
            if brief["faqs"]:
                st.write("**FAQ ideas**")
                for q in brief["faqs"]:
                    st.write(f"- {q}")

with tabs[3]:
    st.markdown('<div class="section-title">Action plan + exports</div>', unsafe_allow_html=True)
    st.caption("The table below is the work queue. Hand this to whoever edits the website.")

    st.dataframe(
        action_plan,
        use_container_width=True,
        hide_index=True,
        column_config={
            "rank": st.column_config.NumberColumn("#", width="small"),
            "owner_priority_score": st.column_config.ProgressColumn("Priority", min_value=0, max_value=100),
            "owner_action": st.column_config.TextColumn("Do this", width="medium"),
            "customer_need": st.column_config.TextColumn("Customer need", width="medium"),
            "volume": st.column_config.NumberColumn("Searches/mo", format="%d"),
            "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
            "recommended_meta": st.column_config.TextColumn("Recommended meta", width="large"),
            "recommended_title": st.column_config.TextColumn("Recommended title", width="large"),
        },
    )

    st.subheader("Keyword table")
    keyword_cols = [
        "priority",
        "owner_priority_score",
        "owner_action",
        "work_type",
        "keyword",
        "customer_need",
        "page",
        "url",
        "volume",
        "cpc",
        "is_brand",
        "is_noise",
        "missing_onpage_signal",
        "reason",
    ]
    st.dataframe(
        filtered.sort_values(["owner_priority_score", "volume"], ascending=False)[keyword_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "owner_priority_score": st.column_config.ProgressColumn("Priority", min_value=0, max_value=100),
            "volume": st.column_config.NumberColumn("Searches/mo", format="%d"),
            "cpc": st.column_config.NumberColumn("CPC", format="$%.2f"),
        },
    )

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Download action plan CSV",
            data=action_plan.to_csv(index=False).encode("utf-8"),
            file_name="local_seo_action_plan.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            "Download enriched keywords CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="local_seo_keywords_enriched.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with d3:
        st.download_button(
            "Download page diagnosis CSV",
            data=pages_view.to_csv(index=False).encode("utf-8"),
            file_name="local_seo_page_diagnosis.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with st.expander("How the priority score works"):
        st.markdown(
            """
            The score favors useful local-business work: real search volume, some commercial value, customer intent, and weak title/H1/URL coverage.

            It penalizes bad-fit terms and keeps brand searches from overpowering growth work. Brand searches still appear in the customer demand view because they matter for calls, visits, and trust.
            """
        )

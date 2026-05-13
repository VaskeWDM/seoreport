import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import io

# ======================================================================
# PAGE CONFIG
# ======================================================================
st.set_page_config(page_title="SEO Strategy App", layout="wide")

st.markdown("""
<style>
    div[data-testid="stMetric"] {
        background-color: #1a1a2e;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #4a4a8a;
    }
    .question-header {
        color: #4facf7;
        font-size: 22px;
        font-weight: 600;
        margin-top: 30px;
        margin-bottom: 10px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ======================================================================
# PARSER
# ======================================================================
@st.cache_data
def parse_audit_csv(file_bytes):
    content = file_bytes.getvalue().decode('utf-8')
    reader = csv.reader(io.StringIO(content))
    lines = list(reader)
    
    groups = []
    current_group = {}
    expecting_group_data = False
    expecting_keywords = False
    
    for row in lines:
        if not row or not any(row): continue
            
        if row[0] == "Group":
            if current_group and 'keywords' in current_group:
                groups.append(current_group)
            expecting_group_data = True
            expecting_keywords = False
            current_group = {}
            
        elif expecting_group_data:
            current_group['Name'] = row[0].replace('&amp;', '&')
            current_group['URL'] = row[2]
            current_group['keywords'] = []
            expecting_group_data = False
            
        elif row[0] == "Keyword":
            expecting_keywords = True
            
        elif expecting_keywords:
            if row[0] == "Group":
                if current_group and 'keywords' in current_group:
                    groups.append(current_group)
                expecting_group_data = True
                expecting_keywords = False
                current_group = {}
                continue
                
            kw = row[0]
            vol = row[1].replace('="', '').replace('"', '') if len(row) > 1 else "0"
            cpc = row[2].replace('="', '').replace('"', '') if len(row) > 2 else "0"
            
            try: vol = int(vol)
            except: vol = 0
            
            try: cpc = float(cpc)
            except: cpc = 0.0
            
            current_group['keywords'].append({'Keyword': kw, 'Volume': vol, 'CPC': cpc})

    if current_group and 'keywords' in current_group:
        groups.append(current_group)
        
    return groups

# ======================================================================
# APP LAYOUT
# ======================================================================
st.title("🚀 SEO Strategy Dashboard")

# The drag-and-drop file uploader
uploaded_file = st.file_uploader("📥 Upload SEO Audit CSV", type=['csv'])

if not uploaded_file:
    st.info("Upload your CSV to generate the SEO breakdown.")
    st.stop()

# Parse & Flatten Data
groups_data = parse_audit_csv(uploaded_file)
all_keywords = []
for g in groups_data:
    for kw in g['keywords']:
        all_keywords.append({
            'Page URL': g['URL'],
            'Keyword': kw['Keyword'],
            'Volume': kw['Volume'],
            'CPC': kw['CPC']
        })

df_all = pd.DataFrame(all_keywords)
if df_all.empty:
    st.warning("No keywords found.")
    st.stop()

# --- GLOBAL METRICS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Keywords", f"{len(df_all):,}")
col2.metric("Total Search Volume", f"{df_all['Volume'].sum():,}")
col3.metric("Max Keyword CPC", f"${df_all['CPC'].max():.2f}")
col4.metric("Pages Audited", len(groups_data))

# --- QUESTION 1 ---
st.markdown("<div class='question-header'>1. Which pages have the highest traffic potential?</div>", unsafe_allow_html=True)
st.caption("Aggregated monthly search volume mapped to specific URLs.")

df_pages = df_all.groupby('Page URL')['Volume'].sum().reset_index().sort_values('Volume', ascending=True)
fig1 = px.bar(df_pages, x='Volume', y='Page URL', orientation='h', color='Volume', color_continuous_scale='Blues')
fig1.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig1, use_container_width=True)

# --- QUESTION 2 ---
st.markdown("<div class='question-header'>2. Where is the commercial intent? (The Golden Keywords)</div>", unsafe_allow_html=True)
st.caption("Scatter plot of Volume vs. CPC. Look for points in the top right (High Traffic + High Value). Hover to see the keyword.")

df_cpc = df_all[df_all['CPC'] > 0]
if not df_cpc.empty:
    fig2 = px.scatter(
        df_cpc, x='Volume', y='CPC', hover_name='Keyword', hover_data=['Page URL'],
        color='CPC', size='Volume', color_continuous_scale='Teal', log_x=True
    )
    fig2.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Volume (Log Scale)")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No CPC data found to map commercial intent.")

# --- QUESTION 3 ---
st.markdown("<div class='question-header'>3. Where are the Quick Wins? (High Volume, $0 CPC)</div>", unsafe_allow_html=True)
st.caption("These keywords drive massive traffic but have little to no commercial ad competition, making them great for informational blog posts.")

df_zero = df_all[df_all['CPC'] == 0].sort_values('Volume', ascending=False).head(15)
fig3 = px.bar(df_zero, x='Volume', y='Keyword', orientation='h', text='Page URL', color='Volume', color_continuous_scale='Greens')
fig3.update_yaxes(autorange="reversed")
fig3.update_layout(height=500, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig3, use_container_width=True)

# --- FOOLPROOF PAGE VIEW ---
st.markdown("<div class='question-header'>Raw Data by Page</div>", unsafe_allow_html=True)
st.caption("Click on any page below to view all assigned keywords.")

for group in groups_data:
    df_group = pd.DataFrame(group['keywords']).sort_values('Volume', ascending=False)
    with st.expander(f"📄 {group['URL']} (Total Volume: {df_group['Volume'].sum():,})"):
        st.dataframe(
            df_group.style.format({'Volume': '{:,}', 'CPC': '${:.2f}'}),
            use_container_width=True, hide_index=True
        )
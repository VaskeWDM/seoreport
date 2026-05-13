import streamlit as st
import pandas as pd
import plotly.express as px
import csv
import io
import glob
import os

# ======================================================================
# PAGE CONFIG & CSS
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
    /* Make tabs larger and clearer */
    button[data-baseweb="tab"] {
        font-size: 18px !important;
        font-weight: 600 !important;
    }
    section[data-testid="stSidebar"] hr { margin: 12px 0; }
</style>
""", unsafe_allow_html=True)

# ======================================================================
# PARSER
# ======================================================================
@st.cache_data
def parse_audit_csv(file_content_str):
    reader = csv.reader(io.StringIO(file_content_str))
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
# SIDEBAR: FILE SELECTION
# ======================================================================
st.sidebar.markdown("## 📂 Report Library")
mode = st.sidebar.radio("Choose Input Method:", ("📄 Select Local File", "📤 Upload New CSV"))
st.sidebar.divider()

file_content_str = None
report_title = "SEO Report"

if mode == "📄 Select Local File":
    # Scan local directory for CSVs
    all_files = glob.glob("**/*.csv", recursive=True) + glob.glob("**/*.CSV", recursive=True)
    repo_files = sorted(list(set(all_files)), reverse=True)
    
    if repo_files:
        selected_file = st.sidebar.selectbox("Pick an SEO report:", repo_files)
        if selected_file:
            try:
                with open(selected_file, 'r', encoding='utf-8') as f:
                    file_content_str = f.read()
                report_title = os.path.basename(selected_file)
            except Exception as e:
                st.sidebar.error(f"Error reading file: {e}")
    else:
        st.sidebar.info("No CSV files found in this folder.")

elif mode == "📤 Upload New CSV":
    uploaded_file = st.sidebar.file_uploader("Drop SEO CSV here", type=['csv'])
    if uploaded_file:
        try:
            file_content_str = uploaded_file.getvalue().decode('utf-8')
            report_title = uploaded_file.name
        except Exception as e:
            st.sidebar.error(f"Error reading file: {e}")

if not file_content_str:
    st.info("👈 Please select a local file or upload a new CSV from the sidebar to begin.")
    st.stop()

# ======================================================================
# DATA PROCESSING
# ======================================================================
groups_data = parse_audit_csv(file_content_str)
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
    st.warning("No keyword data found in this file.")
    st.stop()

# ======================================================================
# MAIN LAYOUT
# ======================================================================
st.title(f"🚀 SEO Dashboard: {report_title}")

# Global Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Keywords", f"{len(df_all):,}")
col2.metric("Total Search Volume", f"{df_all['Volume'].sum():,}")
col3.metric("Max Keyword CPC", f"${df_all['CPC'].max():.2f}")
col4.metric("Pages Audited", len(groups_data))

st.divider()

# TABS for cleaner layout
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Traffic Potential", 
    "💰 Golden Keywords", 
    "🧊 Quick Wins", 
    "📄 Page-by-Page View"
])

# --- TAB 1 ---
with tab1:
    st.subheader("Which pages have the highest traffic potential?")
    st.caption("Aggregated monthly search volume mapped to specific URLs.")
    df_pages = df_all.groupby('Page URL')['Volume'].sum().reset_index().sort_values('Volume', ascending=True)
    fig1 = px.bar(df_pages, x='Volume', y='Page URL', orientation='h', color='Volume', color_continuous_scale='Blues')
    fig1.update_layout(height=max(400, len(df_pages)*30), margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig1, use_container_width=True)

# --- TAB 2 ---
with tab2:
    st.subheader("Where is the commercial intent? (The Golden Keywords)")
    st.caption("High Volume + High CPC. Look for points in the top right. Hover to see the keyword.")
    df_cpc = df_all[df_all['CPC'] > 0]
    if not df_cpc.empty:
        fig2 = px.scatter(
            df_cpc, x='Volume', y='CPC', hover_name='Keyword', hover_data=['Page URL'],
            color='CPC', size='Volume', color_continuous_scale='Teal', log_x=True
        )
        fig2.update_layout(height=500, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="Volume (Log Scale)")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No CPC data found to map commercial intent.")

# --- TAB 3 ---
with tab3:
    st.subheader("Where are the Quick Wins? (High Volume, $0 CPC)")
    st.caption("These keywords drive traffic but have no ad competition—great for informational content.")
    df_zero = df_all[df_all['CPC'] == 0].sort_values('Volume', ascending=False).head(20)
    fig3 = px.bar(df_zero, x='Volume', y='Keyword', orientation='h', text='Page URL', color='Volume', color_continuous_scale='Greens')
    fig3.update_yaxes(autorange="reversed")
    fig3.update_layout(height=600, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig3, use_container_width=True)

# --- TAB 4 ---
with tab4:
    st.subheader("Raw Data by Page")
    st.caption("Click on any page below to view all assigned keywords.")
    
    for group in groups_data:
        df_group = pd.DataFrame(group['keywords']).sort_values('Volume', ascending=False)
        with st.expander(f"🔗 {group['URL']} (Total Volume: {df_group['Volume'].sum():,})"):
            st.dataframe(
                df_group.style.format({'Volume': '{:,}', 'CPC': '${:.2f}'}),
                use_container_width=True, hide_index=True
            )
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import csv
import io

# ======================================================================
# PAGE CONFIG & CSS
# ======================================================================
st.set_page_config(page_title="SEO Audit Report", layout="wide")

st.markdown("""
<style>
    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #1e1e1e;
        border-radius: 10px;
        padding: 12px 16px;
        border: 1px solid #333;
    }
    /* Meta Info box */
    .meta-box {
        background: #1a1a2e;
        border-left: 4px solid #5c6bc0;
        border-radius: 0 8px 8px 0;
        padding: 14px;
        margin: 8px 0 16px 0;
        color: #e0e0e0;
        font-size: 14px;
        line-height: 1.6;
    }
    .meta-box b { color: #8c9eff; }
    /* Sidebar polish */
    section[data-testid="stSidebar"] hr { margin: 12px 0; }
    .sidebar-header {
        font-size: 13px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 16px 0 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ======================================================================
# PARSING LOGIC FOR CUSTOM SEO CSV
# ======================================================================
def parse_audit_csv(file_bytes):
    content = file_bytes.getvalue().decode('utf-8')
    reader = csv.reader(io.StringIO(content))
    lines = list(reader)
    
    project_name = "Unknown Project"
    total_groups = 0
    groups = []
    
    current_group = None
    expecting_group_data = False
    expecting_keywords = False
    
    for row in lines:
        if not row or not any(row):
            continue
            
        if row[0] == "Project Name":
            project_name = row[1]
        elif row[0] == "Total Groups":
            total_groups = row[1]
            
        elif row[0] == "Group":
            if current_group and 'keywords' in current_group:
                groups.append(current_group)
            expecting_group_data = True
            expecting_keywords = False
            current_group = {}
            
        elif expecting_group_data:
            current_group['Name'] = row[0].replace('&amp;', '&')
            current_group['Title'] = row[1].replace('&amp;', '&')
            current_group['URL'] = row[2]
            current_group['DESC'] = row[3].replace('&amp;', '&')
            current_group['H1'] = row[4].replace('&amp;', '&')
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
            # Clean values like ="40500" into pure numbers
            vol_str = row[1].replace('="', '').replace('"', '') if len(row) > 1 else "0"
            cpc_str = row[2].replace('="', '').replace('"', '') if len(row) > 2 else "0"
            
            try: vol = int(vol_str)
            except: vol = 0
            
            try: cpc = float(cpc_str)
            except: cpc = 0.0
            
            current_group['keywords'].append({
                'Keyword': kw,
                'Volume': vol,
                'CPC': cpc
            })

    if current_group and 'keywords' in current_group:
        groups.append(current_group)
        
    return project_name, total_groups, groups


# ======================================================================
# APP LAYOUT
# ======================================================================
st.title("🔍 SEO Audit Report")

st.sidebar.markdown('<div class="sidebar-header">UPLOAD DATA</div>', unsafe_allow_html=True)
uploaded_file = st.sidebar.file_uploader("Drop your SEO Audit CSV here", type=['csv'])

if not uploaded_file:
    st.info("👈 Please upload an SEO Audit CSV file to generate the report.")
    st.stop()

try:
    project_name, total_groups_str, groups_data = parse_audit_csv(uploaded_file)
except Exception as e:
    st.error(f"Error parsing the file. Details: {e}")
    st.stop()

# --- GLOBAL SUMMARY ---
st.subheader(f"🌐 Project: {project_name}")

all_keywords = []
for g in groups_data:
    all_keywords.extend(g['keywords'])

df_all = pd.DataFrame(all_keywords)
total_kw_count = len(df_all)
total_volume = df_all['Volume'].sum() if not df_all.empty else 0
avg_cpc = df_all['CPC'].mean() if not df_all.empty else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("📁 Total Groups", len(groups_data))
c2.metric("🔑 Total Keywords", f"{total_kw_count:,}")
c3.metric("📈 Total Search Volume", f"{total_volume:,}")
c4.metric("💰 Avg. CPC", f"${avg_cpc:.2f}")

st.divider()

# --- GROUP VIEW ---
if groups_data:
    st.markdown("### 📑 Group Analysis")
    group_names = [g['Name'] for g in groups_data]
    
    # Dropdown to swap between different URL groups
    selected_group_name = st.selectbox("Select a Group to view details:", group_names)
    group = next((g for g in groups_data if g['Name'] == selected_group_name), None)
    
    if group:
        # Group Meta Information
        st.markdown(f"""
        <div class="meta-box">
            <b>URL:</b> {group['URL']} <br>
            <b>H1:</b> {group['H1']} <br>
            <b>Title:</b> {group['Title']} <br>
            <b>Description:</b> {group['DESC']}
        </div>
        """, unsafe_allow_html=True)
        
        df_group = pd.DataFrame(group['keywords'])
        
        gc1, gc2, gc3 = st.columns(3)
        gc1.metric("Keywords in Group", len(df_group))
        gc2.metric("Group Volume", f"{df_group['Volume'].sum():,}")
        gc3.metric("Group Avg CPC", f"${df_group['CPC'].mean():.2f}" if not df_group.empty else "$0.00")
        
        col1, col2 = st.columns([1.5, 1])
        
        with col1:
            st.markdown("**📊 Top 10 Keywords by Volume**")
            if not df_group.empty:
                # Get top 10 keywords and sort ascending for Plotly horizontal bar chart
                df_chart = df_group.nlargest(10, 'Volume').sort_values('Volume', ascending=True)
                fig = go.Figure(go.Bar(
                    x=df_chart['Volume'],
                    y=df_chart['Keyword'],
                    orientation='h',
                    marker_color='#5c6bc0'
                ))
                fig.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=400,
                    xaxis_title="Search Volume",
                    yaxis_title=""
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No keywords found for this group.")
                
        with col2:
            st.markdown("**📋 All Keyword Data**")
            if not df_group.empty:
                # Display standard dataframe table for sorting/scrolling
                st.dataframe(
                    df_group.style.format({'Volume': '{:,}', 'CPC': '${:.2f}'}),
                    use_container_width=True,
                    height=400
                )

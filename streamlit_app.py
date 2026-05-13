import streamlit as st
import pandas as pd
import csv
import io

# ======================================================================
# PAGE CONFIGURATION
# ======================================================================
st.set_page_config(page_title="SEO Report Viewer", layout="wide")

# ======================================================================
# CUSTOM CSV PARSER
# ======================================================================
@st.cache_data
def parse_audit_csv(file_bytes):
    content = file_bytes.getvalue().decode('utf-8')
    reader = csv.reader(io.StringIO(content))
    lines = list(reader)
    
    project_name = "Unknown"
    groups = []
    current_group = {}
    expecting_group_data = False
    expecting_keywords = False
    
    for row in lines:
        if not row or not any(row): continue
            
        if row[0] == "Project Name":
            project_name = row[1]
            
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
            current_group['Description'] = row[3].replace('&amp;', '&')
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
            vol_raw = row[1].replace('="', '').replace('"', '') if len(row) > 1 else "0"
            cpc_raw = row[2].replace('="', '').replace('"', '') if len(row) > 2 else "0"
            
            try: vol = int(vol_raw)
            except: vol = 0
            
            try: cpc = float(cpc_raw)
            except: cpc = 0.0
            
            current_group['keywords'].append({
                'Keyword': kw,
                'Volume': vol,
                'CPC ($)': cpc
            })

    if current_group and 'keywords' in current_group:
        groups.append(current_group)
        
    return project_name, groups

# ======================================================================
# APP LAYOUT
# ======================================================================
st.title("📄 SEO Report")

# 1. Uploader at the top
uploaded_file = st.file_uploader("Upload your SEO .csv file", type=['csv'])

if not uploaded_file:
    st.info("Awaiting file upload...")
    st.stop()

# 2. Parse the file
project_name, groups_data = parse_audit_csv(uploaded_file)

st.markdown(f"### Project: **{project_name}**")

# 3. Global Filters
st.markdown("#### ⚙️ Filters")
col1, col2 = st.columns(2)
hide_zero_cpc = col1.checkbox("Hide $0 CPC Keywords", value=False)
hide_low_volume = col2.checkbox("Hide < 50 Search Volume", value=False)

st.divider()

# 4. Display the entire report on one page
for group in groups_data:
    df = pd.DataFrame(group['keywords'])
    
    if df.empty:
        continue
        
    # Apply user filters
    if hide_zero_cpc:
        df = df[df['CPC ($)'] > 0]
    if hide_low_volume:
        df = df[df['Volume'] >= 50]
        
    # Skip rendering this group if filters hide all its keywords
    if df.empty:
        continue 

    # Sort remaining keywords by Volume
    df = df.sort_values(by='Volume', ascending=False)

    # Print Group Headers
    st.markdown(f"### 🔗 {group['URL']}")
    st.markdown(f"**H1:** {group['H1']} | **Title:** {group['Title']}")
    
    # Print Data Table
    st.dataframe(
        df.style.format({
            'Volume': '{:,}', 
            'CPC ($)': '${:.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    # Add a little spacing between groups
    st.markdown("<br>", unsafe_allow_html=True)
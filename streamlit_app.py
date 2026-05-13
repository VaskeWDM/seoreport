import streamlit as st
import pandas as pd
import csv
import io

st.set_page_config(page_title="SEO Report", layout="wide")

# ======================================================================
# PARSER
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
            vol_raw = row[1].replace('="', '').replace('"', '') if len(row) > 1 else "0"
            cpc_raw = row[2].replace('="', '').replace('"', '') if len(row) > 2 else "0"
            intitle = row[3].replace('="', '').replace('"', '') if len(row) > 3 else ""
            inurl = row[4].replace('="', '').replace('"', '') if len(row) > 4 else ""
            
            try: vol = int(vol_raw)
            except: vol = 0
            
            try: cpc = float(cpc_raw)
            except: cpc = 0.0
            
            current_group['keywords'].append({
                'Keyword': kw,
                'Volume': vol,
                'CPC': cpc,
                'inTITLE': intitle,
                'inURL': inurl
            })

    if current_group and 'keywords' in current_group:
        groups.append(current_group)
        
    return project_name, groups

# ======================================================================
# UI LAYOUT
# ======================================================================
st.title("SEO Audit Report")

# Uploader
uploaded_file = st.file_uploader("Upload your SEO .csv file", type=['csv'])

if not uploaded_file:
    st.info("Please upload a CSV file to view the report.")
    st.stop()

project_name, groups_data = parse_audit_csv(uploaded_file)
st.subheader(f"Project: {project_name}")

# FILTERS (As requested)
col1, col2 = st.columns(2)
hide_zero_cpc = col1.checkbox("Hide $0 CPC", value=False)
hide_low_volume = col2.checkbox("Hide < 50 Volume", value=False)

st.divider()

# DISPLAY ALL ON ONE PAGE
for group in groups_data:
    df = pd.DataFrame(group['keywords'])
    
    if df.empty:
        continue
        
    # Apply Filters
    if hide_zero_cpc:
        df = df[df['CPC'] > 0]
    if hide_low_volume:
        df = df[df['Volume'] >= 50]
        
    # Skip if group is empty after filtering
    if df.empty:
        continue 

    # Clean formatting for display
    df = df.sort_values(by='Volume', ascending=False)
    
    # Print the group header
    st.markdown(f"### {group['Name']}")
    st.markdown(f"**URL:** {group['URL']} | **H1:** {group['H1']}")
    
    # Render the exact table
    st.dataframe(
        df.style.format({
            'Volume': '{:,}', 
            'CPC': '${:.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    st.write("") # Spacer between groups
import streamlit as st
import pandas as pd
import csv
import io

# ======================================================================
# PAGE CONFIGURATION
# ======================================================================
st.set_page_config(page_title="SEO Report Viewer", layout="wide")

st.markdown("""
<style>
    /* Clean up the metadata box */
    .metadata-box {
        background-color: #1e1e2e;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #4facf7;
        margin-bottom: 20px;
    }
    .metadata-box p { margin: 5px 0; font-size: 15px; }
    .metadata-label { color: #8c9eff; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ======================================================================
# CUSTOM CSV PARSER (To handle your specific file structure)
# ======================================================================
@st.cache_data
def parse_audit_csv(file_bytes):
    # Read the raw file content
    content = file_bytes.getvalue().decode('utf-8')
    reader = csv.reader(io.StringIO(content))
    lines = list(reader)
    
    project_name = "Unknown"
    groups = []
    
    current_group = {}
    expecting_group_data = False
    expecting_keywords = False
    
    for row in lines:
        if not row or not any(row): 
            continue
            
        if row[0] == "Project Name":
            project_name = row[1]
            
        elif row[0] == "Group":
            # Save previous group if it exists
            if current_group and 'keywords' in current_group:
                groups.append(current_group)
            
            expecting_group_data = True
            expecting_keywords = False
            current_group = {}
            
        elif expecting_group_data:
            # This row contains the Group, Title, URL, DESC, H1
            current_group['Group Name'] = row[0].replace('&amp;', '&')
            current_group['Title'] = row[1].replace('&amp;', '&')
            current_group['URL'] = row[2]
            current_group['Description'] = row[3].replace('&amp;', '&')
            current_group['H1'] = row[4].replace('&amp;', '&')
            current_group['keywords'] = []
            expecting_group_data = False
            
        elif row[0] == "Keyword":
            # Header for keywords, next rows are data
            expecting_keywords = True
            
        elif expecting_keywords:
            # Stop if we hit a new group without a blank line
            if row[0] == "Group":
                if current_group and 'keywords' in current_group:
                    groups.append(current_group)
                expecting_group_data = True
                expecting_keywords = False
                current_group = {}
                continue
                
            # Extract and clean keyword data (removes the ="..." formatting)
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

    # Catch the very last group in the file
    if current_group and 'keywords' in current_group:
        groups.append(current_group)
        
    return project_name, groups


# ======================================================================
# SIDEBAR
# ======================================================================
st.sidebar.title("📂 File Upload")
uploaded_file = st.sidebar.file_uploader("Upload your SEO .csv file", type=['csv'])

if not uploaded_file:
    st.info("👈 Please upload your CSV file in the sidebar to view the data.")
    st.stop()

# Parse the uploaded file
project_name, groups_data = parse_audit_csv(uploaded_file)

if not groups_data:
    st.error("Could not find any group data in this file. Please check the format.")
    st.stop()

# Sidebar Navigation (Select a page to view)
st.sidebar.divider()
st.sidebar.subheader("Navigation")

# Create a list of URL names for the dropdown
group_urls = [g['URL'] for g in groups_data]
selected_url = st.sidebar.radio("Select a Page to view:", group_urls)

# Find the data for the selected group
selected_group = next(g for g in groups_data if g['URL'] == selected_url)


# ======================================================================
# MAIN DISPLAY AREA
# ======================================================================
st.title(f"📊 Project: {project_name}")
st.divider()

# 1. Display the "Group" metadata nicely
st.markdown("### Page Details")
st.markdown(f"""
<div class="metadata-box">
    <p><span class="metadata-label">URL:</span> {selected_group.get('URL', '')}</p>
    <p><span class="metadata-label">H1 Tag:</span> {selected_group.get('H1', '')}</p>
    <p><span class="metadata-label">Title:</span> {selected_group.get('Title', '')}</p>
    <p><span class="metadata-label">Description:</span> {selected_group.get('Description', '')}</p>
</div>
""", unsafe_allow_html=True)

# 2. Convert keywords to a DataFrame
df_keywords = pd.DataFrame(selected_group['keywords'])

# Calculate quick totals for this specific page
total_kws = len(df_keywords)
total_vol = df_keywords['Volume'].sum() if not df_keywords.empty else 0

col1, col2 = st.columns(2)
col1.metric("Keywords mapped to this page", total_kws)
col2.metric("Total Search Volume", f"{total_vol:,}")

# 3. Display the raw keyword data in a clean table
st.markdown("### Keyword Data")

if not df_keywords.empty:
    # Sort by volume highest to lowest by default
    df_keywords = df_keywords.sort_values(by='Volume', ascending=False)
    
    # Display dataframe, formatting the volume with commas and CPC with dollar signs
    st.dataframe(
        df_keywords.style.format({
            'Volume': '{:,}', 
            'CPC ($)': '${:.2f}'
        }),
        use_container_width=True,
        hide_index=True,
        height=500
    )
else:
    st.warning("No keywords found for this page.")
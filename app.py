import streamlit as st

st.markdown(
    """
    <style>
    body {
        background: linear-gradient(135deg, #f9f7f7, #dbe2ef, #3f72af);
        color: #112d4e;
    }
    h1, h2, h3 {
        font-family: 'Trebuchet MS', sans-serif;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    .stButton>button {
        background-color: #3f72af;
        color: white;
        border-radius: 12px;
        padding: 0.5em 1em;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #112d4e;
        transform: scale(1.05);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Welcome to the Fancy Streamlit App")
st.write("This is your freshly styled application. Bask in its glory.")

st.button("Click me!")

import pandas as pd
import re

st.set_page_config(page_title="Estimate vs CDK Cross-Reference", layout="wide")

st.title("Estimate vs CDK Cross-Reference Tool")
st.write("Upload your estimate Excel file and paste your CDK parts list below. Get a detailed match report instantly!")

# Upload estimate Excel
estimate_file = st.file_uploader("Upload Estimate Excel", type=["xlsx"])

# Input CDK text
cdk_text = st.text_area("Paste CDK Parts List", height=300)

if st.button("Generate Match Report") and estimate_file and cdk_text.strip():
    with st.spinner("Processing..."):

        # Read estimate Excel
        estimate_df = pd.read_excel(estimate_file)
        estimate_clean = estimate_df.copy()
        estimate_clean = estimate_clean[estimate_clean["Part Number"].notnull()]
        estimate_clean = estimate_clean[estimate_clean["Part Number"].astype(str).str.strip() != "-"]
        estimate_clean["Part Number"] = estimate_clean["Part Number"].apply(
            lambda x: str(int(x)) if pd.notnull(x) and isinstance(x, (int, float)) else str(x).strip())
        estimate_clean["Quantity"] = estimate_clean["Quantity"].fillna(0).astype(int)

        # Parse CDK text
        cdk_lines = []
        for line in cdk_text.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 4:
                part_no, qty, description, price = parts[0], parts[1], " ".join(parts[2:-1]), parts[-1]
                try:
                    cdk_lines.append({
                        "Part Number": part_no.strip(),
                        "CDK Quantity": int(qty.strip()),
                        "CDK Description": description.strip(),
                        "CDK Price": float(price.replace(",", "").strip()),
                    })
                except ValueError:
                    continue
        cdk_df = pd.DataFrame(cdk_lines)

        # Perform matching
        matches = []
        for _, est in estimate_clean.iterrows():
            est_part = est["Part Number"]
            est_qty = est["Quantity"]
            est_price = est["Extended Price"]
            cdk_match = cdk_df[cdk_df["Part Number"] == est_part]

            if not cdk_match.empty:
                cdk_row = cdk_match.iloc[0]
                if est_qty == cdk_row["CDK Quantity"] and abs(est_price - cdk_row["CDK Price"]) < 0.01:
                    match_status = "Matched by Part #, Qty & Price"
                elif est_qty == cdk_row["CDK Quantity"]:
                    match_status = "Matched by Part # & Qty"
                elif abs(est_price - cdk_row["CDK Price"]) < 0.01:
                    match_status = "Matched by Part # & Price"
                else:
                    match_status = "Matched by Part # Only"
                matches.append({
                    "Estimate Line #": est["Line"],
                    "Part Number": est_part,
                    "Description": est["Description"],
                    "Estimate Quantity": est_qty,
                    "CDK Quantity": cdk_row["CDK Quantity"],
                    "Estimate Price": est_price,
                    "CDK Price": cdk_row["CDK Price"],
                    "Match Report": match_status
                })
            else:
                matches.append({
                    "Estimate Line #": est["Line"],
                    "Part Number": est_part,
                    "Description": est["Description"],
                    "Estimate Quantity": est_qty,
                    "CDK Quantity": None,
                    "Estimate Price": est_price,
                    "CDK Price": None,
                    "Match Report": "No Match Found"
                })

        match_df = pd.DataFrame(matches)

        # Add color-coded status
        def color_code_status(row):
            if row["Match Report"] == "Matched by Part #, Qty & Price":
                return "✅ Perfect Match"
            elif "No Match Found" in row["Match Report"]:
                return "❌ No Match"
            else:
                return "⚠️ Discrepancy"
        match_df["Color Coded Match Report"] = match_df.apply(color_code_status, axis=1)

        # Add missing flags
        match_df["Missing in Estimate"] = match_df["Estimate Price"].apply(lambda x: "❌" if pd.isnull(x) else "")
        match_df["Missing in CDK"] = match_df["CDK Price"].apply(lambda x: "❌" if pd.isnull(x) else "")

        # Reorder columns
        final_columns = ["Estimate Line #", "Part Number", "Description",
                         "Estimate Quantity", "CDK Quantity",
                         "Estimate Price", "CDK Price",
                         "Match Report", "Color Coded Match Report",
                         "Missing in Estimate", "Missing in CDK"]
        match_df = match_df[final_columns]

        st.success("Match Report Generated!")
        st.dataframe(match_df, use_container_width=True)

        csv = match_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Report as CSV", csv, "match_report.csv", "text/csv")

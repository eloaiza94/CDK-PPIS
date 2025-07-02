import streamlit as st
import pandas as pd
import re
from fpdf import FPDF
import base64

st.set_page_config(page_title="Estimate vs CDK Cross-Reference", layout="centered")

st.markdown(
    """
    <style>
    body {
        background-color: #1e1e1e;
        color: #e0e0e0;
        font-family: 'Helvetica Neue', sans-serif;
    }
    .stApp {
        max-width: 800px;
        margin: 0 auto;
        padding-top: 2rem;
    }
    h1, h2, h3 {
        color: #f5f5f5;
        text-align: center;
    }
    .stButton>button {
        background-color: #0a84ff;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6em 1.2em;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:hover {
        background-color: #0066cc;
        transform: scale(1.05);
    }
    .stTextInput>div>div>input {
        background-color: #2c2c2c;
        color: #e0e0e0;
        border: none;
        border-radius: 6px;
        padding: 0.5em;
    }
    .stTextInput>div>div>input:focus {
        outline: 2px solid #0a84ff;
    }
    .stMarkdown p {
        font-size: 1.1em;
        line-height: 1.6;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Estimate vs CDK Cross-Reference Tool")
st.write("Upload your estimate Excel file and paste your CDK parts list below. Get a detailed match report instantly!")

# Upload estimate Excel
estimate_file = st.file_uploader("Upload Estimate Excel", type=["xlsx"])

# Input CDK text
cdk_text = st.text_area("Paste CDK Parts List", height=300)

# Add RO number and customer last name fields
ro_number = st.text_input("Enter RO Number (optional)")
customer_lastname = st.text_input("Enter Customer Last Name (optional)")

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

        # Two-way matching
        matches = []
        # 1) Loop over estimate parts
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
                    "Match Report": "❌ Missing in CDK"
                })

        # 2) Loop over CDK parts for extras not in estimate
        for _, cdk in cdk_df.iterrows():
            cdk_part = cdk["Part Number"]
            est_match = estimate_clean[estimate_clean["Part Number"] == cdk_part]
            if est_match.empty:
                matches.append({
                    "Estimate Line #": "-",
                    "Part Number": cdk_part,
                    "Description": cdk["CDK Description"],
                    "Estimate Quantity": None,
                    "CDK Quantity": cdk["CDK Quantity"],
                    "Estimate Price": None,
                    "CDK Price": cdk["CDK Price"],
                    "Match Report": "❌ Missing in Estimate"
                })

        match_df = pd.DataFrame(matches)

        # Color-coded status & missing flags
        def color_code_status(row):
            if row["Match Report"] == "Matched by Part #, Qty & Price":
                return "✅ Perfect Match"
            elif "No Match" in row["Match Report"] or "Missing" in row["Match Report"]:
                return "❌ Issue"
            else:
                return "⚠️ Discrepancy"
        match_df["Color Coded Match Report"] = match_df.apply(color_code_status, axis=1)
        match_df["Missing in Estimate"] = match_df["Estimate Price"].apply(lambda x: "❌" if pd.isnull(x) else "")
        match_df["Missing in CDK"] = match_df["CDK Price"].apply(lambda x: "❌" if pd.isnull(x) else "")

        final_columns = ["Estimate Line #", "Part Number", "Description",
                         "Estimate Quantity", "CDK Quantity",
                         "Estimate Price", "CDK Price",
                         "Match Report", "Color Coded Match Report",
                         "Missing in Estimate", "Missing in CDK"]
        match_df = match_df[final_columns]

        st.success("Match Report Generated!")
        st.dataframe(match_df, use_container_width=True)

        # Generate PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "Estimate vs CDK Match Report", ln=1, align="C")
        pdf.set_font("Arial", "", 12)
        if ro_number:
            pdf.cell(0, 10, f"RO Number: {ro_number}", ln=1)
        if customer_lastname:
            pdf.cell(0, 10, f"Customer: {customer_lastname}", ln=1)
        pdf.ln(5)

        col_widths = [20, 30, 60, 20, 20, 25, 25]
        headers = ["Line", "Part #", "Description", "Est Qty", "CDK Qty", "Est Price", "CDK Price"]
        for w, h in zip(col_widths, headers):
            pdf.cell(w, 8, h, border=1)
        pdf.ln()

        for _, row in match_df.iterrows():
            pdf.cell(20, 8, str(row["Estimate Line #"]), border=1)
            pdf.cell(30, 8, row["Part Number"], border=1)
            pdf.cell(60, 8, row["Description"][:30], border=1)
            pdf.cell(20, 8, str(row["Estimate Quantity"]), border=1)
            pdf.cell(20, 8, str(row["CDK Quantity"]), border=1)
            pdf.cell(25, 8, f"{row['Estimate Price']}" if pd.notnull(row["Estimate Price"]) else "-", border=1)
            pdf.cell(25, 8, f"{row['CDK Price']}" if pd.notnull(row["CDK Price"]) else "-", border=1)
            pdf.ln()

        pdf_bytes = pdf.output(dest="S").encode("latin1")
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="match_report.pdf">📄 Download Match Report as PDF</a>'
        st.markdown(href, unsafe_allow_html=True)

        # Email 1: Missing in Estimate
        missing_estimate = match_df[match_df["Match Report"].str.contains("Missing in Estimate")]
        email1 = f"Hey Deshunn, can you look into these for me please? They're billed out and I want to see if they're supposed to be on the estimate:\n\n"
        for _, row in missing_estimate.iterrows():
            email1 += f"• {row['Part Number']} - {row['Description']} (${row['CDK Price']})\n"
        st.text_area("Email to Estimator", email1, height=200)

        # Email 2: RFC & Missing in CDK
        rfc_items = match_df[match_df["Description"].str.contains("RFC", case=False, na=False)]
        email2 = "Can we get these taken off of the ticket please:\n\n"
        for _, row in rfc_items.iterrows():
            email2 += f"• {row['Part Number']} - {row['Description']} (${row['Estimate Price']}, Qty: {row['Estimate Quantity']})\n"
        email2 += "\n\n\nAlso can you look into these for me and let me know if we forgot to bill them out please!\n\n"
        missing_cdk = match_df[match_df["Match Report"].str.contains("Missing in CDK")]
        for _, row in missing_cdk.iterrows():
            email2 += f"• {row['Part Number']} - {row['Description']} (${row['Estimate Price']})\n"
        st.text_area("Email to Parts Department", email2, height=300)
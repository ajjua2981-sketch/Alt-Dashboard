"""
Alternate Drug Dashboard
Run with:  streamlit run app.py
"""

import io
import pandas as pd
import streamlit as st

from api_client import lookup_alternate_drugs
from config import API_CONFIG, EXPORT_CONFIG

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Alternate Drug Dashboard",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.badge-Y { color:#fff; background:#28a745; padding:2px 10px; border-radius:4px; font-size:0.78rem; }
.badge-N { color:#fff; background:#dc3545; padding:2px 10px; border-radius:4px; font-size:0.78rem; }
.badge-G { color:#fff; background:#17a2b8; padding:2px 10px; border-radius:4px; font-size:0.78rem; }
.badge-X { color:#212529; background:#ffc107; padding:2px 10px; border-radius:4px; font-size:0.78rem; }
div[data-testid="metric-container"] { background:#f8f9fa; border-radius:8px; padding:12px; }
.stDataFrame { font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💊 Alternate Drug")
    st.subheader("Dashboard")
    st.divider()

    st.markdown("**API Configuration**")
    st.code(
        f"Endpoint : {API_CONFIG['base_url']}{API_CONFIG['endpoint']}\n"
        f"Batch Size: {API_CONFIG['batch_size']} NDCs per call\n"
        f"Timeout  : {API_CONFIG['timeout_seconds']}s",
        language="text",
    )

    st.divider()
    st.markdown("**Instructions**")
    st.markdown("""
1. Download the Excel template below
2. Fill in your NDC values
3. Upload the completed file
4. Click **Look Up Alternate Drugs**
5. View results and export
""")

    st.divider()

    # ── Template download ─────────────────────────────────────────────────────
    st.markdown("**Download Input Template**")
    template_df = pd.DataFrame(columns=["NDC", "DAW Code", "Substitution Indicator"])
    template_buffer = io.BytesIO()
    with pd.ExcelWriter(template_buffer, engine="openpyxl") as writer:
        template_df.to_excel(writer, index=False, sheet_name="Input")
        # Auto-size columns
        worksheet = writer.sheets["Input"]
        for col in worksheet.columns:
            worksheet.column_dimensions[col[0].column_letter].width = 25
        # Bold header row
        from openpyxl.styles import Font, PatternFill
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    st.download_button(
        label="⬇️ Download Excel Template",
        data=template_buffer.getvalue(),
        file_name="input_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("💊 Alternate Drug Dashboard")
st.caption("Upload an Excel file with NDC, DAW Code and Substitution Indicator to look up alternate drugs.")

st.divider()

# ── File upload ───────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Upload Excel file (.xlsx)",
    type=["xlsx"],
    help="Excel file must have columns: 'NDC', 'DAW Code', 'Substitution Indicator'",
)

if uploaded_file:
    # ── Parse Excel ───────────────────────────────────────────────────────────
    try:
        # Read the first sheet by default
        xl         = pd.ExcelFile(uploaded_file, engine="openpyxl")
        sheet_name = xl.sheet_names[0]

        # If multiple sheets, let user pick
        if len(xl.sheet_names) > 1:
            sheet_name = st.selectbox(
                "Multiple sheets found — select the input sheet:",
                options=xl.sheet_names,
            )

        df_input = xl.parse(sheet_name)
        df_input.columns = df_input.columns.str.strip()

    except Exception as exc:
        st.error(f"Could not read Excel file: {exc}")
        st.stop()

    # ── Validate required columns ─────────────────────────────────────────────
    required_cols = {"NDC", "DAW Code", "Substitution Indicator"}
    missing = required_cols - set(df_input.columns)
    if missing:
        st.error(
            f"Excel file is missing required columns: **{', '.join(missing)}**\n\n"
            f"Found columns: {', '.join(df_input.columns.tolist())}\n\n"
            f"Download the template from the sidebar to get the correct format."
        )
        st.stop()

    # ── Clean data ────────────────────────────────────────────────────────────
    df_input["NDC"]                    = df_input["NDC"].astype(str).str.strip()
    df_input["DAW Code"]               = df_input["DAW Code"].astype(str).str.strip()
    df_input["Substitution Indicator"] = df_input["Substitution Indicator"].astype(str).str.strip()

    # Drop empty rows
    df_input = df_input[df_input["NDC"].str.len() > 0]
    df_input = df_input[df_input["NDC"] != "nan"]
    df_input = df_input.reset_index(drop=True)

    total_records = len(df_input)

    if total_records == 0:
        st.warning("The uploaded file has no data rows. Please fill in the NDC values and re-upload.")
        st.stop()

    # ── Preview ───────────────────────────────────────────────────────────────
    st.subheader("📂 Uploaded File Preview")
    col_prev, col_info = st.columns([3, 1])
    with col_prev:
        st.dataframe(df_input, use_container_width=True, height=220)
    with col_info:
        st.metric("Total Records",  total_records)
        num_batches = -(-total_records // API_CONFIG["batch_size"])
        st.metric("API Calls Needed", num_batches)
        st.metric("Batch Size", API_CONFIG["batch_size"])

    st.divider()

    # ── Lookup button ─────────────────────────────────────────────────────────
    if st.button("🔍 Look Up Alternate Drugs", type="primary", use_container_width=True):
        drugs = [
            {
                "ndc":                   row["NDC"],
                "dawCode":               row["DAW Code"],
                "substitutionIndicator": row["Substitution Indicator"],
            }
            for _, row in df_input.iterrows()
        ]

        progress_bar = st.progress(0, text="Calling API...")
        status_text  = st.empty()

        batch_size  = API_CONFIG["batch_size"]
        batches     = [drugs[i:i + batch_size] for i in range(0, len(drugs), batch_size)]
        all_results = []
        all_errors  = []

        for i, batch in enumerate(batches):
            status_text.text(f"Processing batch {i + 1} of {len(batches)}...")
            results, errors = lookup_alternate_drugs(batch)
            all_results.extend(results)
            all_errors.extend(errors)
            progress_bar.progress((i + 1) / len(batches), text=f"Batch {i+1}/{len(batches)} done")

        progress_bar.empty()
        status_text.empty()

        st.session_state["results"]   = all_results
        st.session_state["errors"]    = all_errors
        st.session_state["processed"] = len(all_results)
        st.session_state["failed"]    = len(all_errors)

# ── Results section ───────────────────────────────────────────────────────────
if "results" in st.session_state and (
    st.session_state["results"] or st.session_state.get("errors")
):
    results = st.session_state["results"]
    errors  = st.session_state["errors"]

    st.divider()
    st.subheader("📊 Results Summary")

    m1, m2, m3, m4 = st.columns(4)
    sub_yes = sum(1 for r in results if r.get("Substitution Indicator") in ("Y", "G", "X"))
    sub_no  = sum(1 for r in results if r.get("Substitution Indicator") == "N")

    m1.metric("✅ Successful Lookups",      st.session_state["processed"])
    m2.metric("❌ Failed Lookups",          st.session_state["failed"])
    m3.metric("🔄 Substitution Available",  sub_yes)
    m4.metric("🚫 No Substitution",         sub_no)

    st.divider()

    if results:
        # ── Filters ───────────────────────────────────────────────────────────
        st.subheader("🔎 Filter Results")
        f1, f2, f3 = st.columns([2, 2, 2])

        with f1:
            all_indicators = sorted(set(r.get("Substitution Indicator", "") for r in results))
            filter_sub = st.multiselect(
                "Substitution Indicator",
                options=all_indicators,
                default=all_indicators,
            )
        with f2:
            filter_ndc = st.text_input("Search by Requested NDC", placeholder="leave blank for all")
        with f3:
            filter_drug = st.text_input("Search by Drug Name", placeholder="leave blank for all")

        df_results = pd.DataFrame(results)

        if filter_sub:
            df_results = df_results[df_results["Substitution Indicator"].isin(filter_sub)]
        if filter_ndc.strip():
            df_results = df_results[
                df_results["Requested NDC"].str.contains(filter_ndc.strip(), case=False, na=False)
            ]
        if filter_drug.strip():
            df_results = df_results[
                df_results["Requested Drug Name"].str.contains(filter_drug.strip(), case=False, na=False) |
                df_results["Alternate Drug Name"].str.contains(filter_drug.strip(), case=False, na=False)
            ]

        st.divider()

        # ── Results table ─────────────────────────────────────────────────────
        st.subheader(f"📋 Alternate Drug Results ({len(df_results)} records)")

        if df_results.empty:
            st.info("No results match the current filter.")
        else:
            def _badge(val):
                css_map = {"Y": "badge-Y", "N": "badge-N", "G": "badge-G", "X": "badge-X"}
                css = css_map.get(str(val).upper(), "badge-X")
                return f'<span class="{css}">{val}</span>'

            df_display = df_results.copy()
            df_display["Substitution Indicator"] = df_display["Substitution Indicator"].apply(_badge)
            st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)

        st.divider()

        # ── Export ────────────────────────────────────────────────────────────
        st.subheader("📥 Export Results")
        fname = EXPORT_CONFIG["default_filename"]
        ex1, ex2 = st.columns(2)

        with ex1:
            csv_data = df_results.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download as CSV",
                data=csv_data,
                file_name=f"{fname}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with ex2:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_results.to_excel(writer, index=False, sheet_name="Alternate Drugs")
                worksheet = writer.sheets["Alternate Drugs"]
                for col in worksheet.columns:
                    worksheet.column_dimensions[col[0].column_letter].width = 28
                from openpyxl.styles import Font, PatternFill
                for cell in worksheet[1]:
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            st.download_button(
                label="⬇️ Download as Excel",
                data=excel_buffer.getvalue(),
                file_name=f"{fname}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    # ── Errors table ──────────────────────────────────────────────────────────
    if errors:
        st.divider()
        st.subheader("⚠️ Failed Records")
        st.warning(f"{len(errors)} records could not be processed.")
        st.dataframe(pd.DataFrame(errors), use_container_width=True)

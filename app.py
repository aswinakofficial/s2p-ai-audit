"""
app.py — S2P-Audit-Core Enterprise Streamlit Dashboard

Features:
  - Sidebar: DB connection status, mock data viewer
  - Main view: Invoice file upload, real-time graph execution, audit results
  - Enterprise Carbon-inspired dark theme with custom CSS
"""

import streamlit as st
import pandas as pd
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ── Page Configuration ─────────────────────────────
st.set_page_config(
    page_title="S2P Audit Core — Three-Way Match",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Enterprise Carbon Dark Theme CSS ───────────────
st.markdown("""
<style>
    /* ── Global Theme ────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    .stApp {
        font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Header Banner ───────────────────────────── */
    .hero-banner {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        border-radius: 12px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .hero-banner h1 {
        color: #ffffff;
        font-size: 1.75rem;
        font-weight: 600;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.02em;
    }
    .hero-banner p {
        color: rgba(255,255,255,0.7);
        font-size: 0.95rem;
        margin: 0;
        font-weight: 300;
    }

    /* ── Status Cards ────────────────────────────── */
    .status-card {
        border-radius: 10px;
        padding: 1.5rem;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 1rem;
    }
    .status-approved {
        background: linear-gradient(145deg, #064e3b, #065f46);
        border-color: #10b981;
    }
    .status-review {
        background: linear-gradient(145deg, #7c2d12, #9a3412);
        border-color: #f97316;
    }
    .status-pending {
        background: linear-gradient(145deg, #1e3a5f, #1e40af);
        border-color: #3b82f6;
    }
    .status-card h2 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .status-card p {
        margin: 0.5rem 0 0 0;
        font-size: 0.85rem;
        opacity: 0.8;
    }

    /* ── Audit Result Cards ──────────────────────── */
    .variance-pass {
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid #10b981;
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
        margin: 0.5rem 0;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
    }
    .variance-fail {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
        margin: 0.5rem 0;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
    }

    /* ── Sidebar Styling ─────────────────────────── */
    .db-status-online {
        background: rgba(16, 185, 129, 0.15);
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
    }
    .db-status-offline {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
    }

    /* ── Metric-like display ─────────────────────── */
    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.4rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        font-size: 0.9rem;
    }
    .metric-label {
        opacity: 0.7;
    }
    .metric-value {
        font-weight: 600;
        font-family: 'IBM Plex Mono', monospace;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ System Console")
    st.divider()

    # DB Connection Status
    st.markdown("**Database Status**")
    from src.tools import check_db_connection
    db_connected, db_message = check_db_connection()

    if db_connected:
        st.markdown(
            f'<div class="db-status-online">🟢 &nbsp;{db_message}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="db-status-offline">🔴 &nbsp;{db_message}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # OpenAI Key Status
    st.markdown("**OpenAI API**")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and api_key != "sk-your-openai-api-key-here":
        st.markdown(
            '<div class="db-status-online">🟢 &nbsp;API Key configured</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="db-status-offline">🔴 &nbsp;API Key not set in .env</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Mock Data Viewer
    st.markdown("**📊 ERP Data Viewer**")
    if db_connected:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_system.db")
        conn = sqlite3.connect(db_path)

        data_tab = st.radio(
            "Select Table",
            ["PO Master", "GR Records"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if data_tab == "PO Master":
            df_po = pd.read_sql_query("SELECT po_number, vendor_name, item_desc, qty, unit_price, total_value, status FROM po_master", conn)
            st.dataframe(df_po, use_container_width=True, hide_index=True)
        else:
            df_gr = pd.read_sql_query("SELECT gr_number, po_number, item_desc, received_qty, receipt_date, quality_status FROM gr_records", conn)
            st.dataframe(df_gr, use_container_width=True, hide_index=True)

        conn.close()


# ── Main Content ───────────────────────────────────
st.markdown("""
<div class="hero-banner">
    <h1>🔍 S2P Audit Core</h1>
    <p>Enterprise Three-Way Match • Purchase Order ↔ Goods Receipt ↔ Invoice Verification</p>
</div>
""", unsafe_allow_html=True)

# File uploader
uploaded_file = st.file_uploader(
    "📄 Upload Invoice (Text/OCR output)",
    type=["txt"],
    help="Upload a .txt file containing raw invoice text or OCR output.",
)

if uploaded_file is not None:
    raw_text = uploaded_file.read().decode("utf-8")

    # Show raw text preview
    with st.expander("📝 Raw Invoice Text", expanded=False):
        st.code(raw_text, language="text")

    # Check prerequisites
    if not db_connected:
        st.error("❌ Database not connected. Run `python init_db.py` first.")
        st.stop()

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        st.error("❌ OpenAI API key not configured. Update the `.env` file.")
        st.stop()

    # Execute the audit graph
    from src.graph import audit_graph

    initial_state = {
        "file_name": uploaded_file.name,
        "raw_text": raw_text,
        "extracted_data": None,
        "erp_context": None,
        "audit_report": None,
        "status": "PENDING",
    }

    with st.status("🔄 Running Three-Way Match Audit...", expanded=True) as status_container:
        # Step 1: Extraction
        st.write("🧠 **Step 1/3:** Extracting invoice data with GPT-4o...")
        result = audit_graph.invoke(initial_state)
        st.write("✅ Extraction complete")

        # Step 2: ERP Fetch (already done in graph)
        st.write("🗄️ **Step 2/3:** Fetching ERP data & verifying vendor...")
        st.write("✅ ERP data retrieved")

        # Step 3: Audit (already done in graph)
        st.write("⚖️ **Step 3/3:** Running deterministic three-way match...")
        st.write("✅ Audit complete")

        final_status = result.get("status", "UNKNOWN")
        if final_status == "AUTO_APPROVED":
            status_container.update(label="✅ Audit Complete — AUTO APPROVED", state="complete")
        else:
            status_container.update(label="⚠️ Audit Complete — MANUAL REVIEW REQUIRED", state="complete")

    st.divider()

    # ── Status Card ────────────────────────────────
    if final_status == "AUTO_APPROVED":
        st.markdown("""
        <div class="status-card status-approved">
            <h2>✅ AUTO APPROVED</h2>
            <p>All checks passed — invoice cleared for payment processing.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="status-card status-review">
            <h2>⚠️ MANUAL REVIEW</h2>
            <p>Variances detected — requires human review before payment.</p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Results Columns ────────────────────────────
    col_left, col_right = st.columns(2)

    # LEFT: Extracted Data
    with col_left:
        st.markdown("### 📋 Extracted Invoice Data")

        extracted = result.get("extracted_data")
        if extracted:
            # Convert to dict if Pydantic model
            if hasattr(extracted, "model_dump"):
                extracted_dict = extracted.model_dump()
            else:
                extracted_dict = extracted

            # Key metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Confidence", f"{extracted_dict.get('confidence_score', 0):.0%}")
            m2.metric("PO Number", extracted_dict.get("po_number", "N/A"))
            m3.metric("Vendor", extracted_dict.get("vendor_name", "N/A"))

            # Line items table
            items = extracted_dict.get("items", [])
            if items:
                items_df = pd.DataFrame(items)
                items_df.columns = [c.replace("_", " ").title() for c in items_df.columns]
                st.dataframe(items_df, use_container_width=True, hide_index=True)

            # Totals
            st.markdown(f"""
            <div class="metric-row"><span class="metric-label">Subtotal</span><span class="metric-value">${extracted_dict.get('subtotal', 0):,.2f}</span></div>
            <div class="metric-row"><span class="metric-label">Tax</span><span class="metric-value">${extracted_dict.get('tax', 0):,.2f}</span></div>
            <div class="metric-row"><span class="metric-label">Total</span><span class="metric-value">${extracted_dict.get('total', 0):,.2f}</span></div>
            """, unsafe_allow_html=True)

    # RIGHT: Audit Report
    with col_right:
        st.markdown("### 🔎 Audit Report")

        audit_report = result.get("audit_report")
        if audit_report:
            # Summary
            st.info(audit_report.get("summary", "No summary available."))

            # Vendor verification
            vendor = audit_report.get("vendor_verification", {})
            if vendor:
                score = vendor.get("score", 0)
                is_match = vendor.get("is_match", False)
                inv_v = vendor.get("invoice_vendor", "N/A")
                po_v = vendor.get("po_vendor", "N/A")

                if is_match:
                    st.markdown(
                        f'<div class="variance-pass">✅ Vendor Match: "{inv_v}" ↔ "{po_v}" (Score: {score}%)</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="variance-fail">❌ Vendor Mismatch: "{inv_v}" ↔ "{po_v}" (Score: {score}%)</div>',
                        unsafe_allow_html=True,
                    )

            # Line-item audit details
            line_items = audit_report.get("line_items", [])
            for idx, item in enumerate(line_items):
                st.markdown(f"**Line {idx + 1}: {item.get('item_desc', 'Unknown')}**")

                # Quantity check
                qty_status = item.get("qty_check", "N/A")
                inv_qty = item.get("invoice_qty", 0)
                gr_qty = item.get("gr_received_qty", 0)
                if qty_status == "PASS":
                    st.markdown(
                        f'<div class="variance-pass">✅ Qty: Invoice {inv_qty} ≤ GR {gr_qty}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="variance-fail">❌ Qty: Invoice {inv_qty} &gt; GR {gr_qty}</div>',
                        unsafe_allow_html=True,
                    )

                # Price check
                price_status = item.get("price_check", "N/A")
                inv_price = item.get("invoice_unit_price", 0)
                po_price = item.get("po_unit_price", "N/A")
                if price_status == "PASS":
                    st.markdown(
                        f'<div class="variance-pass">✅ Price: Invoice ${inv_price:.2f} ≈ PO ${po_price}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="variance-fail">❌ Price: Invoice ${inv_price:.2f} ≠ PO ${po_price}</div>',
                        unsafe_allow_html=True,
                    )

                # Detailed variances
                for var in item.get("variances", []):
                    st.caption(f"↳ {var}")

            # Flags
            flags = audit_report.get("flags", [])
            if flags:
                st.divider()
                st.markdown("**🚩 Flags Raised**")
                for flag in flags:
                    st.warning(f"`{flag}`")

    # Full JSON expander
    with st.expander("🔬 Full Audit State (JSON)", expanded=False):
        display_result = {}
        for k, v in result.items():
            if hasattr(v, "model_dump"):
                display_result[k] = v.model_dump()
            else:
                display_result[k] = v
        st.json(display_result)

else:
    # Landing state — no file uploaded
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="status-card status-pending">
            <h2>📤</h2>
            <p>Upload an invoice text file to begin the audit</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="status-card status-pending">
            <h2>⚡</h2>
            <p>GPT-4o extracts data · Python audits deterministically</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="status-card status-pending">
            <h2>🛡️</h2>
            <p>Three-Way Match: PO ↔ GR ↔ Invoice</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "**Getting Started:** Create a test file like `invoice_test.txt` with content such as:\n\n"
        "> *Invoice from IBM India for PO-002. We are billing you for 100 units at $50 each.*\n\n"
        "Then upload it above to see the three-way match in action."
    )

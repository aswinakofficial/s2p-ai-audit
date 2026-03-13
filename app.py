"""
app.py — S2P AI Audit: Enterprise Multi-Page Streamlit Dashboard (V2)

Pages:
  1. Audit Engine  — Upload invoices, run three-way match, view results
  2. Analytics     — Audit history, trends, vendor risk heatmap
  3. ERP Manager   — Browse and manage PO, GR, and Vendor data
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Page Configuration ─────────────────────────────
st.set_page_config(
    page_title="S2P AI Audit — Three-Way Match Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Enterprise Theme CSS ───────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    .stApp { font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif; }

    .hero-banner {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        border-radius: 12px; padding: 2rem 2.5rem; margin-bottom: 1.5rem;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .hero-banner h1 { color: #fff; font-size: 1.75rem; font-weight: 600; margin: 0 0 0.5rem 0; letter-spacing: -0.02em; }
    .hero-banner p { color: rgba(255,255,255,0.7); font-size: 0.95rem; margin: 0; font-weight: 300; }

    .status-card {
        border-radius: 10px; padding: 1.5rem; text-align: center;
        border: 1px solid rgba(255,255,255,0.1); margin-bottom: 1rem;
    }
    .status-approved { background: linear-gradient(145deg, #064e3b, #065f46); border-color: #10b981; }
    .status-review { background: linear-gradient(145deg, #7c2d12, #9a3412); border-color: #f97316; }
    .status-pending { background: linear-gradient(145deg, #1e3a5f, #1e40af); border-color: #3b82f6; }
    .status-card h2 { margin: 0; font-size: 1.5rem; font-weight: 700; letter-spacing: 0.05em; }
    .status-card p { margin: 0.5rem 0 0 0; font-size: 0.85rem; opacity: 0.8; }

    .variance-pass {
        background: rgba(16, 185, 129, 0.1); border-left: 4px solid #10b981;
        padding: 0.75rem 1rem; border-radius: 0 6px 6px 0; margin: 0.5rem 0;
        font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
    }
    .variance-fail {
        background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444;
        padding: 0.75rem 1rem; border-radius: 0 6px 6px 0; margin: 0.5rem 0;
        font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
    }
    .variance-warn {
        background: rgba(251, 191, 36, 0.1); border-left: 4px solid #fbbf24;
        padding: 0.75rem 1rem; border-radius: 0 6px 6px 0; margin: 0.5rem 0;
        font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem;
    }

    .db-status-online {
        background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981;
        border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.85rem;
    }
    .db-status-offline {
        background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444;
        border-radius: 8px; padding: 0.75rem 1rem; font-size: 0.85rem;
    }

    .metric-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.4rem 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem;
    }
    .metric-label { opacity: 0.7; }
    .metric-value { font-weight: 600; font-family: 'IBM Plex Mono', monospace; }

    .risk-high { color: #ef4444; font-weight: 600; }
    .risk-medium { color: #fbbf24; font-weight: 600; }
    .risk-low { color: #10b981; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar (Global) ──────────────────────────────
from src.tools import check_db_connection

with st.sidebar:
    st.markdown("### ⚙️ System Console")
    st.divider()

    # DB Status
    db_connected, db_message = check_db_connection()
    if db_connected:
        st.markdown(f'<div class="db-status-online">🟢 &nbsp;{db_message}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="db-status-offline">🔴 &nbsp;{db_message}</div>', unsafe_allow_html=True)

    st.divider()

    # API Key Status
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and api_key != "sk-your-openai-api-key-here":
        st.markdown('<div class="db-status-online">🟢 &nbsp;OpenAI API Key configured</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="db-status-offline">🔴 &nbsp;API Key not set in .env</div>', unsafe_allow_html=True)

    st.divider()
    st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")


# ── Page Navigation ────────────────────────────────

def page_audit_engine():
    """Page 1: Audit Engine — upload invoices and run three-way match."""

    st.markdown("""
    <div class="hero-banner">
        <h1>🔍 S2P AI Audit Engine</h1>
        <p>Three-Way Match • Purchase Order ↔ Goods Receipt ↔ Invoice Verification</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sample Invoice Generator ───────────────────
    with st.expander("📝 Generate Sample Invoice", expanded=False):
        st.caption("Create a test invoice file to try the system.")
        sample_col1, sample_col2 = st.columns(2)
        with sample_col1:
            sample_type = st.selectbox("Select Scenario", [
                "PO-001: Perfect Match",
                "PO-002: Quantity Mismatch",
                "PO-003: Vendor Name Typo",
                "PO-004: Price Mismatch",
                "PO-005: Multi-Line Mixed",
                "PO-006: Duplicate Invoice",
            ])

        samples = {
            "PO-001: Perfect Match": (
                "Invoice from Acme Corp\nPO Number: PO-001\n\n"
                "Line Items:\n1. Laptop Dell Latitude 5540 — Qty: 50 — Unit Price: $1,200.00\n"
                "2. Wireless Mouse Logitech MX — Qty: 50 — Unit Price: $45.00\n\n"
                "Subtotal: $62,250.00\nTax: $0.00\nTotal: $62,250.00"
            ),
            "PO-002: Quantity Mismatch": (
                "Invoice from TechSupply Inc for PO-002.\n"
                "Billing for 100 units of Server Rack Unit 42U at $50.00 each.\n"
                "Subtotal: $5,000.00\nTax: $0.00\nTotal: $5,000.00"
            ),
            "PO-003: Vendor Name Typo": (
                "Invoice from GlobalTech Pvt Ltd\nReference: PO-003\n\n"
                "Cloud Hosting Annual License — Qty: 1 — $25,000.00\n\n"
                "Total Due: $25,000.00"
            ),
            "PO-004: Price Mismatch": (
                "Invoice from NexGen Solutions\nPO: PO-004\n\n"
                "Network Switch 48-Port x 20 units @ $52.00 per unit\n\n"
                "Subtotal: $1,040.00\nTax: $0.00\nTotal: $1,040.00"
            ),
            "PO-005: Multi-Line Mixed": (
                "INVOICE\nVendor: PrimeParts Ltd\nPO Reference: PO-005\n\n"
                "1. Hydraulic Pump Assembly — Qty: 10 — $500.00 each\n"
                "2. Pressure Gauge Module — Qty: 25 — $80.00 each\n"
                "3. Steel Mounting Bracket — Qty: 100 — $12.00 each\n\n"
                "Subtotal: $8,200.00\nTax: $0.00\nTotal: $8,200.00"
            ),
            "PO-006: Duplicate Invoice": (
                "Invoice from Acme Corp\nPO: PO-006\n\n"
                "Office Chair Ergonomic Pro — 30 units at $350.00\n\n"
                "Subtotal: $10,500.00\nTax: $0.00\nTotal: $10,500.00"
            ),
        }

        sample_text = samples[sample_type]
        with sample_col2:
            st.text_area("Preview", sample_text, height=180, disabled=True)

        if st.button("📋 Copy to Clipboard & Use", type="primary"):
            st.session_state["sample_text"] = sample_text
            st.success("✅ Sample loaded! It will be used for the next audit run below.")

    st.divider()

    # ── File Upload or Sample ──────────────────────
    uploaded_file = st.file_uploader(
        "📄 Upload Invoice (Text/OCR output)",
        type=["txt"],
        help="Upload a .txt file containing raw invoice text or OCR output.",
    )

    # Determine the raw text source
    raw_text = None
    file_name = None

    if uploaded_file is not None:
        raw_text = uploaded_file.read().decode("utf-8")
        file_name = uploaded_file.name
    elif st.session_state.get("sample_text"):
        raw_text = st.session_state.pop("sample_text")
        file_name = "sample_invoice.txt"

    if raw_text:
        with st.expander("📝 Raw Invoice Text", expanded=False):
            st.code(raw_text, language="text")

        if not db_connected:
            st.error("❌ Database not connected. Run `python init_db.py` first.")
            st.stop()

        if not api_key or api_key == "sk-your-openai-api-key-here":
            st.error("❌ OpenAI API key not configured. Update the `.env` file.")
            st.stop()

        # ── Execute Audit Graph ────────────────────
        from src.graph import audit_graph

        initial_state = {
            "file_name": file_name,
            "raw_text": raw_text,
            "extracted_data": None,
            "erp_context": None,
            "audit_report": None,
            "status": "PENDING",
        }

        with st.status("🔄 Running Three-Way Match Audit...", expanded=True) as status_container:
            st.write("🧠 **Step 1/3:** Extracting invoice data with GPT-4o...")
            result = audit_graph.invoke(initial_state)

            if result.get("status") == "EXTRACTION_FAILED":
                st.write("⚠️ Primary extraction failed — error captured")
                status_container.update(label="⚠️ Audit Complete — Extraction Failed", state="complete")
            else:
                st.write("✅ Extraction complete")
                st.write("🗄️ **Step 2/3:** Fetching ERP data & verifying vendor...")
                st.write("✅ ERP data retrieved")
                st.write("⚖️ **Step 3/3:** Running deterministic three-way match...")
                st.write("✅ Audit complete")

                final_status = result.get("status", "UNKNOWN")
                if final_status == "AUTO_APPROVED":
                    status_container.update(label="✅ Audit Complete — AUTO APPROVED", state="complete")
                else:
                    status_container.update(label="⚠️ Audit Complete — MANUAL REVIEW REQUIRED", state="complete")

        st.divider()
        final_status = result.get("status", "UNKNOWN")

        # ── Status Card ────────────────────────────
        if final_status == "AUTO_APPROVED":
            st.markdown("""
            <div class="status-card status-approved">
                <h2>✅ AUTO APPROVED</h2>
                <p>All checks passed — invoice cleared for payment processing.</p>
            </div>
            """, unsafe_allow_html=True)
            st.balloons()
        elif final_status == "EXTRACTION_FAILED":
            st.markdown("""
            <div class="status-card status-review">
                <h2>❌ EXTRACTION FAILED</h2>
                <p>Could not extract invoice data. Check API key and invoice format.</p>
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

        # ── Results Columns ────────────────────────
        col_left, col_right = st.columns(2)

        # LEFT: Extracted Data
        with col_left:
            st.markdown("### 📋 Extracted Invoice Data")
            extracted = result.get("extracted_data")
            if extracted:
                if hasattr(extracted, "model_dump"):
                    extracted_dict = extracted.model_dump()
                else:
                    extracted_dict = extracted

                m1, m2, m3 = st.columns(3)
                m1.metric("Confidence", f"{extracted_dict.get('confidence_score', 0):.0%}")
                m2.metric("PO Number", extracted_dict.get("po_number", "N/A"))
                m3.metric("Vendor", extracted_dict.get("vendor_name", "N/A"))

                items = extracted_dict.get("items", [])
                if items:
                    items_df = pd.DataFrame(items)
                    items_df.columns = [c.replace("_", " ").title() for c in items_df.columns]
                    st.dataframe(items_df, use_container_width=True, hide_index=True)

                st.markdown(f"""
                <div class="metric-row"><span class="metric-label">Subtotal</span><span class="metric-value">${extracted_dict.get('subtotal', 0):,.2f}</span></div>
                <div class="metric-row"><span class="metric-label">Tax</span><span class="metric-value">${extracted_dict.get('tax', 0):,.2f}</span></div>
                <div class="metric-row"><span class="metric-label">Total</span><span class="metric-value">${extracted_dict.get('total', 0):,.2f}</span></div>
                """, unsafe_allow_html=True)
            else:
                st.warning("No data extracted — see audit report for details.")

        # RIGHT: Audit Report
        with col_right:
            st.markdown("### 🔎 Audit Report")
            audit_report = result.get("audit_report")
            if audit_report:
                st.info(audit_report.get("summary", "No summary available."))

                # Match type
                match_type = audit_report.get("match_type", "THREE_WAY")
                if match_type == "TWO_WAY":
                    st.markdown('<div class="variance-warn">⚠️ Two-Way Match (No Goods Receipt found)</div>', unsafe_allow_html=True)

                # Duplicate check
                dup = audit_report.get("duplicate_check", {})
                if dup.get("is_duplicate"):
                    prev = dup.get("previous_audit", {})
                    st.markdown(
                        f'<div class="variance-fail">🔁 DUPLICATE: Previously processed on {prev.get("processed_at", "N/A")}</div>',
                        unsafe_allow_html=True,
                    )

                # Vendor verification
                vendor = audit_report.get("vendor_verification", {})
                if vendor:
                    score = vendor.get("score", 0)
                    is_match = vendor.get("is_match", False)
                    inv_v = vendor.get("invoice_vendor", "N/A")
                    po_v = vendor.get("po_vendor", "N/A")
                    if is_match:
                        st.markdown(f'<div class="variance-pass">✅ Vendor: "{inv_v}" ↔ "{po_v}" (Score: {score}%)</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="variance-fail">❌ Vendor: "{inv_v}" ↔ "{po_v}" (Score: {score}%)</div>', unsafe_allow_html=True)

                # Vendor master info
                vm = audit_report.get("vendor_master")
                if vm:
                    risk = vm.get("risk_tier", "UNKNOWN")
                    risk_class = f"risk-{risk.lower()}"
                    st.markdown(f'**Vendor Risk:** <span class="{risk_class}">{risk}</span> &nbsp; | &nbsp; Tax ID: `{vm.get("tax_id", "N/A")}`', unsafe_allow_html=True)

                # Line-item details
                line_items = audit_report.get("line_items", [])
                for idx, item in enumerate(line_items):
                    st.markdown(f"**Line {idx + 1}: {item.get('item_desc', 'Unknown')}**")

                    if item.get("matched_to"):
                        st.caption(f"↳ Fuzzy matched to: {item['matched_to']}")

                    inv_qty = item.get("invoice_qty", 0)
                    gr_qty = item.get("gr_received_qty", 0)
                    if item.get("qty_check") == "PASS":
                        st.markdown(f'<div class="variance-pass">✅ Qty: Invoice {inv_qty} ≤ GR {gr_qty}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="variance-fail">❌ Qty: Invoice {inv_qty} &gt; GR {gr_qty}</div>', unsafe_allow_html=True)

                    inv_price = item.get("invoice_unit_price", 0)
                    po_price = item.get("po_unit_price", "N/A")
                    if item.get("price_check") == "PASS":
                        st.markdown(f'<div class="variance-pass">✅ Price: Invoice ${inv_price:.2f} ≈ PO ${po_price}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="variance-fail">❌ Price: Invoice ${inv_price:.2f} ≠ PO ${po_price}</div>', unsafe_allow_html=True)

                    for var in item.get("variances", []):
                        st.caption(f"↳ {var}")

                # Flags
                flags = audit_report.get("flags", [])
                if flags:
                    st.divider()
                    st.markdown("**🚩 Flags Raised**")
                    for flag in flags:
                        st.warning(f"`{flag}`")

        with st.expander("🔬 Full Audit State (JSON)", expanded=False):
            display_result = {}
            for k, v in result.items():
                if hasattr(v, "model_dump"):
                    display_result[k] = v.model_dump()
                else:
                    display_result[k] = v
            st.json(display_result)

    else:
        # Landing state
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div class="status-card status-pending"><h2>📤</h2><p>Upload an invoice or generate a sample to begin</p></div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="status-card status-pending"><h2>⚡</h2><p>GPT-4o extracts · Python audits deterministically</p></div>', unsafe_allow_html=True)
        with col3:
            st.markdown('<div class="status-card status-pending"><h2>🛡️</h2><p>Three-Way Match: PO ↔ GR ↔ Invoice</p></div>', unsafe_allow_html=True)


def page_analytics():
    """Page 2: Analytics — audit history, trends, vendor risk."""
    st.markdown("""
    <div class="hero-banner">
        <h1>📊 Audit Analytics</h1>
        <p>Historical trends · Vendor risk · Performance metrics</p>
    </div>
    """, unsafe_allow_html=True)

    if not db_connected:
        st.error("Database not connected.")
        return

    from src.analytics import get_audit_stats, get_variance_trends, get_vendor_risk_scores
    from src.tools import fetch_audit_history

    # ── Summary Metrics ────────────────────────────
    stats = get_audit_stats()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Audits", stats["total_audits"])
    m2.metric("Approval Rate", f"{stats['approval_rate']}%")
    m3.metric("Avg Confidence", f"{stats['avg_confidence']:.0%}")
    m4.metric("Total Variances", stats["total_variances"])

    st.divider()

    # ── Audit History Table ────────────────────────
    st.markdown("### 📜 Audit History")
    history = fetch_audit_history(limit=100)

    if history:
        df = pd.DataFrame(history)

        # Filters
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            status_filter = st.multiselect("Filter by Status", ["AUTO_APPROVED", "MANUAL_REVIEW"], default=["AUTO_APPROVED", "MANUAL_REVIEW"])
        with filter_col2:
            po_filter = st.text_input("Filter by PO Number", placeholder="e.g., PO-001")

        if status_filter:
            df = df[df["status"].isin(status_filter)]
        if po_filter:
            df = df[df["po_number"].str.contains(po_filter, case=False, na=False)]

        # Style the status column
        st.dataframe(
            df[["id", "invoice_file", "po_number", "vendor_name", "invoice_total", "status", "confidence", "total_variances", "processed_at"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "ID",
                "invoice_file": "Invoice File",
                "po_number": "PO Number",
                "vendor_name": "Vendor",
                "invoice_total": st.column_config.NumberColumn("Total", format="$%.2f"),
                "status": "Status",
                "confidence": st.column_config.NumberColumn("Confidence", format="%.0f%%"),
                "total_variances": "Variances",
                "processed_at": "Processed At",
            },
        )

        # Export
        csv = df.to_csv(index=False)
        st.download_button("📥 Export as CSV", csv, "audit_history.csv", "text/csv")
    else:
        st.info("No audit history yet. Process some invoices first!")

    st.divider()

    # ── Common Flags ───────────────────────────────
    st.markdown("### 🚩 Most Common Flags")
    if stats["common_flags"]:
        flag_df = pd.DataFrame(stats["common_flags"], columns=["Flag", "Count"])
        st.bar_chart(flag_df.set_index("Flag"))
    else:
        st.info("No flags recorded yet.")

    st.divider()

    # ── Vendor Risk ────────────────────────────────
    st.markdown("### 🏢 Vendor Risk Assessment")
    risk_scores = get_vendor_risk_scores()
    if risk_scores:
        risk_df = pd.DataFrame(risk_scores)
        st.dataframe(
            risk_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "vendor_name": "Vendor",
                "total_audits": "Audits",
                "approved_count": "Approved",
                "review_count": "Reviews",
                "total_variances": "Variances",
                "risk_score": st.column_config.NumberColumn("Risk Score", format="%.1f"),
                "risk_level": "Risk Level",
            },
        )
    else:
        st.info("Process some invoices to see vendor risk data.")


def page_erp_manager():
    """Page 3: ERP Manager — browse and manage data."""
    st.markdown("""
    <div class="hero-banner">
        <h1>🗄️ ERP Data Manager</h1>
        <p>Purchase Orders · Goods Receipts · Vendor Registry</p>
    </div>
    """, unsafe_allow_html=True)

    if not db_connected:
        st.error("Database not connected.")
        return

    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_system.db")
    conn = sqlite3.connect(db_path)

    tab1, tab2, tab3, tab4 = st.tabs(["📦 Purchase Orders", "📋 Goods Receipts", "🏢 Vendors", "📊 PO Fulfillment"])

    with tab1:
        st.markdown("### Purchase Order Master")
        df_po = pd.read_sql_query(
            "SELECT po_number, vendor_name, item_desc, qty, unit_price, total_value, status, created_at FROM po_master ORDER BY po_number",
            conn,
        )
        st.dataframe(
            df_po,
            use_container_width=True,
            hide_index=True,
            column_config={
                "unit_price": st.column_config.NumberColumn("Unit Price", format="$%.2f"),
                "total_value": st.column_config.NumberColumn("Total Value", format="$%.2f"),
            },
        )
        st.metric("Total PO Line Items", len(df_po))

    with tab2:
        st.markdown("### Goods Receipt Records")
        df_gr = pd.read_sql_query(
            "SELECT gr_number, po_number, item_desc, received_qty, receipt_date, quality_status FROM gr_records ORDER BY po_number",
            conn,
        )
        st.dataframe(df_gr, use_container_width=True, hide_index=True)
        st.metric("Total GR Records", len(df_gr))

    with tab3:
        st.markdown("### Vendor Master Registry")
        df_vendor = pd.read_sql_query(
            "SELECT vendor_code, vendor_name, alternate_names, address, tax_id, risk_tier FROM vendor_master ORDER BY vendor_code",
            conn,
        )
        st.dataframe(df_vendor, use_container_width=True, hide_index=True)
        st.metric("Registered Vendors", len(df_vendor))

    with tab4:
        st.markdown("### PO Fulfillment Overview")
        from src.analytics import get_po_summary
        po_summary = get_po_summary()
        if po_summary:
            summary_df = pd.DataFrame(po_summary)
            st.dataframe(
                summary_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "po_number": "PO Number",
                    "vendor_name": "Vendor",
                    "line_items": "Line Items",
                    "total_ordered": "Ordered",
                    "total_received": "Received",
                    "fulfillment_pct": st.column_config.ProgressColumn("Fulfillment %", min_value=0, max_value=100),
                },
            )

    conn.close()


# ── Navigation ─────────────────────────────────────
page = st.navigation([
    st.Page(page_audit_engine, title="Audit Engine", icon="🔍"),
    st.Page(page_analytics, title="Analytics", icon="📊"),
    st.Page(page_erp_manager, title="ERP Manager", icon="🗄️"),
])
page.run()

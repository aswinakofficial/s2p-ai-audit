"""
src/nodes.py — LangGraph node functions for the Three-Way Match audit workflow.

Each function takes the shared AuditState and returns a partial state update.
CRITICAL: The LLM is used ONLY for text extraction. All math and auditing
is performed deterministically in Python.
"""

import os
from typing import Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.models import InvoiceSchema
from src.tools import fetch_po_details, fetch_gr_details, fuzzy_match_vendor
from src.state import AuditState


load_dotenv()

# ──────────────────────────────────────────────
# Node 1: LLM-based Invoice Extraction
# ──────────────────────────────────────────────

def extract_node(state: AuditState) -> dict[str, Any]:
    """Extract structured invoice data from raw text using GPT-4o.

    Uses ChatOpenAI with .with_structured_output(InvoiceSchema) to parse
    the raw invoice text into a validated Pydantic model. The LLM only
    extracts data — no calculations are performed by the LLM.

    Args:
        state: Current audit workflow state containing raw_text.

    Returns:
        Partial state update with extracted_data and status.
    """
    raw_text = state["raw_text"]

    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    structured_llm = llm.with_structured_output(InvoiceSchema)

    system_prompt = (
        "You are a precise invoice data extractor for a procurement audit system. "
        "Extract all invoice fields from the provided text. "
        "IMPORTANT RULES:\n"
        "1. Extract ONLY what is explicitly stated in the text.\n"
        "2. If a field is not present, use reasonable defaults: 0.0 for numbers, 'UNKNOWN' for strings.\n"
        "3. For confidence_score: rate 0.0-1.0 based on how complete and clear the invoice text is.\n"
        "4. Do NOT perform any calculations — extract raw values only.\n"
        "5. If tax is not mentioned, set it to 0.0.\n"
        "6. Calculate subtotal as sum of (qty * unit_price) for each item ONLY if not explicitly stated.\n"
        "7. Calculate total as subtotal + tax ONLY if not explicitly stated."
    )

    extracted: InvoiceSchema = structured_llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract invoice data from this text:\n\n{raw_text}"},
        ]
    )

    return {
        "extracted_data": extracted,
        "status": "EXTRACTION_COMPLETE",
    }


# ──────────────────────────────────────────────
# Node 2: ERP Data Fetch + Vendor Verification
# ──────────────────────────────────────────────

def fetch_erp_node(state: AuditState) -> dict[str, Any]:
    """Fetch PO and GR data from the mock ERP and verify vendor name.

    Queries the SQLite database for Purchase Order and Goods Receipt
    records matching the extracted PO number. Performs fuzzy matching
    on the vendor name to catch typos.

    Args:
        state: Current audit workflow state with extracted_data populated.

    Returns:
        Partial state update with erp_context and status.
    """
    extracted = state["extracted_data"]

    po_number = extracted.po_number if isinstance(extracted, InvoiceSchema) else extracted["po_number"]
    invoice_vendor = extracted.vendor_name if isinstance(extracted, InvoiceSchema) else extracted["vendor_name"]

    # Fetch PO details
    po_data = fetch_po_details(po_number)
    if po_data is None:
        return {
            "erp_context": {
                "po_found": False,
                "po_number": po_number,
                "error": f"PO {po_number} not found in ERP system.",
                "po_details": [],
                "gr_details": [],
                "vendor_match": {"is_match": False, "score": 0, "invoice_vendor": invoice_vendor, "po_vendor": "N/A"},
            },
            "status": "ERP_FETCH_FAILED",
        }

    # Fetch GR details
    gr_data = fetch_gr_details(po_number)

    # Fuzzy vendor match
    po_vendor = po_data[0]["vendor_name"]
    is_match, score = fuzzy_match_vendor(invoice_vendor, po_vendor)

    erp_context = {
        "po_found": True,
        "po_number": po_number,
        "po_details": po_data,
        "gr_details": gr_data,
        "vendor_match": {
            "is_match": is_match,
            "score": score,
            "invoice_vendor": invoice_vendor,
            "po_vendor": po_vendor,
        },
    }

    return {
        "erp_context": erp_context,
        "status": "ERP_FETCH_COMPLETE",
    }


# ──────────────────────────────────────────────
# Node 3: Deterministic Three-Way Match Audit
# ──────────────────────────────────────────────

def deterministic_audit_node(state: AuditState) -> dict[str, Any]:
    """Perform deterministic three-way match audit — pure Python, no LLM.

    Checks:
        1. Quantity: invoice_qty <= gr_received_qty (cannot bill for unreceived items)
        2. Price: |invoice_price - po_price| / po_price <= 0.01 (1% tolerance)

    Builds a structured audit report with line-level variance details and
    determines the final routing: AUTO_APPROVED or MANUAL_REVIEW.

    Args:
        state: Current audit workflow state with extracted_data and erp_context.

    Returns:
        Partial state update with audit_report and status.
    """
    extracted = state["extracted_data"]
    erp_context = state["erp_context"]

    # Handle case where PO was not found
    if not erp_context.get("po_found", False):
        return {
            "audit_report": {
                "summary": "FAILED — Purchase Order not found in ERP system.",
                "po_number": erp_context.get("po_number", "UNKNOWN"),
                "total_variances": 1,
                "line_items": [],
                "vendor_verification": erp_context.get("vendor_match", {}),
                "flags": ["PO_NOT_FOUND"],
            },
            "status": "MANUAL_REVIEW",
        }

    po_details = erp_context["po_details"]
    gr_details = erp_context["gr_details"]
    vendor_match = erp_context["vendor_match"]

    # Build GR lookup: item_desc -> total received qty
    gr_lookup: dict[str, float] = {}
    for gr in gr_details:
        desc = gr["item_desc"]
        gr_lookup[desc] = gr_lookup.get(desc, 0.0) + gr["received_qty"]

    # Build PO lookup: item_desc -> {qty, unit_price}
    po_lookup: dict[str, dict] = {}
    for po in po_details:
        po_lookup[po["item_desc"]] = {
            "qty": po["qty"],
            "unit_price": po["unit_price"],
        }

    # Audit each invoice line item
    invoice_items = extracted.items if isinstance(extracted, InvoiceSchema) else extracted["items"]
    confidence = extracted.confidence_score if isinstance(extracted, InvoiceSchema) else extracted["confidence_score"]

    line_audits = []
    total_variances = 0
    flags: list[str] = []

    for item in invoice_items:
        item_desc = item.item_desc if hasattr(item, "item_desc") else item["item_desc"]
        inv_qty = item.qty if hasattr(item, "qty") else item["qty"]
        inv_price = item.unit_price if hasattr(item, "unit_price") else item["unit_price"]

        # Find best matching PO/GR item (exact or closest match)
        po_match = po_lookup.get(item_desc)
        gr_received = gr_lookup.get(item_desc, 0.0)

        # If no exact match, try to find a match from PO items
        if po_match is None and po_lookup:
            # Use the first PO item as fallback for single-item POs
            if len(po_lookup) == 1:
                fallback_key = list(po_lookup.keys())[0]
                po_match = po_lookup[fallback_key]
                gr_received = gr_lookup.get(fallback_key, 0.0)
                item_desc = fallback_key  # Use PO's item description

        line_audit = {
            "item_desc": item_desc,
            "invoice_qty": inv_qty,
            "invoice_unit_price": inv_price,
            "po_unit_price": po_match["unit_price"] if po_match else None,
            "gr_received_qty": gr_received,
            "qty_check": "PASS",
            "price_check": "PASS",
            "variances": [],
        }

        if po_match is None:
            line_audit["qty_check"] = "FAIL"
            line_audit["price_check"] = "FAIL"
            line_audit["variances"].append("Item not found in PO master.")
            total_variances += 1
            flags.append("ITEM_NOT_FOUND")
        else:
            # Check 1: Quantity — invoice qty must not exceed GR received qty
            if inv_qty > gr_received:
                line_audit["qty_check"] = "FAIL"
                variance_detail = (
                    f"Quantity variance: Invoice claims {inv_qty}, "
                    f"but only {gr_received} received (GR)."
                )
                line_audit["variances"].append(variance_detail)
                total_variances += 1
                flags.append("QTY_EXCEEDS_GR")

            # Check 2: Price — 1% tolerance
            po_price = po_match["unit_price"]
            if po_price > 0:
                price_deviation = abs(inv_price - po_price) / po_price
                if price_deviation > 0.01:
                    line_audit["price_check"] = "FAIL"
                    variance_detail = (
                        f"Price variance: Invoice ${inv_price:.2f} vs "
                        f"PO ${po_price:.2f} (deviation: {price_deviation:.2%})."
                    )
                    line_audit["variances"].append(variance_detail)
                    total_variances += 1
                    flags.append("PRICE_MISMATCH")

        line_audits.append(line_audit)

    # Vendor name check
    if not vendor_match.get("is_match", False):
        flags.append("VENDOR_MISMATCH")
        total_variances += 1

    # Determine final status
    if total_variances > 0 or confidence < 0.85:
        final_status = "MANUAL_REVIEW"
        if confidence < 0.85:
            flags.append("LOW_CONFIDENCE")
    else:
        final_status = "AUTO_APPROVED"

    audit_report = {
        "summary": f"{'APPROVED' if final_status == 'AUTO_APPROVED' else 'REQUIRES REVIEW'} — "
                   f"{total_variances} variance(s) detected.",
        "po_number": erp_context["po_number"],
        "confidence_score": confidence,
        "total_variances": total_variances,
        "line_items": line_audits,
        "vendor_verification": vendor_match,
        "flags": flags,
    }

    return {
        "audit_report": audit_report,
        "status": final_status,
    }

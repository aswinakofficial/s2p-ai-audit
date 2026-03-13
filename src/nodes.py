"""
src/nodes.py — LangGraph node functions for the Three-Way Match audit (V2).

Nodes:
  1. extract_node           — LLM-based invoice extraction with retry/fallback
  2. fetch_erp_node         — ERP data fetch + vendor verification + vendor master
  3. deterministic_audit_node — Pure Python audit with duplicate detection

CRITICAL: The LLM is used ONLY for text extraction. All math and auditing
is performed deterministically in Python.
"""

import os
from typing import Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.models import InvoiceSchema
from src.tools import (
    fetch_po_details,
    fetch_gr_details,
    fuzzy_match_vendor,
    find_best_item_match,
    fetch_vendor_master,
    check_duplicate_invoice,
    save_audit_result,
)
from src.state import AuditState


load_dotenv()

# ──────────────────────────────────────────────
# Node 1: LLM-based Invoice Extraction
# ──────────────────────────────────────────────

EXTRACTION_PROMPT = (
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


def extract_node(state: AuditState) -> dict[str, Any]:
    """Extract structured invoice data from raw text using GPT-4o.

    Uses ChatOpenAI with .with_structured_output(InvoiceSchema) to parse
    the raw invoice text into a validated Pydantic model. Includes fallback
    to gpt-4o-mini if the primary model fails.

    Args:
        state: Current audit workflow state containing raw_text.

    Returns:
        Partial state update with extracted_data and status.
    """
    raw_text = state["raw_text"]
    api_key = os.getenv("OPENAI_API_KEY")

    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {"role": "user", "content": f"Extract invoice data from this text:\n\n{raw_text}"},
    ]

    # Try primary model first, fallback to mini
    models = ["gpt-4o", "gpt-4o-mini"]
    last_error = None

    for model_name in models:
        try:
            llm = ChatOpenAI(
                model=model_name,
                temperature=0,
                api_key=api_key,
            )
            structured_llm = llm.with_structured_output(InvoiceSchema)
            extracted: InvoiceSchema = structured_llm.invoke(messages)

            return {
                "extracted_data": extracted,
                "status": "EXTRACTION_COMPLETE",
            }
        except Exception as e:
            last_error = e
            continue

    # All models failed — return error state
    return {
        "extracted_data": None,
        "status": "EXTRACTION_FAILED",
        "audit_report": {
            "summary": f"EXTRACTION FAILED — {str(last_error)}",
            "po_number": "UNKNOWN",
            "total_variances": 0,
            "line_items": [],
            "vendor_verification": {},
            "flags": ["EXTRACTION_FAILED"],
            "error": str(last_error),
        },
    }


# ──────────────────────────────────────────────
# Node 2: ERP Data Fetch + Vendor Verification
# ──────────────────────────────────────────────

def fetch_erp_node(state: AuditState) -> dict[str, Any]:
    """Fetch PO and GR data from the mock ERP and verify vendor name.

    Also enriches with vendor master data (address, tax ID, risk tier)
    and checks for duplicate invoices.

    Args:
        state: Current audit workflow state with extracted_data populated.

    Returns:
        Partial state update with erp_context and status.
    """
    extracted = state.get("extracted_data")

    # Handle extraction failure
    if extracted is None:
        return {
            "erp_context": {
                "po_found": False,
                "error": "No extracted data available — extraction failed.",
                "po_details": [],
                "gr_details": [],
                "vendor_match": {"is_match": False, "score": 0},
            },
            "status": state.get("status", "EXTRACTION_FAILED"),
        }

    po_number = extracted.po_number if isinstance(extracted, InvoiceSchema) else extracted["po_number"]
    invoice_vendor = extracted.vendor_name if isinstance(extracted, InvoiceSchema) else extracted["vendor_name"]
    invoice_total = extracted.total if isinstance(extracted, InvoiceSchema) else extracted.get("total", 0)

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
                "vendor_master": None,
                "duplicate_check": None,
            },
            "status": "ERP_FETCH_FAILED",
        }

    # Fetch GR details
    gr_data = fetch_gr_details(po_number)

    # Fuzzy vendor match against PO
    po_vendor = po_data[0]["vendor_name"]
    is_match, score = fuzzy_match_vendor(invoice_vendor, po_vendor)

    # Vendor master enrichment
    vendor_info = fetch_vendor_master(invoice_vendor)

    # Duplicate invoice check
    duplicate = check_duplicate_invoice(po_number, invoice_vendor, invoice_total)

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
        "vendor_master": vendor_info,
        "duplicate_check": duplicate,
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
        1. Quantity: invoice_qty <= gr_received_qty
        2. Price: |invoice_price - po_price| / po_price <= 0.01 (1% tolerance)
        3. Duplicate: has this exact PO+vendor+amount been audited before?

    Also supports two-way match fallback when no GR exists.

    Args:
        state: Current audit workflow state with extracted_data and erp_context.

    Returns:
        Partial state update with audit_report and status.
    """
    extracted = state["extracted_data"]
    erp_context = state["erp_context"]

    # Handle extraction failure
    if extracted is None:
        report = state.get("audit_report", {
            "summary": "FAILED — Invoice extraction failed.",
            "po_number": "UNKNOWN",
            "total_variances": 1,
            "line_items": [],
            "vendor_verification": {},
            "flags": ["EXTRACTION_FAILED"],
        })
        _persist_audit(state, report, "MANUAL_REVIEW")
        return {"audit_report": report, "status": "MANUAL_REVIEW"}

    # Handle PO not found
    if not erp_context.get("po_found", False):
        report = {
            "summary": "FAILED — Purchase Order not found in ERP system.",
            "po_number": erp_context.get("po_number", "UNKNOWN"),
            "total_variances": 1,
            "line_items": [],
            "vendor_verification": erp_context.get("vendor_match", {}),
            "vendor_master": erp_context.get("vendor_master"),
            "duplicate_check": None,
            "flags": ["PO_NOT_FOUND"],
        }
        _persist_audit(state, report, "MANUAL_REVIEW")
        return {"audit_report": report, "status": "MANUAL_REVIEW"}

    po_details = erp_context["po_details"]
    gr_details = erp_context["gr_details"]
    vendor_match = erp_context["vendor_match"]
    vendor_master = erp_context.get("vendor_master")
    duplicate_check = erp_context.get("duplicate_check")

    # Build GR lookup: item_desc -> total received qty
    gr_lookup: dict[str, float] = {}
    for gr in gr_details:
        desc = gr["item_desc"]
        gr_lookup[desc] = gr_lookup.get(desc, 0.0) + gr["received_qty"]

    # Build PO lookup
    po_lookup: dict[str, dict] = {}
    for po in po_details:
        po_lookup[po["item_desc"]] = {
            "qty": po["qty"],
            "unit_price": po["unit_price"],
        }

    # Determine if this is a 2-way or 3-way match
    match_type = "THREE_WAY" if gr_details else "TWO_WAY"

    # Audit each invoice line item
    invoice_items = extracted.items if isinstance(extracted, InvoiceSchema) else extracted["items"]
    confidence = extracted.confidence_score if isinstance(extracted, InvoiceSchema) else extracted["confidence_score"]

    line_audits = []
    total_variances = 0
    flags: list[str] = []

    if match_type == "TWO_WAY":
        flags.append("NO_GR_FOUND")

    for item in invoice_items:
        item_desc = item.item_desc if hasattr(item, "item_desc") else item["item_desc"]
        inv_qty = item.qty if hasattr(item, "qty") else item["qty"]
        inv_price = item.unit_price if hasattr(item, "unit_price") else item["unit_price"]

        # Try exact match first, then fuzzy match
        po_match = po_lookup.get(item_desc)
        gr_received = gr_lookup.get(item_desc, 0.0)
        matched_desc = item_desc

        if po_match is None:
            # Try fuzzy item matching
            fuzzy_result = find_best_item_match(item_desc, po_details)
            if fuzzy_result:
                matched_po, match_score = fuzzy_result
                po_match = {
                    "qty": matched_po["qty"],
                    "unit_price": matched_po["unit_price"],
                }
                matched_desc = matched_po["item_desc"]
                gr_received = gr_lookup.get(matched_desc, 0.0)

        line_audit = {
            "item_desc": item_desc,
            "matched_to": matched_desc if matched_desc != item_desc else None,
            "invoice_qty": inv_qty,
            "invoice_unit_price": inv_price,
            "po_unit_price": po_match["unit_price"] if po_match else None,
            "po_qty": po_match["qty"] if po_match else None,
            "gr_received_qty": gr_received,
            "qty_check": "PASS",
            "price_check": "PASS",
            "match_type": match_type,
            "variances": [],
        }

        if po_match is None:
            line_audit["qty_check"] = "FAIL"
            line_audit["price_check"] = "FAIL"
            line_audit["variances"].append("Item not found in PO master (exact or fuzzy).")
            total_variances += 1
            flags.append("ITEM_NOT_FOUND")
        else:
            # Check 1: Quantity — invoice qty must not exceed GR received qty (3-way)
            if match_type == "THREE_WAY":
                if inv_qty > gr_received:
                    line_audit["qty_check"] = "FAIL"
                    variance_detail = (
                        f"Quantity variance: Invoice claims {inv_qty}, "
                        f"but only {gr_received} received (GR)."
                    )
                    line_audit["variances"].append(variance_detail)
                    total_variances += 1
                    flags.append("QTY_EXCEEDS_GR")
            else:
                # 2-way: just check against PO qty
                if inv_qty > po_match["qty"]:
                    line_audit["qty_check"] = "FAIL"
                    variance_detail = (
                        f"Quantity variance (2-way): Invoice claims {inv_qty}, "
                        f"but PO only has {po_match['qty']}."
                    )
                    line_audit["variances"].append(variance_detail)
                    total_variances += 1
                    flags.append("QTY_EXCEEDS_PO")

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

    # Check 3: Vendor name
    if not vendor_match.get("is_match", False):
        flags.append("VENDOR_MISMATCH")
        total_variances += 1

    # Check 4: Duplicate invoice
    is_duplicate = False
    if duplicate_check:
        is_duplicate = True
        flags.append("DUPLICATE_INVOICE")
        total_variances += 1

    # Check 5: Vendor risk tier
    vendor_risk = None
    if vendor_master:
        vendor_risk = vendor_master.get("risk_tier", "UNKNOWN")
        if vendor_risk == "HIGH":
            flags.append("HIGH_RISK_VENDOR")

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
        "match_type": match_type,
        "total_variances": total_variances,
        "line_items": line_audits,
        "vendor_verification": vendor_match,
        "vendor_master": vendor_master,
        "duplicate_check": {
            "is_duplicate": is_duplicate,
            "previous_audit": duplicate_check,
        } if duplicate_check else {"is_duplicate": False},
        "flags": list(set(flags)),  # deduplicate
    }

    # Persist to audit history
    _persist_audit(state, audit_report, final_status)

    return {
        "audit_report": audit_report,
        "status": final_status,
    }


def _persist_audit(state: AuditState, report: dict, status: str) -> None:
    """Helper to persist audit results to the database.

    Args:
        state:  Current workflow state.
        report: Generated audit report.
        status: Final audit status.
    """
    try:
        extracted = state.get("extracted_data")
        if extracted is None:
            return

        po_number = extracted.po_number if isinstance(extracted, InvoiceSchema) else extracted.get("po_number", "UNKNOWN")
        vendor_name = extracted.vendor_name if isinstance(extracted, InvoiceSchema) else extracted.get("vendor_name", "UNKNOWN")
        invoice_total = extracted.total if isinstance(extracted, InvoiceSchema) else extracted.get("total", 0)
        confidence = extracted.confidence_score if isinstance(extracted, InvoiceSchema) else extracted.get("confidence_score", 0)

        save_audit_result(
            invoice_file=state.get("file_name", "unknown"),
            po_number=po_number,
            vendor_name=vendor_name,
            invoice_total=invoice_total,
            status=status,
            confidence=confidence,
            total_variances=report.get("total_variances", 0),
            flags=report.get("flags", []),
            audit_report=report,
        )
    except Exception:
        pass  # Don't fail the audit if persistence fails

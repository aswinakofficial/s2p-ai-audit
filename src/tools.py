"""
src/tools.py — SQLite query utilities and fuzzy matching logic (V2).

Provides functions to query the mock ERP database (erp_system.db) for
Purchase Order, Goods Receipt, and Vendor Master data. Also handles
fuzzy matching, audit history persistence, and duplicate invoice detection.
"""

import sqlite3
import os
import json
from typing import Optional
from datetime import datetime
from thefuzz import fuzz


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "erp_system.db")

# Fuzzy matching thresholds (0-100)
VENDOR_MATCH_THRESHOLD = 75
ITEM_MATCH_THRESHOLD = 70


def get_db_connection() -> sqlite3.Connection:
    """Create and return a new SQLite connection with row_factory enabled.

    Returns:
        sqlite3.Connection: Connection to erp_system.db with dict-like row access.

    Raises:
        FileNotFoundError: If the database file does not exist.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run 'python init_db.py' first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── PO & GR Queries ─────────────────────────────────────


def fetch_po_details(po_number: str) -> Optional[list[dict]]:
    """Fetch all line items for a given PO number from po_master.

    Args:
        po_number: The Purchase Order number to query (e.g., 'PO-001').

    Returns:
        A list of dicts representing PO line items, or None if no PO found.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT po_number, vendor_name, item_desc, qty, unit_price, total_value, status "
            "FROM po_master WHERE po_number = ?",
            (po_number,),
        )
        rows = cursor.fetchall()
        if not rows:
            return None
        return [dict(row) for row in rows]
    finally:
        conn.close()


def fetch_gr_details(po_number: str) -> list[dict]:
    """Fetch all Goods Receipt records linked to a given PO number.

    Args:
        po_number: The Purchase Order number to query.

    Returns:
        A list of dicts representing GR records.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT gr_number, po_number, item_desc, received_qty, receipt_date, quality_status "
            "FROM gr_records WHERE po_number = ?",
            (po_number,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── Vendor Master ────────────────────────────────────────


def fetch_vendor_master(vendor_name: str) -> Optional[dict]:
    """Look up a vendor in the vendor_master table using fuzzy matching.

    Searches both vendor_name and alternate_names columns for the best
    fuzzy match above the threshold.

    Args:
        vendor_name: The vendor name to look up.

    Returns:
        A dict with vendor details if found, or None.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT vendor_code, vendor_name, alternate_names, address, tax_id, risk_tier "
            "FROM vendor_master"
        )
        rows = cursor.fetchall()

        best_match = None
        best_score = 0

        for row in rows:
            row_dict = dict(row)
            # Check primary name
            score = fuzz.token_sort_ratio(vendor_name.strip(), row_dict["vendor_name"].strip())
            if score > best_score:
                best_score = score
                best_match = row_dict

            # Check alternate names
            alt_names = row_dict.get("alternate_names", "") or ""
            for alt in alt_names.split(","):
                alt = alt.strip()
                if alt:
                    alt_score = fuzz.token_sort_ratio(vendor_name.strip(), alt)
                    if alt_score > best_score:
                        best_score = alt_score
                        best_match = row_dict

        if best_match and best_score >= VENDOR_MATCH_THRESHOLD:
            best_match["match_score"] = best_score
            return best_match
        return None
    finally:
        conn.close()


# ── Fuzzy Matching ───────────────────────────────────────


def fuzzy_match_vendor(invoice_vendor: str, po_vendor: str) -> tuple[bool, int]:
    """Compare vendor names using fuzzy token-sort matching.

    Args:
        invoice_vendor: Vendor name from the invoice.
        po_vendor:      Vendor name from the PO master record.

    Returns:
        A tuple of (is_match: bool, score: int).
    """
    score = fuzz.token_sort_ratio(invoice_vendor.strip(), po_vendor.strip())
    return (score >= VENDOR_MATCH_THRESHOLD, score)


def fuzzy_match_item(invoice_item: str, po_item: str) -> tuple[bool, int]:
    """Compare item descriptions using fuzzy token-sort matching.

    Args:
        invoice_item: Item description from the invoice.
        po_item:      Item description from the PO.

    Returns:
        A tuple of (is_match: bool, score: int).
    """
    score = fuzz.token_sort_ratio(invoice_item.strip(), po_item.strip())
    return (score >= ITEM_MATCH_THRESHOLD, score)


def find_best_item_match(invoice_item: str, po_items: list[dict]) -> Optional[tuple[dict, int]]:
    """Find the best fuzzy-matching PO line item for an invoice item.

    Args:
        invoice_item: Item description from the invoice.
        po_items:     List of PO item dicts with 'item_desc' key.

    Returns:
        Tuple of (best_match_dict, score) or None if no match above threshold.
    """
    best_match = None
    best_score = 0

    for po_item in po_items:
        _, score = fuzzy_match_item(invoice_item, po_item["item_desc"])
        if score > best_score:
            best_score = score
            best_match = po_item

    if best_match and best_score >= ITEM_MATCH_THRESHOLD:
        return (best_match, best_score)
    return None


# ── Duplicate Invoice Detection ──────────────────────────


def check_duplicate_invoice(po_number: str, vendor_name: str, invoice_total: float) -> Optional[dict]:
    """Check if a similar invoice has already been processed.

    Matches on PO number + vendor name (fuzzy) + total amount (exact).

    Args:
        po_number:     The PO number from the invoice.
        vendor_name:   The vendor name from the invoice.
        invoice_total: The total amount on the invoice.

    Returns:
        The previous audit record dict if a duplicate is found, or None.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, invoice_file, po_number, vendor_name, invoice_total, status, processed_at "
            "FROM invoice_history "
            "WHERE po_number = ? AND invoice_total = ? AND status IN ('AUTO_APPROVED', 'MANUAL_REVIEW')",
            (po_number, invoice_total),
        )
        rows = cursor.fetchall()

        for row in rows:
            row_dict = dict(row)
            is_match, score = fuzzy_match_vendor(vendor_name, row_dict["vendor_name"])
            if is_match:
                row_dict["vendor_match_score"] = score
                return row_dict

        return None
    finally:
        conn.close()


# ── Audit History Persistence ────────────────────────────


def save_audit_result(
    invoice_file: str,
    po_number: str,
    vendor_name: str,
    invoice_total: float,
    status: str,
    confidence: float,
    total_variances: int,
    flags: list[str],
    audit_report: dict,
) -> int:
    """Persist an audit result to the invoice_history table.

    Args:
        invoice_file:    Name of the invoice file.
        po_number:       PO number from the invoice.
        vendor_name:     Vendor name from the invoice.
        invoice_total:   Total amount of the invoice.
        status:          Final audit status (AUTO_APPROVED / MANUAL_REVIEW).
        confidence:      LLM extraction confidence score.
        total_variances: Number of variances detected.
        flags:           List of flag strings.
        audit_report:    Full audit report dict.

    Returns:
        The row ID of the inserted record.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO invoice_history "
            "(invoice_file, po_number, vendor_name, invoice_total, status, confidence, "
            "total_variances, flags, audit_report, processed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                invoice_file,
                po_number,
                vendor_name,
                invoice_total,
                status,
                confidence,
                total_variances,
                ",".join(flags),
                json.dumps(audit_report),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def fetch_audit_history(limit: int = 50) -> list[dict]:
    """Fetch recent audit history records.

    Args:
        limit: Maximum number of records to return (default: 50).

    Returns:
        List of audit history dicts, ordered by most recent first.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, invoice_file, po_number, vendor_name, invoice_total, "
            "status, confidence, total_variances, flags, processed_at "
            "FROM invoice_history ORDER BY processed_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ── DB Health Check ──────────────────────────────────────


def check_db_connection() -> tuple[bool, str]:
    """Check if the ERP database is accessible and has data.

    Returns:
        A tuple of (is_connected: bool, message: str).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        po_count = cursor.execute("SELECT COUNT(*) FROM po_master").fetchone()[0]
        gr_count = cursor.execute("SELECT COUNT(*) FROM gr_records").fetchone()[0]
        vendor_count = cursor.execute("SELECT COUNT(*) FROM vendor_master").fetchone()[0]
        hist_count = cursor.execute("SELECT COUNT(*) FROM invoice_history").fetchone()[0]
        conn.close()
        return (True, f"Online — {po_count} POs, {gr_count} GRs, {vendor_count} vendors, {hist_count} audits")
    except FileNotFoundError:
        return (False, "Database not found. Run 'python init_db.py' first.")
    except Exception as e:
        return (False, f"Database error: {str(e)}")

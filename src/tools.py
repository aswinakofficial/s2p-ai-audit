"""
src/tools.py — SQLite query utilities and fuzzy matching logic.

Provides functions to query the mock ERP database (erp_system.db) for
Purchase Order and Goods Receipt data, plus fuzzy vendor name matching.
"""

import sqlite3
import os
from typing import Optional
from thefuzz import fuzz


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "erp_system.db")

# Fuzzy matching threshold (0-100)
VENDOR_MATCH_THRESHOLD = 75


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


def fetch_po_details(po_number: str) -> Optional[list[dict]]:
    """Fetch all line items for a given PO number from po_master.

    Args:
        po_number: The Purchase Order number to query (e.g., 'PO-001').

    Returns:
        A list of dicts representing PO line items, or None if no PO found.
        Each dict contains: po_number, vendor_name, item_desc, qty, unit_price,
        total_value, status.
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
        po_number: The Purchase Order number to query (e.g., 'PO-001').

    Returns:
        A list of dicts representing GR records.
        Each dict contains: gr_number, po_number, item_desc, received_qty,
        receipt_date, quality_status.
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


def fuzzy_match_vendor(invoice_vendor: str, po_vendor: str) -> tuple[bool, int]:
    """Compare vendor names using fuzzy token-sort matching.

    Uses thefuzz's token_sort_ratio which normalizes word order and casing
    before computing the Levenshtein-based similarity score.

    Args:
        invoice_vendor: Vendor name from the invoice.
        po_vendor:      Vendor name from the PO master record.

    Returns:
        A tuple of (is_match: bool, score: int).
        is_match is True if score >= VENDOR_MATCH_THRESHOLD (75).
        score is the similarity percentage (0-100).
    """
    score = fuzz.token_sort_ratio(invoice_vendor.strip(), po_vendor.strip())
    return (score >= VENDOR_MATCH_THRESHOLD, score)


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
        conn.close()
        return (True, f"Connected — {po_count} PO items, {gr_count} GR records")
    except FileNotFoundError:
        return (False, "Database not found. Run 'python init_db.py' first.")
    except Exception as e:
        return (False, f"Database error: {str(e)}")

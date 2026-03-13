"""
src/analytics.py — Audit analytics and reporting utilities.

Provides aggregate metrics, trend analysis, and vendor risk scoring
for the analytics dashboard.
"""

import sqlite3
import os
from typing import Any
from collections import Counter

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "erp_system.db")


def _get_conn() -> sqlite3.Connection:
    """Get a database connection with row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_audit_stats() -> dict[str, Any]:
    """Get summary audit statistics.

    Returns:
        Dict with total_audits, approval_rate, review_rate,
        avg_confidence, total_variances, common_flags.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()

        total = cursor.execute("SELECT COUNT(*) FROM invoice_history").fetchone()[0]
        if total == 0:
            return {
                "total_audits": 0,
                "approved": 0,
                "manual_review": 0,
                "approval_rate": 0.0,
                "review_rate": 0.0,
                "avg_confidence": 0.0,
                "total_variances": 0,
                "common_flags": [],
            }

        approved = cursor.execute(
            "SELECT COUNT(*) FROM invoice_history WHERE status = 'AUTO_APPROVED'"
        ).fetchone()[0]
        review = cursor.execute(
            "SELECT COUNT(*) FROM invoice_history WHERE status = 'MANUAL_REVIEW'"
        ).fetchone()[0]
        avg_conf = cursor.execute(
            "SELECT AVG(confidence) FROM invoice_history WHERE confidence IS NOT NULL"
        ).fetchone()[0] or 0.0
        total_vars = cursor.execute(
            "SELECT SUM(total_variances) FROM invoice_history"
        ).fetchone()[0] or 0

        # Aggregate flags
        rows = cursor.execute("SELECT flags FROM invoice_history WHERE flags != ''").fetchall()
        flag_counter: Counter = Counter()
        for row in rows:
            flags_str = row[0] or ""
            for flag in flags_str.split(","):
                flag = flag.strip()
                if flag:
                    flag_counter[flag] += 1

        return {
            "total_audits": total,
            "approved": approved,
            "manual_review": review,
            "approval_rate": round(approved / total * 100, 1) if total > 0 else 0.0,
            "review_rate": round(review / total * 100, 1) if total > 0 else 0.0,
            "avg_confidence": round(avg_conf, 3),
            "total_variances": total_vars,
            "common_flags": flag_counter.most_common(10),
        }
    finally:
        conn.close()


def get_variance_trends() -> list[dict]:
    """Get audit results over time for trend charts.

    Returns:
        List of dicts with date, status, confidence, variances for each audit.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT processed_at, status, confidence, total_variances, po_number, vendor_name "
            "FROM invoice_history ORDER BY processed_at ASC"
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_vendor_risk_scores() -> list[dict[str, Any]]:
    """Calculate vendor risk scores based on audit history.

    Scoring:
      - Each MANUAL_REVIEW adds +2 risk points
      - Each variance adds +1 risk point
      - Each AUTO_APPROVED subtracts -0.5 risk points (floor 0)

    Returns:
        Sorted list of dicts with vendor_name, total_audits,
        approved_count, review_count, risk_score, risk_level.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT vendor_name, status, total_variances "
            "FROM invoice_history WHERE vendor_name IS NOT NULL"
        )
        rows = cursor.fetchall()

        vendor_data: dict[str, dict] = {}
        for row in rows:
            vendor = row[0]
            if vendor not in vendor_data:
                vendor_data[vendor] = {
                    "vendor_name": vendor,
                    "total_audits": 0,
                    "approved_count": 0,
                    "review_count": 0,
                    "total_variances": 0,
                    "risk_score": 0.0,
                }

            v = vendor_data[vendor]
            v["total_audits"] += 1
            if row[1] == "AUTO_APPROVED":
                v["approved_count"] += 1
                v["risk_score"] = max(0, v["risk_score"] - 0.5)
            else:
                v["review_count"] += 1
                v["risk_score"] += 2
            v["total_variances"] += row[2] or 0
            v["risk_score"] += (row[2] or 0)

        # Assign risk levels
        result = list(vendor_data.values())
        for v in result:
            score = v["risk_score"]
            if score <= 1:
                v["risk_level"] = "LOW"
            elif score <= 5:
                v["risk_level"] = "MEDIUM"
            else:
                v["risk_level"] = "HIGH"

        result.sort(key=lambda x: x["risk_score"], reverse=True)
        return result
    finally:
        conn.close()


def get_po_summary() -> list[dict]:
    """Get a summary of all POs with their GR status.

    Returns:
        List of dicts with po_number, vendor, total items, total received, fulfillment %.
    """
    conn = _get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.po_number,
                p.vendor_name,
                COUNT(DISTINCT p.item_desc) as line_items,
                SUM(p.qty) as total_ordered,
                COALESCE(SUM(g.received_qty), 0) as total_received
            FROM po_master p
            LEFT JOIN gr_records g ON p.po_number = g.po_number AND p.item_desc = g.item_desc
            GROUP BY p.po_number, p.vendor_name
        """)
        results = []
        for row in cursor.fetchall():
            row_dict = dict(row)
            ordered = row_dict["total_ordered"] or 1
            received = row_dict["total_received"] or 0
            row_dict["fulfillment_pct"] = round(received / ordered * 100, 1)
            results.append(row_dict)
        return results
    finally:
        conn.close()

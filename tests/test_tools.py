"""
tests/test_tools.py — Unit tests for SQLite queries, fuzzy matching, and audit persistence.
"""

import os
import sys
import pytest
import sqlite3

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure the test database exists by running init_db."""
    from init_db import main as init_main, DB_PATH
    if not os.path.exists(DB_PATH):
        init_main()
    yield


class TestFetchPODetails:
    """Tests for fetch_po_details."""

    def test_existing_po(self):
        from src.tools import fetch_po_details
        result = fetch_po_details("PO-001")
        assert result is not None
        assert len(result) == 2  # PO-001 has 2 line items
        assert result[0]["vendor_name"] == "Acme Corp"

    def test_nonexistent_po(self):
        from src.tools import fetch_po_details
        result = fetch_po_details("PO-999")
        assert result is None

    def test_single_line_po(self):
        from src.tools import fetch_po_details
        result = fetch_po_details("PO-002")
        assert result is not None
        assert len(result) == 1
        assert result[0]["qty"] == 100.0


class TestFetchGRDetails:
    """Tests for fetch_gr_details."""

    def test_existing_gr(self):
        from src.tools import fetch_gr_details
        result = fetch_gr_details("PO-001")
        assert len(result) == 2

    def test_partial_receipt(self):
        from src.tools import fetch_gr_details
        result = fetch_gr_details("PO-002")
        assert len(result) == 1
        assert result[0]["received_qty"] == 50.0

    def test_no_gr(self):
        from src.tools import fetch_gr_details
        result = fetch_gr_details("PO-999")
        assert result == []


class TestFuzzyMatching:
    """Tests for fuzzy vendor and item matching."""

    def test_exact_vendor_match(self):
        from src.tools import fuzzy_match_vendor
        is_match, score = fuzzy_match_vendor("Acme Corp", "Acme Corp")
        assert is_match is True
        assert score == 100

    def test_fuzzy_vendor_near_miss(self):
        """GlobalTech Pvt Ltd vs GlobalTech India scores 71 — below 75 threshold.
        This is an intentional edge case that should trigger VENDOR_MISMATCH."""
        from src.tools import fuzzy_match_vendor
        is_match, score = fuzzy_match_vendor("GlobalTech Pvt Ltd", "GlobalTech India")
        assert is_match is False
        assert score < 75

    def test_vendor_mismatch(self):
        from src.tools import fuzzy_match_vendor
        is_match, score = fuzzy_match_vendor("Completely Different Corp", "Acme Corp")
        assert is_match is False

    def test_fuzzy_item_match(self):
        from src.tools import fuzzy_match_item
        is_match, score = fuzzy_match_item("Laptop Dell Latitude", "Laptop Dell Latitude 5540")
        assert is_match is True

    def test_find_best_item_match(self):
        from src.tools import find_best_item_match
        po_items = [
            {"item_desc": "Laptop Dell Latitude 5540", "qty": 50, "unit_price": 1200},
            {"item_desc": "Wireless Mouse Logitech MX", "qty": 50, "unit_price": 45},
        ]
        result = find_best_item_match("Dell Laptop Latitude 5540", po_items)
        assert result is not None
        assert result[0]["item_desc"] == "Laptop Dell Latitude 5540"


class TestVendorMaster:
    """Tests for vendor master lookup."""

    def test_exact_lookup(self):
        from src.tools import fetch_vendor_master
        result = fetch_vendor_master("Acme Corp")
        assert result is not None
        assert result["vendor_code"] == "V-001"

    def test_alternate_name_lookup(self):
        from src.tools import fetch_vendor_master
        result = fetch_vendor_master("Acme Corporation")
        assert result is not None
        assert result["vendor_code"] == "V-001"

    def test_unknown_vendor(self):
        from src.tools import fetch_vendor_master
        result = fetch_vendor_master("Totally Unknown Vendor XYZ")
        assert result is None


class TestDuplicateDetection:
    """Tests for duplicate invoice detection."""

    def test_duplicate_found(self):
        from src.tools import check_duplicate_invoice
        result = check_duplicate_invoice("PO-006", "Acme Corp", 10500.00)
        assert result is not None
        assert result["po_number"] == "PO-006"

    def test_no_duplicate(self):
        from src.tools import check_duplicate_invoice
        result = check_duplicate_invoice("PO-001", "Acme Corp", 99999.99)
        assert result is None


class TestAuditPersistence:
    """Tests for saving and retrieving audit results."""

    def test_save_and_fetch(self):
        from src.tools import save_audit_result, fetch_audit_history
        row_id = save_audit_result(
            invoice_file="test_invoice.txt",
            po_number="PO-TEST",
            vendor_name="Test Vendor",
            invoice_total=1000.00,
            status="AUTO_APPROVED",
            confidence=0.95,
            total_variances=0,
            flags=[],
            audit_report={"summary": "Test passed"},
        )
        assert row_id > 0

        history = fetch_audit_history(limit=5)
        assert len(history) > 0
        latest = history[0]
        assert latest["po_number"] == "PO-TEST"


class TestDBConnection:
    """Tests for database health check."""

    def test_connection_online(self):
        from src.tools import check_db_connection
        connected, message = check_db_connection()
        assert connected is True
        assert "Online" in message

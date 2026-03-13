"""
tests/test_nodes.py — Tests for LangGraph nodes with mocked LLM responses.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import InvoiceSchema, LineItem
from src.state import AuditState


@pytest.fixture(autouse=True)
def setup_db():
    """Re-initialize the database before each test to avoid cross-run pollution."""
    from init_db import main as init_main
    init_main()
    yield


def _make_mock_invoice(
    po_number: str = "PO-001",
    vendor_name: str = "Acme Corp",
    items: list | None = None,
    confidence: float = 0.92,
    total: float = 62250.00,
) -> InvoiceSchema:
    """Create a mock InvoiceSchema for testing."""
    if items is None:
        items = [
            LineItem(item_desc="Laptop Dell Latitude 5540", qty=50, unit_price=1200.00),
            LineItem(item_desc="Wireless Mouse Logitech MX", qty=50, unit_price=45.00),
        ]
    return InvoiceSchema(
        confidence_score=confidence,
        vendor_name=vendor_name,
        po_number=po_number,
        items=items,
        subtotal=total,
        tax=0.0,
        total=total,
    )


class TestFetchERPNode:
    """Tests for fetch_erp_node."""

    def test_successful_fetch(self):
        from src.nodes import fetch_erp_node
        invoice = _make_mock_invoice()
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        result = fetch_erp_node(state)
        assert result["erp_context"]["po_found"] is True
        assert result["erp_context"]["vendor_match"]["is_match"] is True
        assert len(result["erp_context"]["po_details"]) == 2

    def test_po_not_found(self):
        from src.nodes import fetch_erp_node
        invoice = _make_mock_invoice(po_number="PO-999")
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        result = fetch_erp_node(state)
        assert result["erp_context"]["po_found"] is False

    def test_extraction_failure_handled(self):
        from src.nodes import fetch_erp_node
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": None,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_FAILED",
        }
        result = fetch_erp_node(state)
        assert result["erp_context"]["po_found"] is False


class TestDeterministicAuditNode:
    """Tests for deterministic_audit_node."""

    def test_perfect_match(self):
        from src.nodes import fetch_erp_node, deterministic_audit_node
        invoice = _make_mock_invoice()
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        erp_result = fetch_erp_node(state)
        state.update(erp_result)
        audit_result = deterministic_audit_node(state)
        assert audit_result["status"] == "AUTO_APPROVED"
        assert audit_result["audit_report"]["total_variances"] == 0

    def test_qty_mismatch(self):
        from src.nodes import fetch_erp_node, deterministic_audit_node
        invoice = _make_mock_invoice(
            po_number="PO-002",
            vendor_name="TechSupply Inc",
            items=[LineItem(item_desc="Server Rack Unit 42U", qty=100, unit_price=50.00)],
            total=5000.00,
        )
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        erp_result = fetch_erp_node(state)
        state.update(erp_result)
        audit_result = deterministic_audit_node(state)
        assert audit_result["status"] == "MANUAL_REVIEW"
        assert "QTY_EXCEEDS_GR" in audit_result["audit_report"]["flags"]

    def test_price_mismatch(self):
        from src.nodes import fetch_erp_node, deterministic_audit_node
        invoice = _make_mock_invoice(
            po_number="PO-004",
            vendor_name="NexGen Solutions",
            items=[LineItem(item_desc="Network Switch 48-Port", qty=20, unit_price=52.00)],
            total=1040.00,
        )
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        erp_result = fetch_erp_node(state)
        state.update(erp_result)
        audit_result = deterministic_audit_node(state)
        assert audit_result["status"] == "MANUAL_REVIEW"
        assert "PRICE_MISMATCH" in audit_result["audit_report"]["flags"]

    def test_low_confidence(self):
        from src.nodes import fetch_erp_node, deterministic_audit_node
        invoice = _make_mock_invoice(confidence=0.60)
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        erp_result = fetch_erp_node(state)
        state.update(erp_result)
        audit_result = deterministic_audit_node(state)
        assert audit_result["status"] == "MANUAL_REVIEW"
        assert "LOW_CONFIDENCE" in audit_result["audit_report"]["flags"]

    def test_duplicate_detection(self):
        from src.nodes import fetch_erp_node, deterministic_audit_node
        invoice = _make_mock_invoice(
            po_number="PO-006",
            vendor_name="Acme Corp",
            items=[LineItem(item_desc="Office Chair Ergonomic Pro", qty=30, unit_price=350.00)],
            total=10500.00,
        )
        state: AuditState = {
            "file_name": "test.txt",
            "raw_text": "test",
            "extracted_data": invoice,
            "erp_context": None,
            "audit_report": None,
            "status": "EXTRACTION_COMPLETE",
        }
        erp_result = fetch_erp_node(state)
        state.update(erp_result)
        audit_result = deterministic_audit_node(state)
        assert audit_result["status"] == "MANUAL_REVIEW"
        assert "DUPLICATE_INVOICE" in audit_result["audit_report"]["flags"]

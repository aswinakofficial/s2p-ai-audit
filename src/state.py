"""
src/state.py — LangGraph TypedDict state definition.

Defines the shared state that flows through every node in the audit graph.
"""

from typing import TypedDict, Optional
from src.models import InvoiceSchema


class AuditState(TypedDict):
    """State schema for the S2P Three-Way Match audit workflow.

    Attributes:
        file_name:      Name of the uploaded invoice file.
        raw_text:       Raw OCR / text content of the invoice.
        extracted_data: Structured invoice data extracted by the LLM.
        erp_context:    PO + GR data fetched from the mock ERP database.
        audit_report:   Deterministic audit results with line-level variances.
        status:         Current workflow status: PENDING | APPROVED | MANUAL_REVIEW.
    """

    file_name: str
    raw_text: str
    extracted_data: Optional[InvoiceSchema]
    erp_context: Optional[dict]
    audit_report: Optional[dict]
    status: str

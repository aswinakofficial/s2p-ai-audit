"""
src/models.py — Pydantic v2 schemas for strict LLM structured output.

These models are used with ChatOpenAI's .with_structured_output() to ensure
the LLM returns well-typed, validated invoice data.
"""

from pydantic import BaseModel, Field
from typing import List


class LineItem(BaseModel):
    """A single line item on an invoice."""

    item_desc: str = Field(
        ...,
        description="Description of the item or service being billed."
    )
    qty: float = Field(
        ...,
        description="Quantity of items being billed."
    )
    unit_price: float = Field(
        ...,
        description="Unit price per item in the invoice currency."
    )


class InvoiceSchema(BaseModel):
    """Structured representation of an extracted invoice."""

    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM's self-assessed confidence in the extraction accuracy (0.0 to 1.0)."
    )
    vendor_name: str = Field(
        ...,
        description="Name of the vendor/supplier on the invoice."
    )
    po_number: str = Field(
        ...,
        description="Purchase Order number referenced in the invoice."
    )
    items: List[LineItem] = Field(
        ...,
        description="List of line items on the invoice."
    )
    subtotal: float = Field(
        ...,
        description="Invoice subtotal before tax."
    )
    tax: float = Field(
        ...,
        description="Tax amount on the invoice. Use 0.0 if not specified."
    )
    total: float = Field(
        ...,
        description="Invoice grand total (subtotal + tax)."
    )

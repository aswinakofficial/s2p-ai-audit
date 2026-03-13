"""
src/graph.py — LangGraph workflow assembly for the S2P Three-Way Match audit (V2).

Compiles a StateGraph with three nodes and error-aware routing:
  1. extract       — LLM-based invoice extraction (with fallback)
  2. fetch_erp     — ERP data retrieval + vendor verification
  3. deterministic_audit — Pure Python three-way match

Error handling: if extraction fails, the graph still proceeds through
fetch_erp and audit nodes which handle the None extracted_data gracefully.
"""

from langgraph.graph import StateGraph, END
from src.state import AuditState
from src.nodes import extract_node, fetch_erp_node, deterministic_audit_node


def _route_after_extraction(state: AuditState) -> str:
    """Route after extraction: proceed normally or skip to audit on failure."""
    if state.get("status") == "EXTRACTION_FAILED":
        return "deterministic_audit"
    return "fetch_erp"


def build_audit_graph() -> StateGraph:
    """Build and compile the S2P Three-Way Match audit graph.

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    workflow = StateGraph(AuditState)

    # ── Add nodes ──────────────────────────────────
    workflow.add_node("extract", extract_node)
    workflow.add_node("fetch_erp", fetch_erp_node)
    workflow.add_node("deterministic_audit", deterministic_audit_node)

    # ── Set entry point ────────────────────────────
    workflow.set_entry_point("extract")

    # ── Conditional edge after extraction ──────────
    workflow.add_conditional_edges(
        "extract",
        _route_after_extraction,
        {
            "fetch_erp": "fetch_erp",
            "deterministic_audit": "deterministic_audit",
        },
    )

    # ── Linear edges ───────────────────────────────
    workflow.add_edge("fetch_erp", "deterministic_audit")

    # ── Terminal edge ──────────────────────────────
    workflow.add_edge("deterministic_audit", END)

    return workflow.compile()


# Pre-compiled graph instance for import
audit_graph = build_audit_graph()

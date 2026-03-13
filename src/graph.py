"""
src/graph.py — LangGraph workflow assembly for the S2P Three-Way Match audit.

Compiles a StateGraph with three nodes:
  1. extract       — LLM-based invoice extraction
  2. fetch_erp     — ERP data retrieval + vendor verification
  3. deterministic_audit — Pure Python three-way match

Conditional routing after the audit node determines final status:
  - AUTO_APPROVED if zero variances and confidence >= 0.85
  - MANUAL_REVIEW otherwise
"""

from langgraph.graph import StateGraph, END
from src.state import AuditState
from src.nodes import extract_node, fetch_erp_node, deterministic_audit_node


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

    # ── Linear edges ───────────────────────────────
    workflow.add_edge("extract", "fetch_erp")
    workflow.add_edge("fetch_erp", "deterministic_audit")

    # ── Conditional edge after audit ───────────────
    def route_after_audit(state: AuditState) -> str:
        """Determine the routing after the deterministic audit.

        Routes to END in all cases — the status field in the state
        already contains the final determination (AUTO_APPROVED or
        MANUAL_REVIEW) set by the audit node.
        """
        return END

    workflow.add_conditional_edges(
        "deterministic_audit",
        route_after_audit,
        {END: END},
    )

    return workflow.compile()


# Pre-compiled graph instance for import
audit_graph = build_audit_graph()

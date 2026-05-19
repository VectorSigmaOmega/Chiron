from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.specialists import RetrievalSpecialist
from app.orchestration.nodes import (
    aggregate_evidence,
    assess_coverage,
    dispatch_specialists,
    finalize_response,
    load_session_context,
    normalize_query,
    plan_evidence,
    should_replan,
    synthesize_answer,
    verify_answer,
)
from app.orchestration.state import GraphState


def build_graph(specialists: dict[str, RetrievalSpecialist]):
    graph = StateGraph(GraphState)

    async def dispatch_node(state: GraphState):
        return await dispatch_specialists(state, specialists)

    graph.add_node("load_session_context", load_session_context)
    graph.add_node("normalize_query", normalize_query)
    graph.add_node("plan_evidence", plan_evidence)
    graph.add_node("dispatch_specialists", dispatch_node)
    graph.add_node("aggregate_evidence", aggregate_evidence)
    graph.add_node("assess_coverage", assess_coverage)
    graph.add_node("synthesize_answer", synthesize_answer)
    graph.add_node("verify_answer", verify_answer)
    graph.add_node("finalize_response", finalize_response)

    graph.add_edge(START, "load_session_context")
    graph.add_edge("load_session_context", "normalize_query")
    graph.add_edge("normalize_query", "plan_evidence")
    graph.add_conditional_edges(
        "plan_evidence",
        lambda state: "finalize_response" if state.get("final_response") else "dispatch_specialists",
        {
            "dispatch_specialists": "dispatch_specialists",
            "finalize_response": "finalize_response",
        },
    )
    graph.add_edge("dispatch_specialists", "aggregate_evidence")
    graph.add_edge("aggregate_evidence", "assess_coverage")
    graph.add_conditional_edges(
        "assess_coverage",
        should_replan,
        {
            "dispatch_specialists": "dispatch_specialists",
            "synthesize_answer": "synthesize_answer",
            "finalize": "finalize_response",
        },
    )
    graph.add_edge("synthesize_answer", "verify_answer")
    graph.add_edge("verify_answer", "finalize_response")
    graph.add_edge("finalize_response", END)
    return graph.compile()

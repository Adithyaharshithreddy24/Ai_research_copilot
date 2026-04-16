import os
import re
from typing import List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from services.arxiv_service import fetch_papers
from services.llm_service import generate_discovery_suggestions
from services.rag_service import paper_chat_answer, rag_answer
from services.vector_service import add_documents


class GraphState(TypedDict):
    user_input: str
    chat_id: str
    mode: str
    intent: Optional[str]
    papers: Optional[List]
    response: Optional[str]


def _get_max_discovery_papers() -> int:
    raw = os.getenv("MAX_DISCOVERY_PAPERS", "5").strip()
    try:
        value = int(raw)
        return max(1, min(value, 20))
    except Exception:
        return 5


def talkable(state: GraphState):
    text = state["user_input"].lower().strip()

    if text in ["hi", "hello", "hey"]:
        state["response"] = "Hello! I can help you with research papers and PDFs."
        state["intent"] = "end"
        return state

    if len(text) < 2:
        state["response"] = "Please enter a meaningful query."
        state["intent"] = "end"
        return state

    state["intent"] = "proceed"
    return state


def classify_intent(state: GraphState):
    text = state["user_input"].lower()
    follow_up_keywords = [
        "this",
        "that",
        "these",
        "those",
        "above",
        "previous",
        "earlier",
        "it",
        "them",
        "continue",
        "elaborate",
        "explain this",
    ]

    def contains_token(token: str) -> bool:
        if " " in token:
            return token in text
        return bool(re.search(rf"\b{re.escape(token)}\b", text))

    if any(contains_token(x) for x in ["summarize", "review", "citation", "gap"]):
        state["intent"] = "action"
    elif any(contains_token(x) for x in follow_up_keywords):
        state["intent"] = "follow_up"
    else:
        state["intent"] = "new_topic"

    return state


def fetch_arxiv_node(state: GraphState):
    query = _extract_search_query(state["user_input"])
    papers = _discover_papers(
        query,
        state["chat_id"],
        mode=state.get("mode", "keyword"),
        max_results=_get_max_discovery_papers(),
    )
    state["papers"] = papers
    return state


def _get_discovery_mode() -> str:
    mode = os.getenv("DISCOVERY_MODE", "hybrid").strip().lower()
    if mode in {"arxiv_only", "gemini_only", "hybrid"}:
        return mode
    return "hybrid"


def _is_arxiv_unavailable(papers: List[dict]) -> bool:
    if not papers:
        return True
    first_title = str(papers[0].get("title", "")).lower() if isinstance(papers[0], dict) else ""
    return "arxiv temporarily unavailable" in first_title


def _discover_papers(query: str, chat_id: str, mode: str = "keyword", max_results: int = 2) -> List[dict]:
    # Product rule:
    # - keyword mode => hybrid discovery
    # - paper mode => Gemini-only (no arXiv)
    if mode == "paper":
        return generate_discovery_suggestions(query, max_results=max_results)

    discovery_mode = _get_discovery_mode()
    if mode == "keyword":
        discovery_mode = "hybrid"

    if discovery_mode == "gemini_only":
        return generate_discovery_suggestions(query, max_results=max_results)

    if discovery_mode == "arxiv_only":
        return fetch_papers(query, max_results, chat_id=chat_id)

    arxiv_papers = fetch_papers(query, max_results, chat_id=chat_id)
    if not _is_arxiv_unavailable(arxiv_papers):
        return arxiv_papers

    try:
        return generate_discovery_suggestions(query, max_results=max_results)
    except Exception as e:
        print("GEMINI DISCOVERY ERROR:", e)
        return arxiv_papers


def _extract_search_query(user_input: str) -> str:
    text = user_input.strip()
    lowered = text.lower()

    marker = "keyword/topic:"
    if marker in lowered:
        start = lowered.find(marker) + len(marker)
        tail = text[start:].strip()
        first_sentence = re.split(r"[.\n]", tail, maxsplit=1)[0].strip(" :;-")
        if first_sentence:
            return first_sentence

    text = re.sub(r"(?i)^find\s+research\s+papers\s+(for|on)\s+", "", text).strip()
    text = re.sub(r"(?i)^search\s+(papers|arxiv)\s+(for|on)\s+", "", text).strip()

    return text or user_input.strip()


def store_node(state: GraphState):
    add_documents(f"chat_{state['chat_id']}", state["papers"])
    return state


def route_after_talkable(state: GraphState):
    if state.get("intent") == "end":
        return "end"
    return "intent"


def route_after_intent(state: GraphState):
    if state.get("mode") == "paper":
        return "respond"

    if state.get("intent") == "new_topic":
        return "fetch"
    return "respond"


def generate_response_node(state: GraphState):
    chat_id = state["chat_id"]
    question = state["user_input"]
    mode = state.get("mode", "keyword")

    if mode == "paper":
        try:
            paper_resp = paper_chat_answer(chat_id, question)
        except Exception as e:
            print("PAPER CHAT ERROR:", e)
            paper_resp = None

        if paper_resp:
            state["response"] = paper_resp
            return state

        state["response"] = (
            "I could not find enough uploaded-paper context for that question. "
            "Please upload/select your PDF and ask a document-specific question."
        )
        return state

    try:
        rag_resp = rag_answer(chat_id, question)
    except Exception as e:
        print("RAG ERROR:", e)
        rag_resp = None

    if rag_resp:
        state["response"] = rag_resp
        return state

    papers = state.get("papers", [])
    if papers:
        text = "\n\n".join([f"- {p['title']}" for p in papers[:5]])
        state["response"] = f"Top relevant papers:\n{text}"
    else:
        state["response"] = "No relevant data found."

    return state


def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("talkable", talkable)
    builder.add_node("intent", classify_intent)
    builder.add_node("fetch", fetch_arxiv_node)
    builder.add_node("store", store_node)
    builder.add_node("respond", generate_response_node)

    builder.set_entry_point("talkable")

    builder.add_conditional_edges(
        "talkable",
        route_after_talkable,
        {
            "intent": "intent",
            "end": END,
        },
    )
    builder.add_conditional_edges(
        "intent",
        route_after_intent,
        {
            "fetch": "fetch",
            "respond": "respond",
        },
    )
    builder.add_edge("fetch", "store")
    builder.add_edge("store", "respond")
    builder.add_edge("respond", END)

    return builder.compile()


graph = build_graph()


def run_graph(user_input: str, chat_id: str, mode: str = "keyword"):
    state = {
        "user_input": user_input,
        "chat_id": chat_id,
        "mode": mode,
        "intent": None,
        "papers": [],
        "response": None,
    }

    return graph.invoke(state)

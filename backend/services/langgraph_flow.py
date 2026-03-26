from typing import TypedDict, List, Optional

class GraphState(TypedDict):
    user_input: str
    chat_id: str
    intent: Optional[str]
    query: Optional[str]
    max_results: Optional[int]
    papers: Optional[List]
    response: Optional[str]

from services.llm_service import generate_response

def classify_intent(state: GraphState):
    prompt = f"""
    Classify the user input into one of:
    - new_topic
    - follow_up
    - action

    Input: {state['user_input']}

    Only return one word.
    """

    result = generate_response(prompt).strip().lower()

    if "follow" in result:
        intent = "follow_up"
    elif "action" in result:
        intent = "action"
    else:
        intent = "new_topic"

    state["intent"] = intent
    return state

def generate_query(state: GraphState):
    prompt = f"""
    Understand the user's research topic and convert it into an arXiv search query.
    First try to find the core idea of the user, see if any specific methods, domains, or keywords are mentioned, also if there are max_number/min_number of papers needed.
    Generate a concise search query that captures the essence of the user's research interest, suitable for arXiv's search syntax.
Input: {state['user_input']}

Return only the search query.
"""

    query = generate_response(prompt)
    state["query"] = query.strip()
    return state

from services.arxiv_service import fetch_papers

def fetch_arxiv(state: GraphState):
    papers = fetch_papers(state["query"], max_results=5)
    state["papers"] = papers
    return state

from services.vector_service import add_documents

def store_papers(state: GraphState):
    collection_name = f"chat_{state['chat_id']}"
    add_documents(collection_name, state["papers"])
    return state

def generate_response_node(state: GraphState):
    count = len(state.get("papers", []))
    state["response"] = f"Found {count} relevant papers"
    return state

def route_intent(state: GraphState):
    if state["intent"] == "new_topic":
        return "generate_query"
    elif state["intent"] == "follow_up":
        return "generate_response"
    elif state["intent"] == "action":
        return "generate_response"
    
from langgraph.graph import StateGraph

def build_graph():
    builder = StateGraph(GraphState)

    # Nodes
    builder.add_node("intent", classify_intent)
    builder.add_node("generate_query", generate_query)
    builder.add_node("fetch_arxiv", fetch_arxiv)
    builder.add_node("store", store_papers)
    builder.add_node("generate_response", generate_response_node)

    # Flow
    builder.set_entry_point("intent")

    builder.add_conditional_edges(
        "intent",
        route_intent,
        {
            "generate_query": "generate_query",
            "generate_response": "generate_response"
        }
    )

    builder.add_edge("generate_query", "fetch_arxiv")
    builder.add_edge("fetch_arxiv", "store")
    builder.add_edge("store", "generate_response")

    return builder.compile()

graph = build_graph()

def run_graph(user_input: str, chat_id: str):
    state = {
        "user_input": user_input,
        "chat_id": chat_id,
        "intent": None,
        "query": None,
        "papers": [],
        "response": None
    }

    result = graph.invoke(state)
    return result
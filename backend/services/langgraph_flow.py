from typing import TypedDict, List, Optional

class GraphState(TypedDict):
    user_input: str
    paper_count: int
    chat_id: str
    intent: Optional[str]
    query: Optional[str]
    max_results: Optional[int]
    papers: Optional[List]
    response: Optional[str]

from services.llm_service import generate_response

def talkable(state: GraphState):
    prompt = f"""
You are an academic research assistant.

Rules:
- If input is unrelated to research → respond EXACTLY: not_talkable
- If greeting/small talk → respond with a greeting AND include the word: greeting
- Otherwise → respond EXACTLY: proceed

User Input: {state["user_input"]}
"""

    response = generate_response(prompt).strip().lower()
    print(response)
    state["response"] = response
    return state

def route_talkable(state: GraphState):
    res = state["response"]

    if "not_talkable" in res:
        return "end"
    elif "greeting" in res:
        return "end"
    else:
        return "intent"
    

def classify_intent(state: GraphState):
    prompt = f"""
Classify the user input into one of:
- new_topic (user is asking for papers / searching a topic)
- follow_up (referring to previous results)
- action (operations like save, delete, summarize)

Input: {state['user_input']}

Only return one word exactly: new_topic, follow_up, or action.
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

import json

def generate_query(state: GraphState):
    prompt = f"""
You are a strict JSON generator.

Understand the user's research topic and convert it into an arXiv search query.

Rules:
- Extract core idea, methods, domain
- Detect paper count if mentioned(Eg. "top 6 papers on X" == paper_count: 6)
- Default paper_count = 5(if not specified)
- Max paper_count = 10(to avoid overload)

Return ONLY valid JSON like this:
{{
  "query": "your search query",
  "paper_count": 5
}}

User Input:
{state['user_input']}
"""

    response = generate_response(prompt)


    try:
        data = json.loads(response)
        print("Parsed JSON:", data)
        state["query"] = data.get("query", state["user_input"])
        state["paper_count"] = min(int(data.get("paper_count", 5)), 10)

    except Exception as e:
        print("JSON PARSE ERROR:", e)

        # fallback (VERY IMPORTANT)
        state["query"] = state["user_input"]
        state["paper_count"] = 5

    return state

from services.arxiv_service import fetch_papers

def fetch_arxiv(state: GraphState):
    print(state["paper_count"])
    papers = fetch_papers(state["query"], state["paper_count"])
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
    builder.add_node("talkable", talkable)
    builder.add_node("intent", classify_intent)
    builder.add_node("generate_query", generate_query)
    builder.add_node("fetch_arxiv", fetch_arxiv)
    builder.add_node("store", store_papers)
    builder.add_node("generate_response", generate_response_node)

    # ✅ Start from talkable
    builder.set_entry_point("talkable")

    # ✅ Conditional routing from talkable
    builder.add_conditional_edges(
        "talkable",
        route_talkable,
        {
            "intent": "intent",
            "end": "__end__"
        }
    )

    # Existing flow
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
        "paper_count": None,
        "chat_id": chat_id,
        "intent": None,
        "query": None,
        "papers": [],
        "response": None
    }
    result = graph.invoke(state)
    return result
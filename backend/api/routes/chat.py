from fastapi import APIRouter
from pydantic import BaseModel
from db.memory_store import create_chat
from models.schemas import ChatMessageRequest
from db.memory_store import add_message
from services.arxiv_service import fetch_papers
from services.vector_service import add_documents
from utils.helpers import generate_search_query

router = APIRouter()

class CreateChatRequest(BaseModel):
    user_id: str
    title: str

@router.post("/create")
def create_chat_api(req: CreateChatRequest):
    chat_id = create_chat(req.user_id, req.title)
    return {"chat_id": chat_id}


router = APIRouter()

from services.langgraph_flow import run_graph

@router.post("/message")
def chat_message(req: ChatMessageRequest):
    user_input = req.message
    chat_id = req.chat_id
    user_id = req.user_id

    if not chat_id:
        chat_id = create_chat(user_id, title=user_input[:30])

    add_message(chat_id, "user", user_input)


    # 🧠 Run LangGraph
    result = run_graph(user_input, chat_id)
    papers = result.get("papers", [])
    response_text = result.get("response", "")

    add_message(chat_id, "assistant", response_text)

    return {
        "chat_id": chat_id,
        "papers": papers,
        "message": response_text
    }
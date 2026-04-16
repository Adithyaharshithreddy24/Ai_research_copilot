from fastapi import APIRouter
from models.schemas import LoginRequest
from db.memory_store import create_user, create_chat

router = APIRouter()


@router.post("/login")
def login(req: LoginRequest):
    user_id = create_user(req.name)

    # ✅ auto-create 1 chat
    chat_id = create_chat(user_id, "New Chat")

    return {
        "user_id": user_id,
        "chat_id": chat_id
    }
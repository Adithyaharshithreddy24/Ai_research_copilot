from typing import Optional, List, Dict
from pydantic import BaseModel


# =========================
# 🔐 AUTH
# =========================
class LoginRequest(BaseModel):
    name: str
    email: str


# =========================
# 💬 CHAT (ONLY RESPONSE MODEL NEEDED)
# =========================
class ChatMessageResponse(BaseModel):
    chat_id: str
    papers: List[Dict]
    message: str


# =========================
# ⚙️ ACTIONS
# =========================
class ActionRequest(BaseModel):
    chat_id: str


class CitationRequest(BaseModel):
    chat_id: str
    style: str
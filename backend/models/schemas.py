from typing import Optional, List, Dict
from pydantic import BaseModel


# =========================
# 🔐 AUTH
# =========================
class LoginRequest(BaseModel):
    name: str


# =========================
# 💬 CHAT
# =========================
class ChatMessageRequest(BaseModel):
    user_id: str
    message: str
    chat_id: Optional[str] = None

    # OPTIONAL: metadata (useful later)
    has_files: Optional[bool] = False


class ChatMessageResponse(BaseModel):
    chat_id: str
    papers: List[Dict]
    message: str

    # OPTIONAL: debugging / UI
    sources: Optional[List[str]] = []


# =========================
# ⚙️ ACTIONS
# =========================
class ActionRequest(BaseModel):
    chat_id: str


class CitationRequest(BaseModel):
    chat_id: str
    style: str  # "APA", "IEEE", "MLA"
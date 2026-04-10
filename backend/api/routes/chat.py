from fastapi import APIRouter, UploadFile, File, Form
from typing import List, Optional, Union

from db.memory_store import add_message, create_chat
from services.langgraph_flow import run_graph

from services.pdf_service import extract_text
from services.chunk_service import chunk_text
from services.vector_service import add_text_chunks

import os
import uuid
import aiofiles

router = APIRouter()

UPLOAD_DIR = "data/pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/message")
async def chat_message(
    user_id: str = Form(...),
    message: str = Form(...),
    chat_id: Optional[str] = Form(None),
    mode: str = Form("keyword"),
    files: Optional[List[Union[UploadFile, str]]] = File(None)
):
    # ------------------------
    # 🧠 CREATE CHAT
    # ------------------------
    if not chat_id:
        chat_id = create_chat(user_id, message[:30])

    add_message(chat_id, "user", message)

    # ------------------------
    # 📄 HANDLE FILES
    # ------------------------
    valid_files = []

    if files:
        for f in files:
            # ✅ Ignore Swagger empty strings
            if isinstance(f, str):
                continue

            if f and hasattr(f, "filename") and f.filename:
                valid_files.append(f)

    if valid_files:
        all_chunks = []

        try:
            for file in valid_files:
                file_id = str(uuid.uuid4())
                path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"

                # Save file
                async with aiofiles.open(path, "wb") as buffer:
                    content = await file.read()
                    await buffer.write(content)

                # Extract text
                text = extract_text(path)

                # Chunk
                chunks = chunk_text(text)

                all_chunks.extend(chunks)

            # Store in vector DB
            add_text_chunks(f"chat_{chat_id}", all_chunks)
        except Exception as e:
            print("CHAT FILE PROCESSING ERROR:", e)

    # ------------------------
    # 🤖 RUN GRAPH
    # ------------------------
    try:
        result = run_graph(message, chat_id, mode=mode)
        response_text = result.get("response", "")
        papers = result.get("papers", [])
    except Exception as e:
        print("CHAT GRAPH ERROR:", e)
        response_text = (
            "I could not reach external research/model services right now. "
            "Please try again in a moment."
        )
        papers = []

    add_message(chat_id, "assistant", response_text)

    return {
        "chat_id": chat_id,
        "papers": papers,
        "message": response_text
    }

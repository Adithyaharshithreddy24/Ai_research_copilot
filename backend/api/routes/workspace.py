from fastapi import APIRouter, UploadFile, File
import uuid
import os
import aiofiles

from services.pdf_service import extract_text
from services.chunk_service import chunk_text
from services.vector_service import add_text_chunks

router = APIRouter()

UPLOAD_DIR = "data/pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), chat_id: str = ""):
    try:
        file_id = str(uuid.uuid4())
        file_path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"

        async with aiofiles.open(file_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)

        text = extract_text(file_path)
        chunks = chunk_text(text)

        add_text_chunks(f"chat_{chat_id}", chunks)

        return {
            "file": file.filename,
            "chunks": len(chunks),
            "message": "PDF processed and stored"
        }
    except Exception as e:
        print("WORKSPACE UPLOAD ERROR:", e)
        return {
            "file": getattr(file, "filename", "unknown.pdf"),
            "chunks": 0,
            "message": "Could not process this PDF right now. Please try another file."
        }

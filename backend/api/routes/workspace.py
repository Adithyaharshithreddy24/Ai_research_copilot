from fastapi import FastAPI, UploadFile, File
import os
import uuid
import aiofiles
from fastapi import APIRouter

from services.pdf_service import parse_text, parse_ocr, parse_images

router = APIRouter()

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

UPLOAD_DIR = os.path.join(BASE_DIR, "data", "pdfs")

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = f"{UPLOAD_DIR}/{file_id}_{file.filename}"

    # Save file (async)
    async with aiofiles.open(file_path, "wb") as buffer:
        content = await file.read()
        await buffer.write(content)

    try:
        text = parse_text(file_path)

        if len(text.strip()) < 50:
            text = parse_ocr(file_path)

        images = parse_images(file_path)

        return {
            "file": file.filename,
            "text": text,
            "images": images
        }

    except Exception as e:
        return {"error": str(e)}
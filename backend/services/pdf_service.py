import os
import uuid
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def generate_gap_pdf(gaps):
    filename = f"data/pdfs/{uuid.uuid4()}.pdf"

    os.makedirs("data/pdfs", exist_ok=True)

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Research Gap Analysis", styles['Title']))
    elements.append(Spacer(1, 12))

    for paper in gaps:
        elements.append(Paragraph(paper["title"], styles['Heading2']))
        elements.append(Paragraph(paper["gap"], styles['BodyText']))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return filename

def parse_text(file_path):
    import fitz
    doc = fitz.open(file_path)
    
    text = ""
    for page in doc:
        text += page.get_text()
    
    return text

def parse_images(file_path):
    import fitz
    import os

    doc = fitz.open(file_path)
    image_paths = []

    os.makedirs("images", exist_ok=True)

    for page_index, page in enumerate(doc):
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)

            path = f"images/page{page_index}_img{img_index}.png"
            with open(path, "wb") as f:
                f.write(base_image["image"])

            image_paths.append(path)

    return image_paths

def parse_ocr(file_path):
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(file_path)
    text = ""

    for page in doc:
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text += pytesseract.image_to_string(img)

    return text
from fastapi import APIRouter
from models.schemas import ActionRequest, CitationRequest
from services.vector_service import get_all_documents
from services.llm_service import (
    generate_literature_review,
    generate_research_gap,
    generate_citations
)

router = APIRouter()
STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "this", "are", "were", "have",
    "has", "into", "their", "about", "using", "use", "used", "between", "within",
    "based", "study", "paper", "approach", "model", "models", "results"
}


def _top_terms(texts, limit=6):
    counts = {}
    for text in texts[:10]:
        for token in text.lower().split():
            token = "".join(ch for ch in token if ch.isalnum())
            if len(token) < 4 or token in STOPWORDS:
                continue
            counts[token] = counts.get(token, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]]


def _local_literature_review(texts):
    terms = _top_terms(texts)
    intro = (
        f"This review synthesizes {min(len(texts), 10)} document(s) in the current workspace "
        "and highlights recurring patterns from available abstracts/chunks."
    )
    methods = []
    combined = " ".join(texts[:8]).lower()
    for key in ["transformer", "reinforcement", "benchmark", "simulation", "survey", "retrieval", "classification"]:
        if key in combined:
            methods.append(key)
    if not methods:
        methods = ["comparative analysis", "data-driven evaluation"]

    findings = [
        "Most documents emphasize performance improvements in constrained settings.",
        "Generalization and real-world robustness appear less consistently addressed.",
    ]
    if terms:
        findings.insert(0, f"Frequent themes include: {', '.join(terms[:4])}.")

    return {
        "introduction": intro,
        "key_themes": ", ".join(terms) if terms else "No dominant themes could be extracted yet.",
        "methods": ", ".join(methods),
        "findings": " ".join(findings),
        "trends": "Recent work appears to prioritize stronger benchmarks and scalable deployment."
    }


def _format_local_citation(paper, style: str, idx: int):
    title = str(paper.get("title", f"Untitled Paper {idx}")).strip()
    authors = str(paper.get("authors", "")).strip() or "Unknown Author"
    url = str(paper.get("pdf_url", "")).strip()
    year = "n.d."

    normalized_style = (style or "APA").upper()
    if normalized_style == "MLA":
        base = f'{authors}. "{title}." arXiv, {year}.'
    elif normalized_style == "IEEE":
        base = f'[{idx}] {authors}, "{title}," arXiv, {year}.'
    elif normalized_style == "CHICAGO":
        base = f"{authors}. {year}. \"{title}.\" arXiv."
    else:  # APA default
        base = f"{authors}. ({year}). {title}. arXiv."

    return f"{base} {url}".strip()


@router.post("/literature")
def literature(req: ActionRequest):
    try:
        docs = get_all_documents(f"chat_{req.chat_id}")
        texts = docs.get("documents", [])

        if not texts:
            return {"literature_review": "No documents found in this chat yet."}

        try:
            review = generate_literature_review(texts)
        except Exception as llm_error:
            print("LITERATURE LLM ERROR:", llm_error)
            review = _local_literature_review(texts)
        return {"literature_review": review}
    except Exception as e:
        print("LITERATURE ACTION ERROR:", e)
        return {"literature_review": "Could not build literature review right now."}


@router.post("/research-gap")
def research_gap(req: ActionRequest):
    try:
        docs = get_all_documents(f"chat_{req.chat_id}")

        papers = docs.get("metadatas") or []
        texts = docs.get("documents") or []

        if not texts:
            return {"gaps": []}

        gaps = []

        for i in range(min(len(texts), 5)):
            text = texts[i] if isinstance(texts[i], str) else str(texts[i] or "")
            try:
                gap = generate_research_gap(text)
            except Exception as inner_e:
                print("RESEARCH GAP ITEM ERROR:", inner_e)
                if len(text.strip()) < 80:
                    gap = "Document content is too short for reliable gap extraction."
                else:
                    gap = (
                        "Potential gap: limited discussion of limitations, external validity, "
                        "and future work directions."
                    )

            title = "Uploaded PDF"
            if i < len(papers) and isinstance(papers[i], dict):
                title = papers[i].get("title") or "Uploaded PDF"

            gaps.append({
                "title": title,
                "gap": gap
            })

        return {"gaps": gaps}
    except Exception as e:
        print("RESEARCH GAP ACTION ERROR:", e)
        return {"gaps": []}


@router.post("/citation")
def citation(req: CitationRequest):
    try:
        docs = get_all_documents(f"chat_{req.chat_id}")
        papers = docs.get("metadatas", [])

        if not papers:
            return {"citations": "No papers found in this chat yet."}

        try:
            citations = generate_citations(papers, req.style)
        except Exception as llm_error:
            print("CITATION LLM ERROR:", llm_error)
            lines = []
            for i, paper in enumerate(papers[:20], start=1):
                if isinstance(paper, dict):
                    lines.append(_format_local_citation(paper, req.style, i))
            citations = "\n".join(lines) if lines else "No papers available for citation formatting."
        return {"citations": citations}
    except Exception as e:
        print("CITATION ACTION ERROR:", e)
        return {"citations": "Could not generate citations right now."}

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


def _normalize_text(value):
    return " ".join(str(value or "").replace("\r", "\n").split()).strip()


def _clean_generated_section(value, fallback: str):
    text = str(value or "").strip()
    if not text:
        return fallback

    lines = []
    for raw_line in text.replace("\r", "\n").split("\n"):
        line = raw_line.strip(" -*\t")
        if not line:
            continue
        lower = line.lower()
        if lower in {"limitations", "missing aspects", "future work"}:
            continue
        lines.append(line)

    cleaned = " ".join(lines).strip()
    return cleaned or fallback


def _contains_any(text: str, keywords):
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def _local_research_gap(text: str, title: str = ""):
    normalized = _normalize_text(text)
    lower = normalized.lower()

    if len(normalized) < 80:
        return (
            "Limitations: Available text is too short for a strong gap analysis. "
            "Missing Aspects: More abstract or method detail is needed. "
            "Future Work: Add a fuller paper summary, methodology, and evaluation context."
        )

    limitation_points = []
    missing_points = []
    future_points = []

    if not _contains_any(lower, ["limitation", "limitations", "constraint", "drawback", "challenge"]):
        limitation_points.append("The paper does not clearly discuss its main limitations or failure cases.")
    if not _contains_any(lower, ["real-world", "deployment", "field", "practical", "industry"]):
        limitation_points.append("Validation outside controlled or benchmark settings is not clearly established.")
    if not _contains_any(lower, ["compare", "baseline", "state-of-the-art", "sota", "benchmark"]):
        limitation_points.append("Comparative evaluation against strong baselines is not fully evident.")

    if not _contains_any(lower, ["dataset", "sample", "participants", "corpus"]):
        missing_points.append("Dataset scope, diversity, or sampling details are not sufficiently visible.")
    if not _contains_any(lower, ["method", "framework", "architecture", "algorithm", "pipeline"]):
        missing_points.append("Method details are too limited to assess reproducibility with confidence.")
    if not _contains_any(lower, ["bias", "ethics", "fairness", "privacy", "security"]):
        missing_points.append("Broader concerns such as bias, ethics, privacy, or security are not addressed.")

    if not _contains_any(lower, ["future work", "next step", "extend", "extension"]):
        future_points.append("Future work should test the approach on broader datasets and realistic scenarios.")
    if not _contains_any(lower, ["generalization", "robustness", "transfer"]):
        future_points.append("Future work should evaluate robustness, generalization, and transfer performance.")
    future_points.append("Future work should include clearer ablation or comparison studies to isolate the contribution.")

    limitation = limitation_points[0] if limitation_points else "The study appears useful, but its practical boundaries are not fully clarified."
    missing = missing_points[0] if missing_points else "Important implementation and evaluation details could be expanded for stronger reproducibility."
    future = future_points[0] if future_points else "A strong next step is broader validation with more transparent evaluation criteria."

    if title:
        return f"Limitations: {limitation} Missing Aspects: {missing} Future Work: {future}"
    return f"Limitations: {limitation} Missing Aspects: {missing} Future Work: {future}"


def _top_terms(texts, limit=6):
    counts = {}
    for text in texts[:10]:
        for token in text.lower().split():
            token = "".join(ch for ch in token if ch.isalnum())
            if len(token) < 4 or token in STOPWORDS:
                continue
            counts[token] = counts.get(token, 0) + 1
    return [k for k, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]]


def _extract_sentence(text: str, keywords, fallback: str):
    cleaned = str(text or "").replace("\n", " ").strip()
    sentences = [s.strip() for s in cleaned.split(".") if s.strip()]
    for sentence in sentences:
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            return sentence + "."
    return fallback


def _local_paper_insight(text: str, title: str):
    normalized = _normalize_text(text)
    short_title = title or "Untitled paper"

    focus = _extract_sentence(
        normalized,
        ["propose", "address", "investigate", "focus", "aim", "objective"],
        f"{short_title} examines a specific problem in the current topic area."
    )
    method = _extract_sentence(
        normalized,
        ["method", "approach", "framework", "model", "algorithm", "survey"],
        "The paper uses a defined research approach, but the available summary only partially describes the method."
    )
    finding = _extract_sentence(
        normalized,
        ["result", "improve", "outperform", "demonstrate", "show", "finding"],
        "The paper reports a meaningful contribution, although the available workspace text does not expose all quantitative findings."
    )
    limitation = _extract_sentence(
        normalized,
        ["limitation", "challenge", "constraint", "future work"],
        "The paper summary does not clearly state limitations, leaving open questions about generalization, scale, or deployment."
    )

    return {
        "title": short_title,
        "focus": focus,
        "method": method,
        "finding": finding,
        "limitation": limitation,
    }


def _local_literature_review(papers, texts):
    paper_insights = []
    for i, text in enumerate(texts[:5]):
        title = f"Paper {i + 1}"
        if i < len(papers) and isinstance(papers[i], dict):
            title = str(papers[i].get("title") or title)
        paper_insights.append(_local_paper_insight(text, title))

    terms = _top_terms(texts)
    topic_text = ", ".join(terms[:4]) if terms else "the selected topic"
    compared_methods = []
    combined = " ".join(texts[:8]).lower()
    for key in ["survey", "framework", "model", "benchmark", "simulation", "classification", "detection"]:
        if key in combined:
            compared_methods.append(key)
    method_text = ", ".join(compared_methods[:4]) if compared_methods else "multiple methodological approaches"

    return {
        "overview": (
            f"This literature review examines {len(paper_insights)} paper(s) related to {topic_text}. "
            "It highlights each paper's focus, method, contribution, and limitation before synthesizing shared patterns."
        ),
        "paper_insights": paper_insights,
        "synthesis": (
            f"Across the selected papers, the literature concentrates on {topic_text} and often relies on {method_text}. "
            "The papers are connected by a common goal of improving existing understanding or performance, "
            "but they differ in scope, evidence depth, and evaluation detail."
        ),
        "research_gaps": (
            "The reviewed papers leave gaps in real-world validation, reproducibility detail, comparative benchmarking, "
            "and discussion of practical constraints such as deployment, scalability, or risk."
        ),
        "future_direction": (
            "Future studies should compare methods under shared benchmarks, report limitations more explicitly, "
            "and extend evaluation to broader and more realistic settings."
        ),
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
        papers = docs.get("metadatas") or []

        if not texts:
            return {"literature_review": "No documents found in this chat yet."}

        llm_payload = []
        for i, text in enumerate(texts[:10]):
            title = f"Paper {i + 1}"
            if i < len(papers) and isinstance(papers[i], dict):
                title = str(papers[i].get("title") or title)
            llm_payload.append({
                "title": title,
                "abstract": _normalize_text(text)[:2500]
            })

        try:
            review = generate_literature_review(llm_payload)
        except Exception as llm_error:
            print("LITERATURE LLM ERROR:", llm_error)
            review = _local_literature_review(papers, texts)

        if isinstance(review, dict):
            review = {
                "overview": _normalize_text(review.get("overview")),
                "paper_insights": [
                    {
                        "title": _normalize_text(item.get("title")),
                        "focus": _normalize_text(item.get("focus")),
                        "method": _normalize_text(item.get("method")),
                        "finding": _normalize_text(item.get("finding")),
                        "limitation": _normalize_text(item.get("limitation")),
                    }
                    for item in review.get("paper_insights", [])
                    if isinstance(item, dict)
                ],
                "synthesis": _normalize_text(review.get("synthesis")),
                "research_gaps": _normalize_text(review.get("research_gaps")),
                "future_direction": _normalize_text(review.get("future_direction")),
            }
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
            title = "Uploaded PDF"
            if i < len(papers) and isinstance(papers[i], dict):
                title = papers[i].get("title") or "Uploaded PDF"

            try:
                gap = generate_research_gap(text)
            except Exception as inner_e:
                print("RESEARCH GAP ITEM ERROR:", inner_e)
                gap = _local_research_gap(text, title=title)

            gap = _clean_generated_section(
                gap,
                _local_research_gap(text, title=title)
            )

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

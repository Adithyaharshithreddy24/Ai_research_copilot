import re

from services.vector_service import get_all_documents, query_collection
from services.llm_service import generate_response


def _normalize_text(value):
    return " ".join(str(value or "").split()).strip()


def _clean_docs(docs, max_items: int):
    cleaned = []
    for doc in docs or []:
        if not isinstance(doc, str):
            continue
        text = _normalize_text(doc)
        if len(text) < 40:
            continue
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _tokenize(text: str):
    return [token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 2]


def _contains_any(text: str, keywords):
    lower = (text or "").lower()
    return any(keyword in lower for keyword in keywords)


def _extract_papers(collection_name: str):
    try:
        data = get_all_documents(collection_name)
    except Exception:
        return []

    docs = data.get("documents", []) if isinstance(data, dict) else []
    metadatas = data.get("metadatas", []) if isinstance(data, dict) else []

    papers = []
    for idx, doc in enumerate(docs):
        metadata = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        title = _normalize_text(metadata.get("title") or f"Paper {idx + 1}")
        summary = _normalize_text(doc)
        authors = _normalize_text(metadata.get("authors", ""))
        pdf_url = _normalize_text(metadata.get("pdf_url", ""))

        if not summary:
            continue

        papers.append({
            "title": title,
            "summary": summary,
            "authors": authors,
            "pdf_url": pdf_url,
        })

    return papers


def _score_paper(question: str, paper: dict):
    q_tokens = _tokenize(question)
    haystack = " ".join([
        paper.get("title", ""),
        paper.get("summary", ""),
        paper.get("authors", ""),
    ]).lower()

    score = 0
    for token in q_tokens:
        if token in haystack:
            score += 3

    title_tokens = _tokenize(paper.get("title", ""))
    for token in q_tokens:
        if token in title_tokens:
            score += 2

    summary = paper.get("summary", "")
    if any(word in question.lower() for word in ["best", "strongest", "most useful"]):
        score += min(len(summary) // 120, 4)
        if any(word in summary.lower() for word in ["result", "improve", "outperform", "benchmark", "evaluation"]):
            score += 3

    return score


def _rank_papers(question: str, papers: list, limit: int = 3):
    ranked = sorted(
        papers,
        key=lambda paper: (_score_paper(question, paper), len(paper.get("summary", ""))),
        reverse=True,
    )
    return ranked[:limit]


def _summary_words(text: str, limit: int = 45):
    words = _normalize_text(text).split()
    if not words:
        return "Summary unavailable."
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + "..."


def _trim_to_word_count(text: str, limit: int):
    words = _normalize_text(text).split()
    if not words:
        return "Summary unavailable."
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]) + "..."


def _extract_sentence(text: str, keywords, fallback: str):
    normalized = _normalize_text(text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
    for sentence in sentences:
        lower = sentence.lower()
        if any(keyword in lower for keyword in keywords):
            return sentence
    return fallback


def _paper_note(paper: dict, index: int):
    title = paper.get("title") or f"Paper {index}"
    summary = paper.get("summary") or ""
    focus = _extract_sentence(
        summary,
        ["propose", "address", "investigate", "focus", "aim", "objective"],
        _summary_words(summary, limit=24),
    )
    method = _extract_sentence(
        summary,
        ["method", "approach", "framework", "model", "architecture", "survey", "analysis"],
        "The available summary does not expose method details clearly.",
    )
    finding = _extract_sentence(
        summary,
        ["result", "improve", "outperform", "demonstrate", "show", "finding", "identify"],
        "The available summary indicates a relevant contribution, but detailed findings are limited.",
    )
    limitation = _extract_sentence(
        summary,
        ["limitation", "challenge", "constraint", "future work"],
        "The available paper summary does not clearly state its limitations.",
    )
    return {
        "title": title,
        "focus": focus,
        "method": method,
        "finding": finding,
        "limitation": limitation,
        "summary": summary,
    }


def _determine_answer_mode(question: str):
    q = (question or "").lower()
    if any(term in q for term in ["each paper", "every paper", "each of the papers", "all papers individually", "paper-wise", "paper wise", "individual paper"]):
        return "per_paper_summary"
    if any(term in q for term in ["100 words", "100-word", "100 word"]) and any(term in q for term in ["summary", "summarize", "overview"]):
        return "word_limited_summary"
    if any(term in q for term in ["best paper", "best", "strongest", "most useful", "which paper"]):
        return "best_match"
    if any(term in q for term in ["compare", "comparison", "difference", "different", "versus", "vs"]):
        return "comparison"
    return "general"


def _question_type(question: str):
    q = (question or "").lower()
    if any(term in q for term in ["each paper", "every paper", "each of the papers", "all papers individually", "paper-wise", "paper wise", "individual paper"]):
        return "summary_each"
    if any(term in q for term in ["best paper", "best", "strongest", "most useful", "which paper"]):
        return "best"
    if any(term in q for term in ["compare", "comparison", "difference", "different", "versus", "vs"]):
        return "compare"
    if any(term in q for term in ["summary", "summarize", "overview", "100 words", "100-word", "100 word"]):
        return "summary"
    if any(term in q for term in ["method", "methods", "approach", "approaches", "technique", "techniques"]):
        return "methods"
    if any(term in q for term in ["result", "results", "finding", "findings", "conclusion", "conclusions"]):
        return "findings"
    if any(term in q for term in ["limitation", "limitations", "gap", "gaps", "weakness", "weaknesses"]):
        return "limitations"
    if any(term in q for term in ["author", "authors", "who wrote"]):
        return "authors"
    return "general"


def _papers_for_question(question: str, papers: list, limit: int = 3):
    ranked = _rank_papers(question, papers, limit=limit)
    if ranked:
        return ranked
    return papers[:limit]


def _format_numbered_notes(header: str, notes: list, fields: list):
    lines = [header]
    for idx, note in enumerate(notes, start=1):
        lines.append(f"{idx}. {note['title']}")
        for label, key in fields:
            value = note.get(key, "")
            if value:
                lines.append(f"   {label}: {value}")
    return "\n".join(lines)


def _build_general_answer(question: str, notes: list, selected: list):
    answer_mode = _determine_answer_mode(question)

    if answer_mode == "per_paper_summary":
        per_paper_limit = 100 if _contains_any(question, ["100 words", "100-word", "100 word"]) else 45
        lines = ["Answer", "Below is a paper-by-paper response based only on the retrieved papers.", "", "Evidence"]
        for idx, note in enumerate(notes, start=1):
            lines.append(f"{idx}. {note['title']}")
            lines.append(f"   Summary: {_trim_to_word_count(note['summary'], limit=per_paper_limit)}")
        lines.append("")
        lines.append("Scope")
        lines.append("This answer is limited to the papers currently stored in this chat.")
        return "\n".join(lines)

    if answer_mode == "word_limited_summary":
        joined = " ".join(note["focus"] for note in notes if note.get("focus"))
        concise = _trim_to_word_count(joined, limit=100)
        lines = ["Answer", concise, "", "Evidence"]
        for idx, note in enumerate(notes, start=1):
            lines.append(f"{idx}. {note['title']}")
        lines.append("")
        lines.append("Scope")
        lines.append("This summary is based only on the retrieved papers in the current chat.")
        return "\n".join(lines)

    if answer_mode == "best_match":
        best = selected[0]
        best_note = notes[0]
        reason = _extract_sentence(
            best["summary"],
            ["result", "improve", "outperform", "evaluation", "benchmark", "analysis"],
            "It appears to provide the clearest combination of focus, method detail, and evaluative signal in the stored paper set.",
        )
        lines = [
            "Answer",
            f"The strongest match in the current paper set is '{best['title']}'.",
            "",
            "Evidence",
            f"- Focus: {best_note['focus']}",
            f"- Method: {best_note['method']}",
            f"- Finding: {best_note['finding']}",
            f"- Why it stands out: {reason}",
        ]
        if len(selected) > 1:
            lines.append("- Other relevant papers:")
            for paper in selected[1:]:
                lines.append(f"  - {paper['title']}")
        lines.extend(["", "Scope", "This ranking is based only on the papers currently stored in this chat."])
        return "\n".join(lines)

    if answer_mode == "comparison" and len(notes) >= 2:
        lines = ["Answer", "The most relevant comparison from the current chat is shown below.", "", "Evidence"]
        for idx, note in enumerate(notes[:2], start=1):
            lines.append(f"{idx}. {note['title']}")
            lines.append(f"   Focus: {note['focus']}")
            lines.append(f"   Method: {note['method']}")
            lines.append(f"   Finding: {note['finding']}")
            lines.append(f"   Limitation: {note['limitation']}")
        lines.extend(["", "Scope", "This comparison is limited to the evidence available in the retrieved paper summaries."])
        return "\n".join(lines)

    lines = ["Answer", "Here is the best evidence-based response from the retrieved papers.", "", "Evidence"]
    for idx, note in enumerate(notes, start=1):
        lines.append(f"{idx}. {note['title']}")
        lines.append(f"   Focus: {note['focus']}")
        lines.append(f"   Method: {note['method']}")
        lines.append(f"   Finding: {note['finding']}")
        lines.append(f"   Limitation: {note['limitation']}")
    lines.extend(["", "Scope", "This answer is based only on the papers currently stored in this chat."])
    return "\n".join(lines)


def _answer_from_papers(question: str, papers: list):
    if not papers:
        return None

    qtype = _question_type(question)
    selected = _papers_for_question(question, papers, limit=3)
    notes = [_paper_note(paper, idx + 1) for idx, paper in enumerate(selected)]

    # Keep narrow handlers for a few exact cases, then fall back to a general paper-QA layout.

    if qtype == "summary_each":
        lines = ["Paper Summaries"]
        per_paper_limit = 100 if _contains_any(question, ["100 words", "100-word", "100 word"]) else 45
        for idx, note in enumerate(notes, start=1):
            lines.append(f"{idx}. {note['title']}")
            lines.append(f"   Summary: {_trim_to_word_count(note['summary'], limit=per_paper_limit)}")
        lines.append("These summaries are based only on the papers currently stored in this chat.")
        return "\n".join(lines)

    if qtype == "summary":
        if _contains_any(question, ["100 words", "100-word", "100 word"]):
            joined = " ".join(note["focus"] for note in notes if note.get("focus"))
            concise = _trim_to_word_count(joined, limit=100)
            lines = ["100-Word Summary", concise, "", "Paper References"]
            for idx, note in enumerate(notes, start=1):
                lines.append(f"{idx}. {note['title']}")
            return "\n".join(lines)
        return _format_numbered_notes("Paper Summaries", notes, [("Summary", "focus"), ("Finding", "finding")])

    if qtype == "best":
        best = selected[0]
        best_note = notes[0]
        reason = _extract_sentence(
            best["summary"],
            ["result", "improve", "outperform", "evaluation", "benchmark", "analysis"],
            "Its available summary provides the clearest combination of problem focus, method signal, and evaluative detail among the retrieved papers."
        )
        lines = [
            "Best Match",
            f"Title: {best['title']}",
            f"Why it stands out: {reason}",
            f"Focus: {best_note['focus']}",
            f"Method: {best_note['method']}",
            f"Finding: {best_note['finding']}",
            "Other relevant papers:",
        ]
        for paper in selected[1:]:
            lines.append(f"- {paper['title']}")
        lines.append("Note: This ranking is based only on the papers currently available in this chat.")
        return "\n".join(lines)

    if qtype == "methods":
        return _format_numbered_notes("Methods Across Retrieved Papers", notes, [("Method", "method"), ("Focus", "focus")])

    if qtype == "findings":
        return _format_numbered_notes("Findings Across Retrieved Papers", notes, [("Finding", "finding"), ("Focus", "focus")])

    if qtype == "limitations":
        return _format_numbered_notes("Limitations Across Retrieved Papers", notes, [("Limitation", "limitation"), ("Finding", "finding")])

    if qtype == "authors":
        lines = ["Authors In Retrieved Papers"]
        for idx, paper in enumerate(selected, start=1):
            author_text = paper.get("authors") or "Authors not available in the stored paper data."
            lines.append(f"{idx}. {paper['title']}")
            lines.append(f"   Authors: {author_text}")
        return "\n".join(lines)

    if qtype == "compare" and len(notes) >= 2:
        lines = ["Paper Comparison"]
        for idx, note in enumerate(notes[:2], start=1):
            lines.append(f"{idx}. {note['title']}")
            lines.append(f"   Focus: {note['focus']}")
            lines.append(f"   Method: {note['method']}")
            lines.append(f"   Finding: {note['finding']}")
        lines.append("Comparison: These papers differ mainly in focus, method emphasis, and the level of evaluative detail available in the stored summaries.")
        return "\n".join(lines)

    return _build_general_answer(question, notes, selected)


def rag_answer(chat_id: str, question: str):
    collection_name = f"chat_{chat_id}"
    papers = _extract_papers(collection_name)

    ranked_papers = _papers_for_question(question, papers, limit=4)
    docs = query_collection(collection_name, question)

    if not docs:
        docs = [paper["summary"] for paper in ranked_papers or papers]

    docs = _clean_docs(docs, max_items=5)

    if not docs and not papers:
        return None

    paper_context = "\n\n".join(
        [
            (
                f"Title: {paper['title']}\n"
                f"Authors: {paper.get('authors') or 'Unknown'}\n"
                f"Summary: {paper['summary']}"
            )
            for paper in (ranked_papers or papers)[:4]
        ]
    )
    context = "\n\n".join(docs[:5])

    prompt = f"""
You are a research assistant.

Rules:
- Answer ONLY from the provided paper context.
- Do not use outside knowledge.
- If the evidence is limited, say so briefly.
- Prefer this output structure:
  Answer:
  <direct answer to the user's question>

  Evidence:
  - <paper title>: <relevant support>
  - <paper title>: <relevant support>

  Scope:
  <brief note about any missing evidence>
- Handle arbitrary paper-related questions, not just fixed question types.
- If the user asks for a constrained format such as "100 words", follow it.

Paper Records:
{paper_context}

Context:
{context}

Question:
{question}
"""
    try:
        return generate_response(prompt)
    except Exception as e:
        print("RAG GENERATION ERROR:", e)
        return _answer_from_papers(question, papers)


def paper_chat_answer(chat_id: str, question: str):
    collection_name = f"chat_{chat_id}"

    query_docs = query_collection(collection_name, question)
    try:
        all_docs_resp = get_all_documents(collection_name)
        all_docs = all_docs_resp.get("documents", []) if isinstance(all_docs_resp, dict) else []
    except Exception:
        all_docs = []

    cleaned_query_docs = _clean_docs(query_docs, max_items=8)
    cleaned_all_docs = _clean_docs(all_docs, max_items=12)

    seed_docs = cleaned_all_docs[:3]
    merged = []
    seen = set()
    for item in seed_docs + cleaned_query_docs + cleaned_all_docs:
        key = item[:200]
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
        if len(merged) >= 8:
            break

    docs = merged

    if not docs:
        return None

    context = "\n\n".join(docs[:8])
    prompt = f"""
You are a research assistant helping with uploaded PDFs.

Rules:
- Use ONLY the provided document context.
- If context is insufficient, say exactly what is missing.
- Do not use outside knowledge.
- Keep the response structured and paper-grounded.

Document Context:
{context}

User Question:
{question}
"""
    try:
        return generate_response(prompt)
    except Exception as e:
        print("PAPER CHAT GENERATION ERROR:", e)
        preview = []
        for chunk in docs[:3]:
            cleaned = _normalize_text(chunk)
            if cleaned:
                preview.append(cleaned[:280])
        if not preview:
            return None
        lines = ["Uploaded Paper Evidence"]
        for idx, item in enumerate(preview, start=1):
            lines.append(f"{idx}. {item}")
        return "\n".join(lines)

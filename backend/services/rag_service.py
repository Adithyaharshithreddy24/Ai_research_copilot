from services.vector_service import get_all_documents, query_collection
from services.llm_service import generate_response


def _clean_docs(docs, max_items: int):
    cleaned = []
    for doc in docs or []:
        if not isinstance(doc, str):
            continue
        text = " ".join(doc.split()).strip()
        if len(text) < 40:
            continue
        cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def rag_answer(chat_id: str, question: str):
    collection_name = f"chat_{chat_id}"

    docs = query_collection(collection_name, question)

    # Fallback: if vector similarity fails/returns empty, use stored chat documents directly.
    if not docs:
        try:
            all_docs = get_all_documents(collection_name)
            docs = all_docs.get("documents", []) if isinstance(all_docs, dict) else []
        except Exception:
            docs = []

    docs = _clean_docs(docs, max_items=5)

    if not docs:
        return None

    context = "\n\n".join(docs[:5])

    prompt = f"""
You are a research assistant.

Use the context below to answer the question.

Context:
{context}

Question:
{question}

Answer clearly with bullet points and explanation.
"""
    try:
        return generate_response(prompt)
    except Exception as e:
        print("RAG GENERATION ERROR:", e)
        # Local fallback when external model is unavailable.
        preview = []
        for chunk in docs[:3]:
            if not isinstance(chunk, str):
                continue
            cleaned = " ".join(chunk.split())
            if cleaned:
                preview.append(cleaned[:260])

        if not preview:
            return None

        bullets = "\n".join([f"- {item}" for item in preview])
        return (
            "I could not reach the model right now, but I found relevant uploaded context:\n"
            f"{bullets}\n\n"
            "Ask a narrower question (for example: methods, results, limitations) and I can refine further."
        )


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

    # Always include opening chunks for section-level questions like "abstract",
    # then add relevant chunks from similarity search.
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
- If user asks for abstract and no explicit "Abstract" section appears,
  provide a concise "best available abstract" from opening content.

Document Context:
{context}

User Question:
{question}

Respond in clear bullet points.
"""
    try:
        return generate_response(prompt)
    except Exception as e:
        print("PAPER CHAT GENERATION ERROR:", e)
        preview = []
        for chunk in docs[:3]:
            if not isinstance(chunk, str):
                continue
            cleaned = " ".join(chunk.split())
            if cleaned:
                preview.append(cleaned[:280])
        if not preview:
            return None
        return "Uploaded-paper context found:\n" + "\n".join([f"- {x}" for x in preview])

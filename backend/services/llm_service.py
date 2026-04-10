import os
import json
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# Load backend/.env no matter where the process was started from.
BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")
load_dotenv()


def _get_api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def _get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def gemini_generate(prompt: str):
    api_key = _get_api_key()
    if not api_key:
        raise Exception(
            "Missing Gemini API key. Set GEMINI_API_KEY (preferred) or GOOGLE_API_KEY in backend/.env."
        )

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=_get_model_name(),
        contents=prompt,
    )

    text = getattr(response, "text", None)
    if text:
        return text

    try:
        return response.candidates[0].content.parts[0].text
    except Exception as exc:
        raise Exception(f"Gemini returned an empty/unsupported response: {response}") from exc


def generate_response(prompt: str):
    return gemini_generate(prompt)


def generate_literature_review(texts: list):
    combined_text = "\n\n".join(texts[:10])  # limit size

    prompt = f"""
You are a research assistant.

Given multiple research paper abstracts, generate a structured literature review with:
- Introduction
- Key Themes
- Methods
- Findings
- Trends

Abstracts:
{combined_text}

Return ONLY valid JSON:

{{
  "introduction": "...",
  "key_themes": "...",
  "methods": "...",
  "findings": "...",
  "trends": "..."
}}
"""
    return gemini_generate(prompt)


def generate_research_gap(text: str):
    prompt = f"""
Analyze this research paper abstract.

Identify:
- Limitations
- Missing aspects
- Future work

Abstract:
{text}
"""
    return gemini_generate(prompt)


def generate_citations(papers, style):
    prompt = f"""
Format the following papers into {style} citations.

Papers:
{papers}
"""
    return gemini_generate(prompt)


def _clean_discovery_item(item: dict):
    title = str(item.get("title", "AI research suggestion")).strip()
    summary = str(item.get("summary", "Suggested research direction.")).strip()
    authors = item.get("authors", []) if isinstance(item.get("authors", []), list) else []
    pdf_url = str(item.get("pdf_url", "")).strip()

    # Guard against markdown/json noise leaking into titles.
    bad_title = not title or title in {"```json", "```", "[", "]", "{", "}", ","}
    if bad_title or title.startswith("```") or title.startswith("[") or title.startswith("{"):
        title = "AI research suggestion"

    return {
        "title": title,
        "summary": summary or "Suggested research direction.",
        "authors": authors,
        "pdf_url": pdf_url,
    }


def _try_parse_discovery_json(raw: str, max_results: int):
    candidates = [raw]
    stripped = raw.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            candidates.append("\n".join(lines[1:-1]).strip())

    l_bracket = stripped.find("[")
    r_bracket = stripped.rfind("]")
    if l_bracket != -1 and r_bracket != -1 and r_bracket > l_bracket:
        candidates.append(stripped[l_bracket:r_bracket + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except Exception:
            continue

        if isinstance(data, dict):
            # Handle {"papers": [...]} style outputs.
            arr = data.get("papers")
            if isinstance(arr, list):
                data = arr

        if isinstance(data, list):
            cleaned = []
            for item in data[:max_results]:
                if isinstance(item, dict):
                    cleaned.append(_clean_discovery_item(item))
            if cleaned:
                return cleaned

    return None


def generate_discovery_suggestions(topic: str, max_results: int = 5):
    prompt = f"""
You are a research discovery assistant.

For the topic below, suggest up to {max_results} relevant real-world research directions.
If uncertain about exact citation details, be explicit and avoid inventing URLs.

Topic:
{topic}

Return ONLY valid JSON as an array of objects:
[
  {{
    "title": "short title",
    "summary": "why this direction matters and what to search for",
    "authors": ["optional", "names or groups"],
    "pdf_url": "leave empty string if unknown"
  }}
]
"""
    raw = gemini_generate(prompt)

    parsed = _try_parse_discovery_json(raw, max_results=max_results)
    if parsed:
        return parsed

    # Fallback if model response is not strict JSON.
    lines = []
    for ln in raw.splitlines():
        value = ln.strip("- ").strip()
        if not value:
            continue
        if value in {"```json", "```", "[", "]", "{", "}", ","}:
            continue
        if value.startswith("```"):
            continue
        lines.append(value)

    suggestions = []
    for line in lines[:max_results]:
        suggestions.append({
            "title": f"AI suggestion: {line[:80]}",
            "summary": line,
            "authors": [],
            "pdf_url": "",
        })
    return suggestions or [{
        "title": "AI research suggestion",
        "summary": f"Explore current literature for: {topic}",
        "authors": [],
        "pdf_url": "",
    }]

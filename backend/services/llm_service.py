import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(
    api_key=os.getenv("GEMINI_API_KEY")
)

llm = genai.GenerativeModel("gemini-1.5-flash")

def generate_response(prompt: str):
    response = llm.generate_content(prompt)
    return response.text


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
"""

    response = llm.generate_content(prompt)
    return response.text


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

    response = llm.generate_content(prompt)
    return response.text

def generate_citations(papers, style):
    prompt = f"""
Format the following papers into {style} citations.

Papers:
{papers}
"""

    response = llm.generate_content(prompt)
    return response.text
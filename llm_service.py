"""
LLM Service — supports Groq, OpenAI, and Gemini via OpenAI-compatible API.

FIX #5: Strips markdown code fences from LLM responses so JSON.parse works.
"""

import os
import re
import json
from openai import OpenAI


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that LLMs love to add."""
    text = text.strip()
    # Strip opening fence (```json, ```JSON, ``` etc.)
    text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text)
    # Strip closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


class LLMService:
    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key

        base_urls = {
            "groq":   "https://api.groq.com/openai/v1",
            "openai": "https://api.openai.com/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
        }
        base_url = base_urls.get(self.provider, "https://api.groq.com/openai/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY is not set. Please add it to your .env file:\n"
                "  LLM_PROVIDER=groq\n"
                "  LLM_API_KEY=gsk_your_key_here\n"
                "  LLM_MODEL=llama-3.3-70b-versatile"
            )
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        return response.choices[0].message.content.strip()

    # ── Prompt templates ──────────────────────────────────────────────────────

    def extract_fields(self, text: str, fields: str = "DOB, mobile number, email, name") -> str:
        system = (
            "You are an expert at extracting structured information from documents. "
            "Extract ONLY what is explicitly present. If a field is missing, say 'Not found'. "
            "Return ONLY a valid JSON object — no markdown, no explanation."
        )
        user = (
            f"Extract the following fields from this document:\n{fields}\n\n"
            f"Document:\n{text[:8000]}\n\n"
            "Return a JSON object with the field names as keys."
        )
        raw = self._chat(system, user)
        return _strip_code_fences(raw)

    def generate_mcq(self, text: str, difficulty: str = "medium", count: int = 5) -> str:
        system = (
            "You are an expert educator. Generate multiple-choice questions from the provided text. "
            "Return ONLY a valid JSON array — no markdown fences, no extra text."
        )
        user = (
            f"Generate {count} {difficulty}-difficulty MCQs from this text.\n\n"
            f"Text:\n{text[:8000]}\n\n"
            "Return a JSON array where each item has:\n"
            '  "question": string\n'
            '  "options": ["A) ...", "B) ...", "C) ...", "D) ..."]\n'
            '  "answer": "A" (just the letter)\n'
            '  "explanation": one sentence\n'
            "Return ONLY the JSON array."
        )
        raw = self._chat(system, user, max_tokens=3000)
        return _strip_code_fences(raw)

    def summarize(self, text: str) -> str:
        system = (
            "You are an expert at summarizing documents. "
            "Extract the most important key points as a clear, concise bullet list."
        )
        user = (
            f"Summarize the following text into 5-10 key bullet points:\n\n"
            f"{text[:8000]}\n\n"
            "Format each point starting with a bullet character."
        )
        return self._chat(system, user)

    def search(self, text: str, query: str) -> str:
        system = (
            "You are a search assistant. Find and return all relevant sections "
            "from the document that match the user's query. Be specific."
        )
        user = (
            f"Search query: {query}\n\n"
            f"Document content:\n{text[:10000]}\n\n"
            "Return all matching lines, rows, or paragraphs. "
            "If nothing matches, say 'No matching results found.'"
        )
        return self._chat(system, user)

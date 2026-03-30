"""
LLM Service — supports Groq, OpenAI, and Gemini (same OpenAI-compatible API).
"""

import os
import json
from openai import OpenAI


class LLMService:
    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider.lower()
        self.model = model
        self.api_key = api_key

        base_urls = {
            "groq": "https://api.groq.com/openai/v1",
            "openai": "https://api.openai.com/v1",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
        }
        base_url = base_urls.get(self.provider, "https://api.groq.com/openai/v1")
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def _chat(self, system: str, user: str, max_tokens: int = 2000) -> str:
        if not self.api_key:
            raise ValueError(
                "LLM_API_KEY is not set. Please add it to your .env file:\n"
                "LLM_PROVIDER=groq\n"
                "LLM_API_KEY=gsk_your_key_here\n"
                "LLM_MODEL=llama3-70b-8192"
            )
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content.strip()

    # ── Prompt templates ──────────────────────────────────────────────────────

    def extract_fields(self, text: str, fields: str = "DOB, mobile number, email, name") -> str:
        system = (
            "You are an expert at extracting structured information from documents. "
            "The text may come from OCR and contain noise, garbled characters, or merged words. "
            "Use your best judgment to reconstruct and extract the correct values. "
            "For example: '&@' near an email likely means '@', 'acin' likely means 'ac.in', "
            "run-together text like '+91-7070511022 B in/krishna' contains a phone number. "
            "Extract ONLY what is explicitly present or can be confidently inferred from the noisy text. "
            "If a field is truly missing and cannot be inferred, say 'Not found'. "
            "Return output in clean JSON format."
        )
        user = (
            f"Extract the following fields from this document:\n{fields}\n\n"
            f"Document (may contain OCR noise):\n{text[:8000]}\n\n"
            "Return a JSON object with the field names as keys. "
            "Clean up any OCR artifacts in the extracted values (fix spacing, symbols, domains)."
        )
        return self._chat(system, user)

    def generate_mcq(self, text: str, difficulty: str = "medium", count: int = 5) -> str:
        system = (
            "You are an expert educator. Generate multiple-choice questions from the provided text. "
            "Always return a valid JSON array, no extra text."
        )
        user = (
            f"Generate {count} {difficulty}-difficulty MCQs from this text.\n\n"
            f"Text:\n{text[:8000]}\n\n"
            "Return a JSON array where each item has:\n"
            '  "question": string\n'
            '  "options": ["A) ...", "B) ...", "C) ...", "D) ..."]\n'
            '  "answer": "A" (just the letter)\n'
            '  "explanation": one sentence\n'
            "Return ONLY the JSON array, no other text."
        )
        return self._chat(system, user, max_tokens=3000)

    def summarize(self, text: str) -> str:
        system = (
            "You are an expert at summarizing documents. "
            "The text may come from OCR and contain noise — ignore garbled characters and focus on meaning. "
            "Extract the most important key points as a clear, concise bullet list."
        )
        user = (
            f"Summarize the following text into 5–10 key bullet points:\n\n"
            f"{text[:8000]}\n\n"
            "Format each point starting with '• '"
        )
        return self._chat(system, user)

    def search(self, text: str, query: str) -> str:
        system = (
            "You are a search assistant. Find and return all relevant sections "
            "from the document that match the user's query. "
            "The text may come from OCR — clean up any garbled characters before presenting results. "
            "Be specific and present cleaned, readable results."
        )
        user = (
            f"Search query: {query}\n\n"
            f"Document content:\n{text[:10000]}\n\n"
            "Return all matching lines, rows, or paragraphs. "
            "Clean up any OCR noise in the results. "
            "If nothing matches, say 'No matching results found.'"
        )
        return self._chat(system, user)
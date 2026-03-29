# AI Document Agent

Upload any document (PDF, DOCX, Excel, CSV, JSON, TXT, Image) and let an AI
extract structured information, generate MCQs, summarize key points, or search
inside it.

---

## Project Structure

```
ai-document-agent/
├── main.py              # FastAPI app — all endpoints, caching, error handling
├── file_readers.py      # Parsers for PDF, DOCX, Excel, CSV, JSON, TXT, RTF, Image
├── llm_service.py       # Pluggable LLM client (Groq / OpenAI / Gemini)
├── startup.py           # Local dev runner (loads .env, prints config)
├── requirements.txt
├── render.yaml          # Render.com deploy config
├── runtime.txt          # Python version pin
├── .env.example         # Copy to .env and add your API key
├── .gitignore
└── static/
    └── index.html       # Frontend UI
```

---

## API Endpoints

| Method | Path                    | Description                         |
|--------|-------------------------|-------------------------------------|
| POST   | `/upload`               | Upload a file, returns `file_id`    |
| POST   | `/extract`              | Extract fields (name, DOB, email…)  |
| POST   | `/generate_mcq`         | Generate MCQ quiz (JSON)            |
| POST   | `/summarize_key_points` | Bullet-point key points             |
| POST   | `/search`               | Search inside a file with a query   |
| GET    | `/files`                | List uploaded files (current session)|
| DELETE | `/files/{file_id}`      | Delete an uploaded file              |
| GET    | `/debug/env`            | Check LLM config status             |

Full interactive docs: `http://localhost:8000/docs`

---

## Quickstart (Local)

### 1 — Prerequisites

- Python 3.10+
- Tesseract OCR *(optional — only for scanned PDFs and images)*:
  - **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr`
  - **macOS:** `brew install tesseract`
  - **Windows:** [download installer](https://github.com/UB-Mannheim/tesseract/wiki)

### 2 — Clone & install

```bash
git clone <your-repo-url>
cd ai-document-agent
pip install -r requirements.txt
```

### 3 — Configure your LLM key

```bash
cp .env.example .env
# Edit .env and set your API key
```

**Supported providers (all have free tiers):**

| Provider | LLM_PROVIDER | LLM_MODEL               | Get key |
|----------|-------------|--------------------------|---------|
| Groq     | `groq`      | `llama-3.3-70b-versatile`| [console.groq.com/keys](https://console.groq.com/keys) |
| OpenAI   | `openai`    | `gpt-4o`                 | [platform.openai.com](https://platform.openai.com/api-keys) |
| Gemini   | `gemini`    | `gemini-1.5-flash`       | [aistudio.google.com](https://aistudio.google.com/app/apikey) |

### 4 — Run

```bash
python startup.py
```

Open http://localhost:8000 for the UI, or http://localhost:8000/docs for the API.

---

## Deploy on Render

1. Push your code to GitHub
2. Go to [render.com](https://render.com) → **New → Web Service**
3. Connect your repo — Render auto-detects `render.yaml`
4. In **Environment Variables**, set `LLM_API_KEY`
5. Deploy

---

## Supported File Types

| Type | Extensions | Notes |
|------|-----------|-------|
| PDF | `.pdf` | Text extraction + table extraction. OCR fallback if Tesseract installed. |
| Word | `.docx`, `.doc` | Paragraphs + tables (resumes, invoices, reports) |
| Excel | `.xlsx`, `.xls` | All sheets, auto-truncated for LLM context |
| CSV | `.csv` | Auto-detects encoding |
| JSON | `.json` | Pretty-printed |
| Text | `.txt` | UTF-8 with Latin-1 fallback |
| RTF | `.rtf` | Via striprtf library |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp` | OCR via Tesseract |

---

## Example API Calls

```bash
# Upload
curl -X POST http://localhost:8000/upload -F "file=@resume.pdf"

# Extract fields
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "fields": "name, dob, mobile, email"}'

# Generate MCQs
curl -X POST http://localhost:8000/generate_mcq \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "difficulty": "medium", "count": 5}'

# Summarize
curl -X POST http://localhost:8000/summarize_key_points \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123"}'

# Search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"file_id": "abc123", "query": "machine learning"}'

# List files
curl http://localhost:8000/files

# Delete file
curl -X DELETE http://localhost:8000/files/abc123
```

---

## Notes

- Uploaded files live in `uploads/` and are tracked in memory (cleared on restart).
  For production, add a database + cloud storage.
- Parsed text is cached in memory — repeated tasks on the same file are instant.
- Large files are auto-truncated to fit LLM context windows (~8K–15K chars).
- OCR requires Tesseract installed on the system.

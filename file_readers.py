"""
File readers for PDF, DOCX, Excel, CSV, JSON, TXT, RTF, and Images (OCR).
"""

import re
import os
import json as json_lib
from pathlib import Path
from PIL import Image

# ── Tesseract — optional ──────────────────────────────────────────────────────
try:
    import pytesseract
    if os.name == "nt":
        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False


# ── PyMuPDF — optional (for PDF OCR fallback) ────────────────────────────────
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


# ── PDF ───────────────────────────────────────────────────────────────────────

def _ocr_pdf(path: str) -> str:
    """Fallback: render each PDF page to image, then OCR with Tesseract."""
    if not PYMUPDF_AVAILABLE:
        return ""
    if not TESSERACT_AVAILABLE:
        return ""

    text_parts = []
    try:
        doc = fitz.open(path)
        for page_num in range(min(len(doc), 20)):  # cap at 20 pages
            page = doc[page_num]
            # Render page at 2x resolution for better OCR
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_text = pytesseract.image_to_string(img)
            if page_text.strip():
                text_parts.append(page_text.strip())
        doc.close()
    except Exception:
        pass

    return "\n\n".join(text_parts)


def read_pdf(path: str) -> str:
    import pdfplumber

    text_parts = []
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

                # Also grab tables on this page
                tables = page.extract_tables()
                for table in tables:
                    rows = []
                    for row in table:
                        cells = [str(c).strip() if c else "" for c in row]
                        rows.append(" | ".join(cells))
                    if rows:
                        text_parts.append("\n".join(rows))
    except Exception as e:
        return f"[PDF read error: {e}]"

    full_text = "\n".join(text_parts).strip()

    # If pdfplumber got very little text, try OCR fallback
    if len(full_text) < 100:
        ocr_text = _ocr_pdf(path)
        if len(ocr_text) > len(full_text):
            return ocr_text

    if not full_text:
        return "[This PDF appears to be image-based. Install Tesseract + PyMuPDF for OCR.]"
    return full_text


# ── DOCX — FIX #6: now reads tables too ──────────────────────────────────────

def read_docx(path: str) -> str:
    from docx import Document

    doc = Document(path)
    parts = []

    # Paragraphs
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            parts.append(text)

    # Tables — very common in resumes, invoices, reports
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(" | ".join(cells))
        if rows:
            parts.append("\n".join(rows))

    return "\n\n".join(parts)


# ── Excel — FIX #8: smarter truncation ───────────────────────────────────────

MAX_EXCEL_CHARS = 15000  # generous but won't blow up LLM context

def read_excel(path: str) -> str:
    import pandas as pd

    ext = Path(path).suffix.lower()
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"

    try:
        xl = pd.ExcelFile(path, engine=engine)
        parts = []
        total_chars = 0

        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            header = f"=== Sheet: {sheet} ({len(df)} rows × {len(df.columns)} cols) ==="
            sheet_text = df.to_string(index=False)

            # Truncate per-sheet if needed
            remaining = MAX_EXCEL_CHARS - total_chars
            if remaining <= 0:
                parts.append(f"=== Sheet: {sheet} (skipped — text limit reached) ===")
                break

            if len(sheet_text) > remaining:
                sheet_text = sheet_text[:remaining] + f"\n... [truncated, {len(df)} total rows]"

            parts.append(header)
            parts.append(sheet_text)
            total_chars += len(header) + len(sheet_text)

        return "\n\n".join(parts)
    except Exception as e:
        return f"[Excel read error: {e}]"


# ── CSV — NEW ─────────────────────────────────────────────────────────────────

def read_csv(path: str) -> str:
    import pandas as pd

    try:
        # Try common encodings
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            return "[CSV read error: could not detect encoding]"

        header = f"=== CSV: {len(df)} rows × {len(df.columns)} cols ==="
        text = df.to_string(index=False)
        if len(text) > MAX_EXCEL_CHARS:
            text = text[:MAX_EXCEL_CHARS] + f"\n... [truncated, {len(df)} total rows]"
        return f"{header}\n{text}"
    except Exception as e:
        return f"[CSV read error: {e}]"


# ── JSON — NEW ────────────────────────────────────────────────────────────────

def read_json(path: str) -> str:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json_lib.loads(raw)
        pretty = json_lib.dumps(data, indent=2, ensure_ascii=False)
        if len(pretty) > MAX_EXCEL_CHARS:
            pretty = pretty[:MAX_EXCEL_CHARS] + "\n... [truncated]"
        return pretty
    except json_lib.JSONDecodeError as e:
        return f"[JSON parse error: {e}]"
    except Exception as e:
        return f"[JSON read error: {e}]"


# ── TXT ───────────────────────────────────────────────────────────────────────

def read_txt(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(path).read_text(encoding="latin-1")


# ── RTF ───────────────────────────────────────────────────────────────────────

def read_rtf(path: str) -> str:
    try:
        from striprtf.striprtf import rtf_to_text
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        return rtf_to_text(content)
    except ImportError:
        # Fallback: crude regex stripping
        content = Path(path).read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"\{[^{}]*\}", "", content)
        text = re.sub(r"\\[a-z]+\d*\s?", "", text)
        text = re.sub(r"[{}\\]", "", text)
        return text.strip()


# ── Image (OCR) ───────────────────────────────────────────────────────────────

def read_image(path: str) -> str:
    if not TESSERACT_AVAILABLE:
        return "[OCR is not available on this server.]"
    img = Image.open(path)
    return pytesseract.image_to_string(img)


# ── Router ────────────────────────────────────────────────────────────────────

READERS = {
    ".pdf":  read_pdf,
    ".docx": read_docx,
    ".doc":  read_docx,
    ".xlsx": read_excel,
    ".xls":  read_excel,
    ".csv":  read_csv,
    ".json": read_json,
    ".txt":  read_txt,
    ".rtf":  read_rtf,
    ".png":  read_image,
    ".jpg":  read_image,
    ".jpeg": read_image,
    ".tiff": read_image,
    ".bmp":  read_image,
}


def read_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    reader = READERS.get(ext)
    if not reader:
        raise ValueError(
            f"Unsupported file type: {ext}. "
            f"Supported: {', '.join(sorted(READERS.keys()))}"
        )
    return reader(path)
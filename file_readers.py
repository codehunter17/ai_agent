"""
File readers for PDF, DOCX, Excel, TXT, RTF, and Images (OCR).
"""

import io
import re
import os
from pathlib import Path
from PIL import Image

# ── Tesseract — optional ──────────────────────────────────────────────────────
try:
    import pytesseract
    if os.name == "nt":
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
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
    if not PYMUPDF_AVAILABLE or not TESSERACT_AVAILABLE:
        return ""

    text_parts = []
    try:
        doc = fitz.open(path)
        for page_num in range(min(len(doc), 20)):  # cap at 20 pages
            page = doc[page_num]
            # Render page at 3x resolution for better OCR
            mat = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            # Convert to grayscale for better OCR accuracy
            img = img.convert("L")
            page_text = pytesseract.image_to_string(img, config="--psm 6")
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
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
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


# ── DOCX ──────────────────────────────────────────────────────────────────────

def read_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


# ── Excel ─────────────────────────────────────────────────────────────────────

def read_excel(path: str) -> str:
    import pandas as pd
    ext = Path(path).suffix.lower()
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
    try:
        xl = pd.ExcelFile(path, engine=engine)
        parts = []
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            parts.append(f"=== Sheet: {sheet} ===")
            parts.append(df.to_string(index=False))
        return "\n\n".join(parts)
    except Exception as e:
        return f"[Excel read error: {e}]"


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

def read_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    readers = {
        ".pdf":  read_pdf,
        ".docx": read_docx,
        ".doc":  read_docx,
        ".xlsx": read_excel,
        ".xls":  read_excel,
        ".txt":  read_txt,
        ".rtf":  read_rtf,
        ".png":  read_image,
        ".jpg":  read_image,
        ".jpeg": read_image,
        ".tiff": read_image,
        ".bmp":  read_image,
    }
    reader = readers.get(ext)
    if not reader:
        raise ValueError(f"Unsupported file type: {ext}")
    return reader(path)
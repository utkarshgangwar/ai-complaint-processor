from pathlib import Path
from typing import Dict, Any
from pypdf import PdfReader
import docx
from src.config import CONFIG, LOGGER

class DocumentIngestionError(Exception):
    """Custom exception raised when file reading fails."""
    pass

def load_text_file(file_path: Path) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except Exception as e:
        raise DocumentIngestionError(f"Failed to read text file {file_path.name}: {str(e)}")

def load_pdf_file(file_path: Path) -> str:
    try:
        reader = PdfReader(str(file_path))
        extracted_pages = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                extracted_pages.append(text)
        return "\n".join(extracted_pages).strip()
    except Exception as e:
        raise DocumentIngestionError(f"Failed to parse PDF {file_path.name}: {str(e)}")

def load_docx_file(file_path: Path) -> str:
    try:
        doc = docx.Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except Exception as e:
        raise DocumentIngestionError(f"Failed to parse Word document {file_path.name}: {str(e)}")

def load_document(file_path: str | Path) -> Dict[str, Any]:
    """
    Ingests a document (.pdf, .docx, .txt) and returns raw text with metadata[cite: 1].
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()
    supported = CONFIG.get("processing", {}).get("supported_extensions", [".pdf", ".docx", ".txt"])

    if ext not in supported:
        raise DocumentIngestionError(f"Unsupported file extension '{ext}'. Supported: {supported}")

    LOGGER.info(f"Loading document: {path.name} ({ext})")

    if ext == ".txt":
        content = load_text_file(path)
    elif ext == ".pdf":
        content = load_pdf_file(path)
    elif ext == ".docx":
        content = load_docx_file(path)
    else:
        raise DocumentIngestionError(f"Unhandled file extension: {ext}")

    if not content:
        LOGGER.warning(f"Extracted content is empty for file: {path.name}")

    return {
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "extension": ext,
        "content": content,
        "character_count": len(content)
    }
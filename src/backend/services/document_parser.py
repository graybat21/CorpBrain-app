import os
import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("CorpBrain.DocumentParser")


class DocumentParser:
    """Parses .docx, .pdf, .txt, .md files and extracts text (ANA-CMD-02 / SRS §8)."""

    @staticmethod
    def extract_text(file_path: str, extension: str) -> str:
        ext = extension.lower().lstrip(".")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if ext in ("txt", "md"):
            return DocumentParser._extract_plain_text(file_path)
        elif ext == "docx":
            return DocumentParser._extract_docx(file_path)
        elif ext == "pdf":
            return DocumentParser._extract_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file format for deep analysis: .{ext}")

    @staticmethod
    def _extract_plain_text(file_path: str) -> str:
        for enc in ("utf-8", "cp949", "euc-kr", "utf-16", "latin-1"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @staticmethod
    def _extract_docx(file_path: str) -> str:
        try:
            import docx
            doc = docx.Document(file_path)
            full_text = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(full_text)
        except ImportError:
            logger.warning("[DocumentParser] python-docx not installed, using plain text fallback")
            return DocumentParser._extract_plain_text(file_path)
        except Exception as e:
            logger.error(f"[DocumentParser] Error parsing .docx file {file_path}: {e}")
            raise

    @staticmethod
    def _extract_pdf(file_path: str) -> str:
        # Try pdfminer.six
        try:
            from pdfminer.high_level import extract_text as pdf_extract
            return pdf_extract(file_path)
        except ImportError:
            pass

        # Try pypdf / PyPDF2
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text_pages = [page.extract_text() for page in reader.pages if page.extract_text()]
            return "\n".join(text_pages)
        except ImportError:
            pass

        # Fallback to plain text read
        return DocumentParser._extract_plain_text(file_path)


class TextChunker:
    """Splits text into chunks of target size with overlap (ANA-CMD-02)."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(
        self,
        text: str,
        file_id: str,
        *,
        workspace_id: Optional[str] = None,
        folder_1depth: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks (ANA-CMD-02).

        `workspace_id` / `folder_1depth` are keyword-only with defaults so existing
        two-positional-argument callers are unaffected. They populate the chunk metadata
        DEC-06 requires ({workspace_id, file_id, chunk_index, folder_1depth}).

        `folder_1depth` must be a bare folder NAME, not a path — derive it with
        `file_utils.derive_folder_1depth`. DEC-08 forbids an absolute path in vector metadata.
        """
        cleaned_text = re.sub(r"\s+", " ", text).strip()
        if not cleaned_text:
            return []

        chunks: List[Dict[str, Any]] = []
        start = 0
        text_len = len(cleaned_text)
        chunk_idx = 0

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_content = cleaned_text[start:end]

            chunk_id = f"{file_id}:{chunk_idx}"
            chunks.append({
                "chunk_id": chunk_id,
                "chunk_index": chunk_idx,
                "text": chunk_content,
                "char_length": len(chunk_content),
                "workspace_id": workspace_id,
                "folder_1depth": folder_1depth,
            })

            chunk_idx += 1
            if end >= text_len:
                break
            start = max(start + 1, end - self.overlap)

        return chunks

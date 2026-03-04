"""Document indexing for RAG — backend-agnostic via VectorStore."""

import asyncio
import io
import logging
import uuid
from pathlib import Path

from grug.rag.vector_store import VectorStore, get_vector_store
from grug.utils import chunk_text

logger = logging.getLogger(__name__)


# Minimum characters extracted by pypdf before we consider a PDF "text-sparse"
# and fall back to OCR.
_PDF_TEXT_MIN_CHARS = 200


def _pdf_ocr(file_path: Path) -> str:
    """OCR all pages of a PDF and return concatenated text."""
    import pytesseract
    from pdf2image import convert_from_path

    images = convert_from_path(str(file_path))
    pages = [pytesseract.image_to_string(img) for img in images]
    return "\n\n".join(pages)


def _extract_text(file_path: Path) -> str:
    """Extract plain text from a file.

    For PDFs: uses pypdf for text-layer extraction first.  If the result is
    sparse (scanned/image-only PDF), falls back to tesseract OCR via
    pdf2image + pytesseract.

    For .docx / .doc: uses python-docx to extract paragraph text.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(file_path.read_bytes()))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)

        if len(text.strip()) < _PDF_TEXT_MIN_CHARS:
            logger.info(
                "PDF %s has sparse text (%d chars) — falling back to OCR",
                file_path.name,
                len(text.strip()),
            )
            text = _pdf_ocr(file_path)

        return text

    if suffix in {".docx", ".doc"}:
        import docx

        doc = docx.Document(str(file_path))
        paragraphs = [p.text for p in doc.paragraphs]
        return "\n".join(paragraphs)

    # Plain text formats (.txt, .md, .rst, etc.)
    return file_path.read_text(encoding="utf-8", errors="replace")


class DocumentIndexer:
    """Indexes text documents into the configured vector store for a guild."""

    def __init__(self, store: VectorStore | None = None) -> None:
        self._store = store or get_vector_store()

    async def index_file(
        self,
        guild_id: int,
        file_path: Path,
        document_id: int,
        description: str | None = None,
    ) -> int:
        """Index a text file or PDF and return the number of chunks stored.

        Text extraction (and OCR for image-only PDFs) is CPU-bound; it is
        offloaded to a thread pool executor so it does not block the event loop.
        """
        text = await asyncio.to_thread(_extract_text, file_path)

        chunks = chunk_text(text)
        if not chunks:
            return 0

        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {
                "document_id": document_id,
                "filename": file_path.name,
                "description": description or "",
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            for i, _ in enumerate(chunks)
        ]
        await self._store.doc_upsert(guild_id, ids, chunks, metadatas)
        logger.info(
            "Indexed %d chunks from %s for guild %d",
            len(chunks),
            file_path.name,
            guild_id,
        )
        return len(chunks)

    async def delete_document(self, guild_id: int, document_id: int) -> None:
        """Remove all chunks belonging to a document."""
        ids = await self._store.doc_get_ids(guild_id, document_id)
        if ids:
            await self._store.doc_delete(guild_id, ids)

    async def delete_guild_collection(self, guild_id: int) -> None:
        """Remove all document chunks for an entire guild."""
        await self._store.guild_delete(guild_id)

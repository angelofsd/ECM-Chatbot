"""
Document ingestion pipeline for ECM RAG Chatbot.

Workflow:
1. Scan OCR_OUTPUT_DIR for PDF files
2. Load PDF → extract text → split into chunks
3. Generate embeddings (BGE or OpenAI)
4. Store in Qdrant (vectors) + Postgres (metadata)
5. Log progress and errors

Usage:
  python -m api.ingest_pdf              # Ingest all PDFs
  python -m api.ingest_pdf --force-reindex  # Reset and re-ingest
  python -m api.ingest_pdf --sample 5   # Process only first 5 PDFs
"""

import os
import csv
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import argparse

# Third-party imports
from tqdm import tqdm
import numpy as np
from sentence_transformers import SentenceTransformer

# Local imports
from config import (
    OCR_OUTPUT_DIR,
    INVENTORY_CSV,
    QDRANT_URL,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    LOG_LEVEL,
)
from db import db, Base, Document, Chunk, add_document, add_chunk

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# ========================
# Setup
# ========================

# Initialize Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, VectorParams, Distance
except ImportError:
    logger.error("qdrant_client not installed")
    raise

qdrant_client = QdrantClient(url=QDRANT_URL)

# Initialize embedding model
logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
embedding_model = SentenceTransformer(EMBEDDING_MODEL)
logger.info(f"Model loaded. Dimension: {EMBEDDING_DIMENSION}")


# ========================
# Data Classes
# ========================

@dataclass
class TextChunk:
    """A text chunk with metadata."""
    text: str
    sequence: int  # Order in document
    token_count: int


# ========================
# Core Functions
# ========================

def load_inventory_csv() -> dict:
    """Load inventory.csv to get document metadata."""
    inventory = {}
    if not INVENTORY_CSV.exists():
        logger.warning(f"Inventory CSV not found: {INVENTORY_CSV}")
        return inventory

    try:
        with open(INVENTORY_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                relative_path = row.get("relative_path", "")
                inventory[relative_path] = row
        logger.info(f"Loaded {len(inventory)} entries from inventory CSV")
    except Exception as e:
        logger.error(f"Failed to load inventory CSV: {e}")

    return inventory


def get_pdfs_to_ingest() -> List[Path]:
    """Get list of PDFs in OCR output directory."""
    if not OCR_OUTPUT_DIR.exists():
        logger.error(f"OCR output directory not found: {OCR_OUTPUT_DIR}")
        return []

    pdfs = list(OCR_OUTPUT_DIR.glob("**/*.pdf"))
    logger.info(f"Found {len(pdfs)} PDFs in {OCR_OUTPUT_DIR}")
    return pdfs


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[TextChunk]:
    """
    Split text into chunks with overlap.
    
    Args:
        text: Full text to chunk
        chunk_size: Target size in tokens (approximate)
        overlap: Token overlap between chunks
    
    Returns:
        List of TextChunk objects
    """
    if not text or not text.strip():
        return []

    # Simple token splitting by word
    words = text.split()
    chunks = []
    sequence = 0

    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end])

        chunks.append(TextChunk(
            text=chunk_text,
            sequence=sequence,
            token_count=end - start
        ))

        # Move to next chunk with overlap
        sequence += 1
        start = end - overlap

    logger.debug(f"Split text into {len(chunks)} chunks")
    return chunks


def embed_chunks(chunks: List[TextChunk]) -> List[Tuple[TextChunk, np.ndarray]]:
    """
    Generate embeddings for text chunks.
    
    Args:
        chunks: List of TextChunk objects
    
    Returns:
        List of (chunk, embedding) tuples
    """
    if not chunks:
        return []

    texts = [chunk.text for chunk in chunks]
    embeddings = embedding_model.encode(texts, normalize_embeddings=True)

    results = [(chunk, emb) for chunk, emb in zip(chunks, embeddings)]
    logger.debug(f"Generated {len(results)} embeddings")
    return results


def ensure_qdrant_collection():
    """Create Qdrant collection if it doesn't exist."""
    try:
        collection_info = qdrant_client.get_collection(QDRANT_COLLECTION)
        logger.info(f"Qdrant collection '{QDRANT_COLLECTION}' exists")
    except:
        logger.info(f"Creating Qdrant collection '{QDRANT_COLLECTION}'...")
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
        )
        logger.info("Collection created")


def upsert_to_qdrant(qdrant_id: str, embedding: np.ndarray, payload: dict) -> bool:
    """Upsert a vector to Qdrant."""
    try:
        point = PointStruct(
            id=hash(qdrant_id) % (2**32),  # Use hash of ID for numeric ID
            vector=embedding.tolist(),
            payload=payload,
        )
        qdrant_client.upsert(
            collection_name=QDRANT_COLLECTION,
            points=[point],
        )
        return True
    except Exception as e:
        logger.error(f"Failed to upsert to Qdrant: {e}")
        return False


def ingest_pdf(pdf_path: Path, inventory: dict) -> Tuple[bool, str]:
    """
    Ingest a single PDF: extract, chunk, embed, store.
    
    Args:
        pdf_path: Path to PDF file
        inventory: Dictionary from inventory CSV
    
    Returns:
        (success: bool, message: str)
    """
    try:
        relative_path = str(pdf_path.relative_to(OCR_OUTPUT_DIR))
        filename = pdf_path.name

        # Extract text
        logger.debug(f"Extracting text from {filename}")
        text = extract_text_from_pdf(pdf_path)
        if not text:
            return False, "No text extracted from PDF"

        # Get metadata from inventory
        inv_entry = inventory.get(relative_path, {})
        department = inv_entry.get("department_guess", "")
        acl_tags = inv_entry.get("acl_tags", "")
        size_bytes = int(inv_entry.get("size_bytes", 0))
        sha256 = inv_entry.get("sha256", "")

        # Add document to Postgres
        doc = add_document(
            filename=filename,
            source_path=str(pdf_path),
            relative_path=relative_path,
            size_bytes=size_bytes,
            sha256=sha256,
            department=department,
            acl_tags=acl_tags,
        )

        # Chunk text
        chunks = chunk_text(text)
        if not chunks:
            return False, "Text chunking produced no chunks"

        # Embed and store chunks
        embedded_chunks = embed_chunks(chunks)
        chunk_count = 0

        for chunk, embedding in embedded_chunks:
            qdrant_id = f"{doc.id}_{chunk.sequence}"
            payload = {
                "doc_id": doc.id,
                "filename": filename,
                "department": department,
                "sequence": chunk.sequence,
                "text": chunk.text,  # Store full text for LLM context
                "text_preview": chunk.text[:300],  # Also keep preview for display
            }

            if upsert_to_qdrant(qdrant_id, embedding, payload):
                # Store chunk metadata in Postgres
                db_chunk = add_chunk(
                    document_id=doc.id,
                    text=chunk.text,
                    sequence=chunk.sequence,
                    qdrant_id=qdrant_id,
                )
                chunk_count += 1

        # Update document status
        session = db.get_session()
        doc.indexed = True
        doc.chunk_count = chunk_count
        session.commit()
        session.close()

        return True, f"Ingested {chunk_count} chunks"

    except Exception as e:
        logger.error(f"Failed to ingest {pdf_path}: {e}")
        return False, str(e)


def main(force_reindex: bool = False, sample: Optional[int] = None):
    """
    Main ingestion pipeline.
    
    Args:
        force_reindex: If True, reset Qdrant and re-ingest all
        sample: If set, only process first N PDFs
    """
    # Initialize database
    logger.info("Initializing database...")
    db.init_sync()
    db.create_all_tables()

    # Initialize Qdrant
    logger.info("Ensuring Qdrant collection exists...")
    ensure_qdrant_collection()

    if force_reindex:
        logger.warning("Force reindex: clearing Qdrant collection")
        try:
            qdrant_client.delete_collection(QDRANT_COLLECTION)
            ensure_qdrant_collection()
        except:
            pass

    # Load inventory
    inventory = load_inventory_csv()

    # Get PDFs
    pdfs = get_pdfs_to_ingest()
    if sample:
        pdfs = pdfs[:sample]

    if not pdfs:
        logger.warning("No PDFs found to ingest")
        return

    # Ingest
    logger.info(f"Starting ingestion of {len(pdfs)} PDFs...")
    success_count = 0
    fail_count = 0

    with tqdm(total=len(pdfs), desc="Ingesting PDFs") as pbar:
        for pdf_path in pdfs:
            success, message = ingest_pdf(pdf_path, inventory)
            if success:
                success_count += 1
                pbar.write(f"✓ {pdf_path.name}: {message}")
            else:
                fail_count += 1
                pbar.write(f"✗ {pdf_path.name}: {message}")
            pbar.update(1)

    # Summary
    logger.info(f"\n✓ Ingestion complete:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Failures: {fail_count}")
    logger.info(f"  Total PDFs: {len(pdfs)}")
    logger.info(f"  Vector store: {QDRANT_URL}/{QDRANT_COLLECTION}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest PDFs into ECM RAG chatbot")
    parser.add_argument("--force-reindex", action="store_true", help="Reset and re-ingest all PDFs")
    parser.add_argument("--sample", type=int, default=None, help="Only process first N PDFs")
    args = parser.parse_args()

    main(force_reindex=args.force_reindex, sample=args.sample)

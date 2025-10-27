"""
Unified ingestion pipeline for multiple source types (PDFs, emails, etc.).

Workflow:
1. Scan configured source directories
2. Detect file type (PDF, email, etc.)
3. Extract content using appropriate extractor
4. Chunk → embed → store in Qdrant + Postgres
5. Track source type and department

Supports:
  - PDFs: C:\\ecm-staging\\04_text_ready
  - Emails: C:\\ecm-staging\\outlook\\*
  - Extensible for other formats
"""

import os
import logging
import gc
from pathlib import Path
from typing import List, Tuple, Optional, Generator
import argparse

from tqdm import tqdm
import numpy as np
from sentence_transformers import SentenceTransformer

# Local imports
from api.config import (
    OCR_OUTPUT_DIR,
    QDRANT_URL,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    LOG_LEVEL,
)
from api.db import db, Document, Chunk, add_document, add_chunk
from api.extractors.email_extractor import extract_email, extract_emails_from_folder

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

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


# ========================
# Source Discovery
# ========================

def discover_sources(
    pdf_dir: Optional[Path] = None,
    email_dir: Optional[Path] = None,
) -> dict:
    """
    Discover all documents across source directories.
    
    Returns:
        {
            "pdf": [(path, dept), ...],
            "email": [(path, dept), ...]
        }
    """
    sources = {
        "pdf": [],
        "email": [],
    }
    
    # PDFs
    if pdf_dir is None:
        pdf_dir = OCR_OUTPUT_DIR
    
    if pdf_dir.exists():
        pdfs = list(pdf_dir.glob("**/*.pdf"))
        for pdf_path in pdfs:
            # Guess department from path
            dept = guess_department_from_path(pdf_path)
            sources["pdf"].append((pdf_path, dept))
        logger.info(f"Found {len(pdfs)} PDFs")
    
    # Emails
    if email_dir:
        if email_dir.exists():
            emails = list(email_dir.glob("**/*.msg")) + list(email_dir.glob("**/*.eml"))
            for email_path in emails:
                # Guess department from folder name
                dept = guess_department_from_path(email_path)
                sources["email"].append((email_path, dept))
            logger.info(f"Found {len(emails)} email files")
    
    return sources


def guess_department_from_path(path: Path) -> str:
    """Guess department from file path."""
    dept_map = {
        "claims": "Claims",
        "underwriting": "Underwriting",
        "billing": "Billing",
        "legal": "Legal",
        "subrogation": "Subrogation",
        "it": "IT",
    }
    
    path_lower = str(path).lower()
    for key, dept in dept_map.items():
        if key in path_lower:
            return dept
    
    return "General"


# ========================
# Content Extraction
# ========================

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        logger.error(f"Failed to extract from {pdf_path}: {e}")
        return ""


def extract_content(file_path: Path, source_type: str) -> Optional[dict]:
    """
    Extract content from any supported file type.
    
    Returns: {"text": str, "title": str, "source_type": str, "metadata": dict}
    """
    if source_type == "pdf":
        text = extract_pdf_text(file_path)
        if not text:
            return None
        return {
            "text": text,
            "title": file_path.stem,
            "source_type": "pdf",
            "metadata": {"filename": file_path.name},
        }
    
    elif source_type == "email":
        return extract_email(file_path)
    
    else:
        logger.warning(f"Unknown source type: {source_type}")
        return None


# ========================
# Ingestion
# ========================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into chunks with overlap."""
    if not text or not text.strip():
        return []
    
    words = text.split()
    chunks = []
    sequence = 0
    
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_text = " ".join(words[start:end])
        chunks.append({
            "text": chunk_text,
            "sequence": sequence,
            "token_count": end - start,
        })
        sequence += 1
        start = end - overlap
    
    return chunks


def embed_chunks(chunks: list) -> list:
    """Generate embeddings for chunks."""
    if not chunks:
        return []
    
    texts = [c["text"] for c in chunks]
    embeddings = embedding_model.encode(texts, normalize_embeddings=True)
    
    return [(c, emb) for c, emb in zip(chunks, embeddings)]


def upsert_to_qdrant(qdrant_id: str, embedding: np.ndarray, payload: dict) -> bool:
    """Upsert vector to Qdrant."""
    try:
        point = PointStruct(
            id=hash(qdrant_id) % (2**32),
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


def ingest_document(file_path: Path, source_type: str, department: str) -> Tuple[bool, str]:
    """
    Ingest a single document.
    
    Returns: (success, message)
    """
    try:
        # Extract content
        content = extract_content(file_path, source_type)
        if not content:
            return False, "No content extracted"
        
        text = content["text"]
        title = content["title"]
        metadata = content.get("metadata", {})
        
        # Add to database
        doc = add_document(
            filename=file_path.name,
            source_path=str(file_path),
            relative_path=str(file_path.relative_to(file_path.parent.parent)),
            size_bytes=file_path.stat().st_size,
            sha256="",  # Could compute if needed
            department=department,
            acl_tags=department,
        )
        doc.source_type = source_type
        
        session = db.get_session()
        session.merge(doc)
        session.commit()
        session.close()
        
        # Chunk and embed
        chunks = chunk_text(text)
        if not chunks:
            return False, "No chunks generated"
        
        embedded = embed_chunks(chunks)
        chunk_count = 0
        
        for chunk, embedding in embedded:
            qdrant_id = f"{doc.id}_{chunk['sequence']}"
            payload = {
                "doc_id": doc.id,
                "filename": file_path.name,
                "source_type": source_type,
                "department": department,
                "sequence": chunk["sequence"],
                "text_preview": chunk["text"][:200],
            }
            
            if upsert_to_qdrant(qdrant_id, embedding, payload):
                add_chunk(
                    document_id=doc.id,
                    text=chunk["text"],
                    sequence=chunk["sequence"],
                    qdrant_id=qdrant_id,
                )
                chunk_count += 1
        
        # Update status
        session = db.get_session()
        doc = session.query(Document).filter_by(id=doc.id).first()
        doc.indexed = True
        doc.chunk_count = chunk_count
        session.commit()
        session.close()
        
        return True, f"Ingested {chunk_count} chunks ({source_type})"
    
    except Exception as e:
        logger.error(f"Failed to ingest {file_path}: {e}")
        return False, str(e)


# ========================
# Main Pipeline
# ========================

def main(pdf_dir: Optional[Path] = None, email_dir: Optional[Path] = None, sample: Optional[int] = None, batch_size: int = 50):
    """Main ingestion pipeline for all source types.
    
    Args:
        pdf_dir: Path to PDF directory
        email_dir: Path to email directory
        sample: Limit processing to first N documents
        batch_size: For emails, process in batches with gc.collect() between batches (default 50)
    """
    
    logger.info("Initializing database...")
    db.init_sync()
    db.create_all_tables()
    
    logger.info("Ensuring Qdrant collection...")
    try:
        qdrant_client.get_collection(QDRANT_COLLECTION)
    except:
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
        )
    
    # Discover sources
    sources = discover_sources(pdf_dir, email_dir)
    
    # Combine all sources
    all_docs = []
    for source_type, docs in sources.items():
        all_docs.extend([(path, dept, source_type) for path, dept in docs])
    
    if sample:
        all_docs = all_docs[:sample]
    
    if not all_docs:
        logger.warning("No documents found")
        return
    
    # Ingest
    logger.info(f"Ingesting {len(all_docs)} documents...")
    success = 0
    failed = 0
    
    # Separate PDFs and emails for batch processing
    pdf_docs = [(p, d, s) for p, d, s in all_docs if s == "pdf"]
    email_docs = [(p, d, s) for p, d, s in all_docs if s == "email"]
    
    # Process PDFs first (no batching needed)
    if pdf_docs:
        logger.info(f"\n📄 Processing {len(pdf_docs)} PDFs...")
        with tqdm(total=len(pdf_docs), desc="PDFs", position=0) as pbar:
            for file_path, department, source_type in pdf_docs:
                ok, msg = ingest_document(file_path, source_type, department)
                if ok:
                    success += 1
                    pbar.write(f"✓ {file_path.name}")
                else:
                    failed += 1
                    pbar.write(f"✗ {file_path.name}: {msg}")
                pbar.update(1)
    
    # Process emails in batches with memory management
    if email_docs:
        logger.info(f"\n📧 Processing {len(email_docs)} emails (batch_size={batch_size})...")
        
        for batch_start in range(0, len(email_docs), batch_size):
            batch_end = min(batch_start + batch_size, len(email_docs))
            batch_num = batch_start // batch_size + 1
            total_batches = (len(email_docs) + batch_size - 1) // batch_size
            
            logger.info(f"\nBatch {batch_num}/{total_batches} ({batch_start + 1}-{batch_end} of {len(email_docs)})")
            
            with tqdm(total=batch_end - batch_start, desc=f"Batch {batch_num}", position=0) as pbar:
                for i, (file_path, department, source_type) in enumerate(email_docs[batch_start:batch_end]):
                    ok, msg = ingest_document(file_path, source_type, department)
                    if ok:
                        success += 1
                        pbar.write(f"✓ {file_path.name}")
                    else:
                        failed += 1
                        pbar.write(f"✗ {file_path.name}: {msg}")
                    pbar.update(1)
            
            # Force garbage collection between batches
            logger.debug(f"Cleaning up memory after batch {batch_num}...")
            gc.collect()
    
    logger.info(f"\n✓ Complete: {success} success, {failed} failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents (PDFs, emails, etc.)")
    parser.add_argument("--pdf-dir", type=Path, default=OCR_OUTPUT_DIR, help="PDF directory")
    parser.add_argument("--email-dir", type=Path, help="Email directory")
    parser.add_argument("--sample", type=int, help="Process only first N files")
    parser.add_argument("--batch-size", type=int, default=50, help="Email batch size for memory management (default 50)")
    args = parser.parse_args()
    
    main(pdf_dir=args.pdf_dir, email_dir=args.email_dir, sample=args.sample, batch_size=args.batch_size)

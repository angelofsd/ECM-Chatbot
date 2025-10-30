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

# CRITICAL: Disable Git monitoring BEFORE any other imports
# Git for Windows can consume 90%+ memory when monitoring file changes
import os
import subprocess
import sys

def kill_git_processes():
    """Kill Git processes that consume excessive memory during file operations."""
    if sys.platform == "win32":
        try:
            # Kill git.exe
            subprocess.run(
                ["taskkill", "/F", "/IM", "git.exe", "/T"],
                capture_output=True,
                timeout=5
            )
            # Kill git-credential-manager
            subprocess.run(
                ["taskkill", "/F", "/IM", "git-credential-manager.exe", "/T"],
                capture_output=True,
                timeout=5
            )
            print("✓ Git processes stopped (prevents memory spike)")
        except Exception:
            pass  # Ignore errors if processes don't exist

# Kill Git processes immediately
kill_git_processes()

import logging
import gc
from pathlib import Path
from typing import List, Tuple, Optional, Generator
import argparse

from tqdm import tqdm
import numpy as np

# Local imports
from api.config import (
    OCR_OUTPUT_DIR,
    QDRANT_URL,
    QDRANT_COLLECTION,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CHUNK_LIMIT,
    EMBEDDING_MINI_BATCH_SIZE,
    EMBEDDING_API_BATCH_SIZE,
    LOG_LEVEL,
    USE_OPENAI_EMBEDDINGS,
)
from api.db import db, Document, Chunk, add_document, add_chunk
from api.extractors.email_extractor import extract_email, extract_emails_from_folder
from api.embeddings import get_embedding_generator

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

# Initialize embedding generator (lazy-loaded, no memory spike)
embedding_generator = None


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
    """Extract text from PDF with proper file handle management."""
    text = ""
    try:
        from pypdf import PdfReader
        
        # Open file with explicit context manager
        with open(str(pdf_path), 'rb') as f:
            reader = PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() or ""
        
        # File handle automatically closed by context manager
        # Force cleanup of reader object
        del reader
        gc.collect()
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"Failed to extract from {pdf_path}: {e}")
        return ""
    finally:
        # Extra safety - ensure text is returned and references are dropped
        gc.collect()


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
    """
    Split text into chunks with overlap - MEMORY OPTIMIZED.
    
    Processes text in smaller segments to avoid holding entire word list in memory.
    """
    if not text or not text.strip():
        return []
    
    # Don't split into words all at once - too memory intensive for large docs
    # Instead, chunk by character count (approximate)
    chunks = []
    sequence = 0
    
    # Approximate: 5 chars per word on average
    char_chunk_size = chunk_size * 5
    char_overlap = overlap * 5
    
    text_len = len(text)
    start = 0
    prev_start = -1
    
    while start < text_len:
        end = min(start + char_chunk_size, text_len)
        
        # Safety: if pointer stops progressing, force jump forward
        if start <= prev_start:
            start = prev_start + char_chunk_size
            end = min(start + char_chunk_size, text_len)
        prev_start = start
        
        # Find word boundary (don't cut mid-word)
        if end < text_len:
            # Look for space after end position
            while end < text_len and text[end] not in (' ', '\n', '\t', '.', ','):
                end += 1
        
        chunk_text = text[start:end].strip()
        
        if chunk_text:  # Only add non-empty chunks
            chunks.append({
                "text": chunk_text,
                "sequence": sequence,
                "token_count": len(chunk_text.split()),  # Approximate
            })
            sequence += 1
            start = max(0, end - char_overlap)
        else:
            # Advance pointer when slice collapses to whitespace to avoid infinite loop
            start = end if end > start else start + char_chunk_size
        
        # Limit total chunks to prevent memory explosion and excessive API calls
        if CHUNK_LIMIT and sequence >= CHUNK_LIMIT:
            logger.warning(f"Document too large, truncating at {sequence} chunks (limit={CHUNK_LIMIT})")
            break
    
    return chunks


def embed_chunks(chunks: list) -> list:
    """Generate embeddings for chunks."""
    global embedding_generator
    
    if not chunks:
        return []
    
    # Lazy-load embedding generator to avoid memory spike at import time
    if embedding_generator is None:
        logger.info(f"Initializing embedding generator: {EMBEDDING_MODEL}")
        logger.info(f"Mode: {'OpenAI API' if USE_OPENAI_EMBEDDINGS else 'Local model'}")
        embedding_generator = get_embedding_generator()
    
    texts = [c["text"] for c in chunks]
    embeddings = embedding_generator.embed(texts, batch_size=max(1, EMBEDDING_API_BATCH_SIZE))
    
    result = [(c, emb) for c, emb in zip(chunks, embeddings)]
    
    # Cleanup after embedding
    del texts, embeddings
    gc.collect()
    
    return result


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
        
        # Add to database - returns doc_id now (no detached instance issue)
        doc_id = add_document(
            filename=file_path.name,
            source_path=str(file_path),
            relative_path=str(file_path.relative_to(file_path.parent.parent)),
            size_bytes=file_path.stat().st_size,
            sha256="",  # Could compute if needed
            department=department,
            acl_tags=department,
            source_type=source_type,
        )
        
        logger.info(f"Document added with ID: {doc_id}")
        
        # Chunk and embed IN BATCHES to avoid memory spike
        all_chunks = chunk_text(text)
        if not all_chunks:
            return False, "No chunks generated"
        
        # Delete the full text immediately after chunking
        del text
        gc.collect()
        
        logger.info(f"Generated {len(all_chunks)} chunks, processing in mini-batches...")
        
        # Process chunks in configurable mini-batches to balance speed vs memory
        chunk_count = 0
        MINI_BATCH_SIZE = max(1, EMBEDDING_MINI_BATCH_SIZE)
        
        for batch_start in range(0, len(all_chunks), MINI_BATCH_SIZE):
            batch_end = min(batch_start + MINI_BATCH_SIZE, len(all_chunks))
            chunk_batch = all_chunks[batch_start:batch_end]
            
            logger.info(f"  Embedding chunks {batch_start}-{batch_end} of {len(all_chunks)} (batch={MINI_BATCH_SIZE})...")
            
            # Embed this mini-batch
            embedded = embed_chunks(chunk_batch)
            
            # Store to Qdrant and DB using doc_id instead of doc.id
            for chunk, embedding in embedded:
                qdrant_id = f"{doc_id}_{chunk['sequence']}"
                payload = {
                    "doc_id": doc_id,
                    "filename": file_path.name,
                    "source_type": source_type,
                    "department": department,
                    "sequence": chunk["sequence"],
                    "text": chunk["text"],  # Store full text for LLM context
                    "text_preview": chunk["text"][:300],  # Also keep preview for display
                }
                
                if upsert_to_qdrant(qdrant_id, embedding, payload):
                    add_chunk(
                        document_id=doc_id,
                        text=chunk["text"],
                        sequence=chunk["sequence"],
                        qdrant_id=qdrant_id,
                    )
                    chunk_count += 1
            
            # Cleanup after each mini-batch
            del chunk_batch, embedded
            gc.collect()
        
        # Update status with proper session management
        session = db.get_session()
        try:
            doc = session.query(Document).filter_by(id=doc_id).first()
            doc.indexed = True
            doc.chunk_count = chunk_count
            session.commit()
        finally:
            session.close()
            del session  # Drop reference
        
        # Aggressive memory cleanup after each document
        del content, all_chunks, doc
        gc.collect()
        
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
    
    # Process PDFs first (with memory cleanup every 10 docs)
    if pdf_docs:
        logger.info(f"\n[PDF] Processing {len(pdf_docs)} PDFs...")
        with tqdm(total=len(pdf_docs), desc="PDFs", position=0) as pbar:
            for idx, (file_path, department, source_type) in enumerate(pdf_docs):
                ok, msg = ingest_document(file_path, source_type, department)
                if ok:
                    success += 1
                    pbar.write(f"OK {file_path.name}")
                else:
                    failed += 1
                    pbar.write(f"FAIL {file_path.name}: {msg}")
                pbar.update(1)
                
                # Aggressive memory cleanup every 5 documents
                if (idx + 1) % 5 == 0:
                    gc.collect()
                    pbar.write(f"  [Memory cleanup at {idx + 1}/{len(pdf_docs)}]")
                
                # SUPER aggressive - force cleanup after EVERY document
                if (idx + 1) % 1 == 0:
                    gc.collect()
    
    # Process emails in batches with memory management
    if email_docs:
        logger.info(f"\n[EMAIL] Processing {len(email_docs)} emails (batch_size={batch_size})...")
        
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
                        pbar.write(f"OK {file_path.name}")
                    else:
                        failed += 1
                        pbar.write(f"FAIL {file_path.name}: {msg}")
                    pbar.update(1)
            
            # Force garbage collection between batches
            logger.debug(f"Cleaning up memory after batch {batch_num}...")
            gc.collect()
    
    logger.info(f"\nCOMPLETE: {success} success, {failed} failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents (PDFs, emails, etc.)")
    parser.add_argument("--pdf-dir", type=Path, default=OCR_OUTPUT_DIR, help="PDF directory")
    parser.add_argument("--email-dir", type=Path, help="Email directory")
    parser.add_argument("--sample", type=int, help="Process only first N files")
    parser.add_argument("--batch-size", type=int, default=50, help="Email batch size for memory management (default 50)")
    args = parser.parse_args()
    
    main(pdf_dir=args.pdf_dir, email_dir=args.email_dir, sample=args.sample, batch_size=args.batch_size)

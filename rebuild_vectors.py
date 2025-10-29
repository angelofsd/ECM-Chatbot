#!/usr/bin/env python3
"""
Rebuild Qdrant vectors from existing database chunks.
Useful after clearing Qdrant but keeping Postgres data intact.
"""
import os
from dotenv import load_dotenv

# Load .env FIRST, BEFORE reading any env vars (override system environment)
load_dotenv(override=True)

os.environ["USE_OPENAI_EMBEDDINGS"] = "true"

from api.db import db, Document, Chunk
from api.embeddings import get_embedding_generator
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def rebuild_vectors_bulk():
    """Bulk upload vectors for all chunks in database."""
    db.init_sync()
    session = db.get_session()
    
    try:
        # Get all chunks with their document metadata
        query = session.query(
            Chunk.id,
            Chunk.text,
            Chunk.sequence,
            Chunk.document_id,
            Document.source_path,
            Document.source_type,
            Document.department
        ).join(Document, Chunk.document_id == Document.id)
        
        chunks = query.all()
        logger.info(f"Found {len(chunks)} chunks to re-embed and upload")
        
        if len(chunks) == 0:
            logger.warning("No chunks found in database!")
            return
        
        # Initialize embedding generator and Qdrant
        embed_gen = get_embedding_generator()
        qdrant = QdrantClient("http://localhost:6333")
        
        # Ensure collection exists
        from qdrant_client.models import VectorParams, Distance
        EMBEDDING_DIMENSION = 1536  # text-embedding-3-small
        QDRANT_COLLECTION = "ecm_docs"
        try:
            qdrant.get_collection(QDRANT_COLLECTION)
        except:
            logger.info(f"Creating collection {QDRANT_COLLECTION}...")
            qdrant.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
            )
        
        # Batch processing (100 chunks at a time)
        BATCH_SIZE = 100
        total_uploaded = 0
        
        for batch_start in tqdm(range(0, len(chunks), BATCH_SIZE), desc="Uploading batches"):
            batch_end = min(batch_start + BATCH_SIZE, len(chunks))
            batch = chunks[batch_start:batch_end]
            
            # Extract texts for embedding
            texts = [chunk.text for chunk in batch]
            
            # Get embeddings
            embeddings = embed_gen.embed(texts, batch_size=100)
            
            # Prepare points for Qdrant
            points = []
            for i, chunk in enumerate(batch):
                qdrant_id_str = f"{chunk.document_id}_{chunk.sequence}"
                qdrant_id_int = hash(qdrant_id_str) % (2**32)  # Convert to integer for Qdrant
                filename = os.path.basename(chunk.source_path)
                
                point = PointStruct(
                    id=qdrant_id_int,
                    vector=embeddings[i],
                    payload={
                        "doc_id": chunk.document_id,
                        "filename": filename,
                        "source_type": chunk.source_type,
                        "department": chunk.department,
                        "sequence": chunk.sequence,
                        "text_preview": chunk.text[:200],
                    }
                )
                points.append(point)
            
            # Bulk upsert to Qdrant
            qdrant.upsert(collection_name="ecm_docs", points=points)
            total_uploaded += len(points)
        
        logger.info(f"✓ Successfully uploaded {total_uploaded} vectors to Qdrant")
        
        # Verify
        collection_info = qdrant.get_collection("ecm_docs")
        logger.info(f"Qdrant now has {collection_info.points_count} vectors")
        
    finally:
        session.close()

if __name__ == "__main__":
    rebuild_vectors_bulk()

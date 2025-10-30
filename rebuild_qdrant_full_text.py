#!/usr/bin/env python3
"""
Rebuild Qdrant collection with full text in payloads.
This reads from existing Qdrant, extracts the text from chunks,
and re-uploads with full text instead of truncated preview.
"""

import os
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv
from tqdm import tqdm
from openai import OpenAI

# Load env
load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ecm_docs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Check if SQLite DB exists with chunk text
SQLITE_DB = Path("ecm_rag.db")

def get_chunk_texts_from_sqlite() -> Dict[str, str]:
    """Load chunk texts from SQLite database."""
    try:
        import sqlite3
        if not SQLITE_DB.exists():
            print("⚠️  SQLite DB not found, will use Qdrant preview only")
            return {}
        
        conn = sqlite3.connect(str(SQLITE_DB))
        cursor = conn.cursor()
        
        # Fetch all chunks: (qdrant_id, text)
        cursor.execute("SELECT qdrant_id, text FROM chunks")
        chunks = dict(cursor.fetchall())
        conn.close()
        
        print(f"✓ Loaded {len(chunks)} chunk texts from SQLite")
        return chunks
    except Exception as e:
        print(f"⚠️  Could not load from SQLite: {e}")
        return {}


def get_all_vectors(limit: int = 10000) -> List[Dict[str, Any]]:
    """Fetch all vectors from Qdrant."""
    try:
        url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points"
        response = requests.get(f"{url}?limit={limit}", timeout=30)
        response.raise_for_status()
        
        data = response.json()
        points = data.get('result', {}).get('points', [])
        print(f"✓ Fetched {len(points)} points from Qdrant")
        return points
    except Exception as e:
        print(f"✗ Error fetching vectors: {e}")
        return []


def embed_text(text: str, client: OpenAI) -> List[float]:
    """Create embedding for text."""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"✗ Embedding error: {e}")
        return None


def update_point(point_id: str, payload: Dict, embedding: List[float]) -> bool:
    """Update a point in Qdrant with new payload and embedding."""
    try:
        url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points"
        
        # Use upsert to update
        data = {
            "points": [
                {
                    "id": point_id,
                    "vector": embedding,
                    "payload": payload
                }
            ]
        }
        
        response = requests.put(f"{url}", json=data, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"✗ Update error for {point_id}: {e}")
        return False


def main():
    print("=" * 60)
    print("Rebuilding Qdrant with full text payloads")
    print("=" * 60)
    
    # Load chunk texts from SQLite
    chunk_texts = get_chunk_texts_from_sqlite()
    
    # Get all points from Qdrant
    points = get_all_vectors()
    if not points:
        print("✗ No points found in Qdrant")
        return
    
    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Process each point
    updated = 0
    failed = 0
    
    print(f"\nUpdating {len(points)} points with full text...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {}
        
        for point in points:
            point_id = point['id']
            vector = point['vector']
            old_payload = point.get('payload', {})
            
            # Get full text
            full_text = chunk_texts.get(str(point_id), '')
            if not full_text:
                # Fall back to truncated preview from payload
                full_text = old_payload.get('text_preview', '')
            
            # Create new payload with full text
            new_payload = {
                **old_payload,
                'text': full_text,  # Add full text
                'text_preview': full_text[:300]  # Update preview to 300 chars
            }
            
            # Submit embedding task
            future = executor.submit(
                update_with_embedding,
                point_id, new_payload, full_text, client
            )
            futures[future] = point_id
        
        # Process results
        for future in tqdm(as_completed(futures), total=len(futures)):
            if future.result():
                updated += 1
            else:
                failed += 1
    
    print(f"\n✓ Updated: {updated}")
    print(f"✗ Failed: {failed}")
    print("\nDone! Qdrant now has full text in payloads.")


def update_with_embedding(point_id: str, payload: Dict, text: str, client: OpenAI) -> bool:
    """Helper to embed text and update point."""
    embedding = embed_text(text, client)
    if not embedding:
        return False
    return update_point(point_id, payload, embedding)


if __name__ == "__main__":
    main()

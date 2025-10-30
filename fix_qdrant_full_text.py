#!/usr/bin/env python3
"""
Fix Qdrant payloads to include full text from source documents.
Since we can't re-ingest (SQLAlchemy issues), we'll read from OCR output 
and directly update Qdrant vectors with full chunk text.
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ecm_docs")

# Try to use config path
try:
    from api.config import OCR_OUTPUT_DIR
except:
    OCR_OUTPUT_DIR = Path(r"C:\ecm-staging\04_text_ready")

def read_document_text(file_path: Path) -> str:
    """Read full text from OCR'd PDF or text file."""
    try:
        if file_path.suffix == '.pdf':
            # Try .pdf.txt first (OCR output)
            txt_path = Path(str(file_path) + '.txt')
            if txt_path.exists():
                return txt_path.read_text(encoding='utf-8', errors='ignore')
        return file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 300, chunk_overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - chunk_overlap
    return chunks

def get_all_qdrant_points() -> list:
    """Fetch all points from Qdrant."""
    try:
        url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?limit=100000"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('result', {}).get('points', [])
    except Exception as e:
        print(f"Error fetching points: {e}")
        return []

def build_document_chunks_map() -> dict:
    """Build a map of (filename, sequence) -> chunk_text."""
    print("Building document chunks map from OCR output...")
    chunks_map = defaultdict(dict)
    
    if not OCR_OUTPUT_DIR.exists():
        print(f"Warning: OCR dir not found: {OCR_OUTPUT_DIR}")
        return chunks_map
    
    # Read all documents
    for file_path in tqdm(list(OCR_OUTPUT_DIR.glob("*.pdf.txt")) + list(OCR_OUTPUT_DIR.glob("*.txt"))):
        filename = file_path.stem.replace('.pdf', '')  # Remove .pdf from name
        text = read_document_text(file_path)
        
        if not text:
            continue
        
        # Chunk the text
        chunks = chunk_text(text)
        for seq, chunk_text_content in enumerate(chunks):
            chunks_map[filename][seq] = chunk_text_content
    
    print(f"Built map with {len(chunks_map)} documents")
    return chunks_map

def update_qdrant_point(point_id: str, payload: dict, vector: list) -> bool:
    """Update a point in Qdrant."""
    try:
        url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points"
        data = {
            "points": [
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": payload
                }
            ]
        }
        response = requests.put(url, json=data, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error updating point {point_id}: {e}")
        return False

def main():
    print("=" * 60)
    print("Fixing Qdrant payloads with full text")
    print("=" * 60)
    
    # Build chunk map
    chunks_map = build_document_chunks_map()
    
    if not chunks_map:
        print("✗ No documents found in OCR output")
        return
    
    # Get all points from Qdrant
    points = get_all_qdrant_points()
    print(f"✓ Fetched {len(points)} points from Qdrant\n")
    
    if not points:
        print("✗ No points in Qdrant")
        return
    
    # Update each point
    updated = 0
    skipped = 0
    
    print(f"Updating {len(points)} points...")
    
    for point in tqdm(points):
        point_id = point['id']
        vector = point['vector']
        payload = point.get('payload', {})
        
        filename = payload.get('filename', '')
        sequence = payload.get('sequence', 0)
        
        # Remove .pdf extension for lookup
        lookup_filename = filename.replace('.pdf', '')
        
        # Get full chunk text
        if lookup_filename in chunks_map and sequence in chunks_map[lookup_filename]:
            full_text = chunks_map[lookup_filename][sequence]
            
            # Update payload with full text
            new_payload = {
                **payload,
                'text': full_text,
                'text_preview': full_text[:300]
            }
            
            if update_qdrant_point(str(point_id), new_payload, vector):
                updated += 1
            else:
                skipped += 1
        else:
            skipped += 1
    
    print(f"\n✓ Updated: {updated}")
    print(f"⊘ Skipped: {skipped}")
    print("\nDone! Qdrant now has full text in payloads.")

if __name__ == "__main__":
    main()

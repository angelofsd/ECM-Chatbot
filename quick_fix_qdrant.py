#!/usr/bin/env python3
"""
Quick fix: Update Qdrant payloads to use larger text_preview (500+ chars instead of 200).
This won't give us full document text, but will give the LLM more context.
"""

import os
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "ecm_docs")

def get_all_points(limit=100000):
    try:
        url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points?limit={limit}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json().get('result', {}).get('points', [])
    except Exception as e:
        print(f"Error: {e}")
        return []

def update_point(point_id, vector, payload):
    try:
        url = f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points"
        data = {"points": [{"id": point_id, "vector": vector, "payload": payload}]}
        response = requests.put(url, json=data, timeout=30)
        return response.status_code == 200
    except:
        return False

print("Getting all points from Qdrant...")
points = get_all_points()
print(f"Found {len(points)} points")

if not points:
    print("No points to update")
    exit(1)

updated = 0
print("\nUpdating payloads with expanded text preview...")

for point in tqdm(points):
    point_id = point['id']
    vector = point['vector']
    payload = point.get('payload', {})
    
    # Update text_preview to use more chars if available
    if 'text' in payload:
        payload['text_preview'] = payload['text'][:800]
    elif 'text_preview' in payload and len(payload['text_preview']) < 500:
        # This won't help much, but at least it's consistent
        pass
    
    if update_point(point_id, vector, payload):
        updated += 1

print(f"\nUpdated {updated}/{len(points)} points")
print("Done!")

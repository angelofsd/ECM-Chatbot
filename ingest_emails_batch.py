"""
Batch email ingestion with memory management.

Processes emails in controlled batches, with explicit garbage collection
between batches to prevent memory creep even with large files.

Usage:
  python ingest_emails_batch.py --email-dir "C:\ecm-staging\Outlook" --batch-size 50
"""

import gc
import sys
from pathlib import Path
from typing import List, Optional
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from api.extractors.email_extractor import extract_email


def ingest_email_batch(
    email_files: List[Path],
    batch_size: int = 50,
    verbose: bool = True,
) -> dict:
    """
    Ingest emails in batches with memory management.
    
    Args:
        email_files: List of email file paths to process
        batch_size: Number of emails per batch (default 50)
        verbose: Print progress
    
    Returns:
        {"total": int, "success": int, "failed": int, "stats": dict}
    """
    stats = {
        "total": len(email_files),
        "success": 0,
        "failed": 0,
        "total_chars": 0,
        "total_chunks": 0,
        "by_sender": {},
    }
    
    num_batches = (len(email_files) + batch_size - 1) // batch_size
    
    for batch_num in range(num_batches):
        start_idx = batch_num * batch_size
        end_idx = min((batch_num + 1) * batch_size, len(email_files))
        batch = email_files[start_idx:end_idx]
        
        print(f"\n{'='*70}")
        print(f"BATCH {batch_num + 1}/{num_batches} ({start_idx+1}-{end_idx} of {len(email_files)})")
        print(f"{'='*70}")
        
        batch_success = 0
        batch_failed = 0
        
        for i, email_file in enumerate(batch, 1):
            try:
                result = extract_email(email_file)
                
                if result:
                    batch_success += 1
                    stats["success"] += 1
                    
                    # Update stats
                    text = result.get("text", "")
                    stats["total_chars"] += len(text)
                    
                    # Count chunks (simple: ~300 tokens per chunk)
                    chunks = len(text.split()) // 300 + 1
                    stats["total_chunks"] += chunks
                    
                    # Track by sender
                    sender = result.get("metadata", {}).get("from", "unknown")[:40]
                    if sender not in stats["by_sender"]:
                        stats["by_sender"][sender] = {"count": 0, "chars": 0}
                    stats["by_sender"][sender]["count"] += 1
                    stats["by_sender"][sender]["chars"] += len(text)
                    
                    if verbose and i % 10 == 0:
                        print(f"  ✓ {i}/{len(batch)}: {email_file.name[:50]}")
                else:
                    batch_failed += 1
                    stats["failed"] += 1
                    if verbose:
                        print(f"  ✗ {i}/{len(batch)}: {email_file.name[:50]} - extraction returned None")
            
            except Exception as e:
                batch_failed += 1
                stats["failed"] += 1
                if verbose:
                    print(f"  ✗ {i}/{len(batch)}: {email_file.name[:50]} - {str(e)[:50]}")
        
        print(f"\nBatch {batch_num + 1} complete: {batch_success} success, {batch_failed} failed")
        print(f"Total so far: {stats['success']} success, {stats['failed']} failed")
        
        # Force garbage collection between batches
        print("Cleaning up memory...")
        gc.collect()
        
        print(f"Batch {batch_num + 1} memory cleanup done.\n")
    
    return stats


def print_summary(stats: dict):
    """Print ingestion summary."""
    print("\n" + "="*70)
    print("INGESTION COMPLETE")
    print("="*70)
    print(f"Total emails:       {stats['total']}")
    print(f"Successful:         {stats['success']}")
    print(f"Failed:             {stats['failed']}")
    print(f"Success rate:       {(stats['success']/stats['total']*100):.1f}%")
    print(f"Total text:         {stats['total_chars']:,} characters")
    print(f"Estimated chunks:   {stats['total_chunks']:,}")
    
    print("\n" + "-"*70)
    print("TOP SENDERS")
    print("-"*70)
    
    for sender, data in sorted(
        stats["by_sender"].items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:10]:
        pct = (data["count"] / stats["success"]) * 100
        print(f"{data['count']:3} emails ({pct:5.1f}%) | {sender}")


def main():
    parser = argparse.ArgumentParser(description="Batch email ingestion with memory management")
    parser.add_argument("--email-dir", type=Path, required=True, help="Email directory")
    parser.add_argument("--batch-size", type=int, default=50, help="Emails per batch (default 50)")
    parser.add_argument("--sample", type=int, help="Only process first N files")
    args = parser.parse_args()
    
    # Find email files
    email_dir = Path(args.email_dir)
    if not email_dir.exists():
        logger.error(f"Email directory not found: {email_dir}")
        sys.exit(1)
    
    email_files = list(email_dir.glob("*.msg")) + list(email_dir.glob("*.eml"))
    logger.info(f"Found {len(email_files)} email files")
    
    if args.sample:
        email_files = email_files[:args.sample]
        logger.info(f"Processing sample: {len(email_files)} files")
    
    # Process batches
    stats = ingest_email_batch(
        email_files,
        batch_size=args.batch_size,
        verbose=True,
    )
    
    # Print summary
    print_summary(stats)


if __name__ == "__main__":
    main()

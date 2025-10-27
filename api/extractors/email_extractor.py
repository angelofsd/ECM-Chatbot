"""
Email extraction module for Outlook .msg and .eml files.

Uses command-line tools (msg-extractor) for memory efficiency with large attachments.
Falls back to Python libraries for standard .eml files.

Workflow:
  1. Use msg-extractor CLI for .msg files (memory efficient)
  2. Use email module for .eml files
  3. Extract only text, skip attachments
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# ========================
# Email Extraction
# ========================

def extract_from_msg(file_path: Path) -> Optional[Dict]:
    """
    Extract text from Outlook .msg file using msg-extractor CLI (memory efficient).
    
    Falls back to Python library if CLI not available.
    
    Args:
        file_path: Path to .msg file
    
    Returns:
        Standardized dict with text, title, source_type, metadata
        Returns None if extraction fails
    """
    # Try CLI first (most memory efficient)
    try:
        result = subprocess.run(
            ["msg-extractor", str(file_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse extracted text
            lines = result.stdout.split("\n")
            subject = ""
            from_addr = ""
            to_addr = ""
            cc_addr = ""
            date_str = ""
            body_start = 0
            
            # Parse headers
            for i, line in enumerate(lines):
                if line.startswith("Subject:"):
                    subject = line[8:].strip()
                elif line.startswith("From:"):
                    from_addr = line[5:].strip()
                elif line.startswith("To:"):
                    to_addr = line[3:].strip()
                elif line.startswith("Cc:"):
                    cc_addr = line[3:].strip()
                elif line.startswith("Date:"):
                    date_str = line[5:].strip()
                elif line.strip() == "":
                    body_start = i + 1
                    break
            
            body = "\n".join(lines[body_start:])[:50000]  # Limit to 50KB
            
            return {
                "text": f"Subject: {subject}\nFrom: {from_addr}\nTo: {to_addr}\nCc: {cc_addr}\nDate: {date_str}\n\n{body}",
                "title": f"Email: {subject}",
                "source_type": "email",
                "metadata": {
                    "subject": subject,
                    "from": from_addr,
                    "to": to_addr,
                    "cc": cc_addr,
                    "date": date_str,
                    "filename": file_path.name,
                }
            }
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"CLI extraction failed, trying Python library: {e}")
    
    # Fallback to Python library
    try:
        import extract_msg
    except ImportError:
        logger.error("extract-msg library not installed and msg-extractor CLI not found")
        return None

    try:
        # Extract message (don't load attachments to save memory)
        msg = extract_msg.Message(str(file_path))
        
        # Extract fields
        subject = msg.subject or "(no subject)"
        from_addr = msg.sender or "unknown"
        to_addr = msg.to or ""
        cc_addr = msg.cc or ""
        date_str = str(msg.date) if msg.date else ""
        
        # Extract body (extract-msg handles both plain and HTML)
        body = msg.body or ""
        
        # Limit text size to first 50KB to avoid memory issues
        if len(body) > 50000:
            body = body[:50000] + "\n[... email truncated ...]"
        
        # Combine into formatted text
        text = f"Subject: {subject}\n"
        text += f"From: {from_addr}\n"
        if to_addr:
            text += f"To: {to_addr}\n"
        if cc_addr:
            text += f"Cc: {cc_addr}\n"
        if date_str:
            text += f"Date: {date_str}\n"
        text += "\n" + (body.strip() or "(empty body)")
        
        # Clean up message object to free memory
        del msg
        
        return {
            "text": text.strip(),
            "title": f"Email: {subject}",
            "source_type": "email",
            "metadata": {
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "cc": cc_addr,
                "date": date_str,
                "filename": file_path.name,
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to extract from {file_path}: {e}")
        return None


def extract_from_eml(file_path: Path) -> Optional[Dict]:
    """
    Extract text from standard .eml file (RFC 822).
    
    Args:
        file_path: Path to .eml file
    
    Returns:
        Standardized dict with text, title, source_type, metadata
    """
    try:
        from email import message_from_file
    except ImportError:
        logger.error("email module not available")
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            msg = message_from_file(f)
        
        # Extract fields
        subject = msg.get("Subject", "(no subject)")
        from_addr = msg.get("From", "unknown")
        to_addr = msg.get("To", "")
        cc_addr = msg.get("Cc", "")
        date_str = msg.get("Date", "")
        
        # Extract body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True)
                    if isinstance(body, bytes):
                        body = body.decode("utf-8", errors="ignore")
                    break
        else:
            body = msg.get_payload(decode=True)
            if isinstance(body, bytes):
                body = body.decode("utf-8", errors="ignore")
        
        # Limit text size to first 50KB to avoid memory issues
        if len(body) > 50000:
            body = body[:50000] + "\n[... email truncated ...]"
        
        # Combine into formatted text
        text = f"Subject: {subject}\n"
        text += f"From: {from_addr}\n"
        if to_addr:
            text += f"To: {to_addr}\n"
        if cc_addr:
            text += f"Cc: {cc_addr}\n"
        if date_str:
            text += f"Date: {date_str}\n"
        text += "\n" + (body or "(empty body)")
        
        return {
            "text": text.strip(),
            "title": f"Email: {subject}",
            "source_type": "email",
            "metadata": {
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "cc": cc_addr,
                "date": date_str,
                "filename": file_path.name,
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to extract from {file_path}: {e}")
        return None


def extract_email(file_path: Path) -> Optional[Dict]:
    """
    Auto-detect email format and extract.
    
    Args:
        file_path: Path to email file (.msg or .eml)
    
    Returns:
        Standardized dict or None
    """
    suffix = file_path.suffix.lower()
    
    if suffix == ".msg":
        return extract_from_msg(file_path)
    elif suffix == ".eml":
        return extract_from_eml(file_path)
    else:
        logger.warning(f"Unknown email format: {suffix}")
        return None


# ========================
# Batch Email Processing
# ========================

def extract_emails_from_folder(folder_path: Path):
    """
    Extract email files from a folder recursively (generator - streaming).
    
    Args:
        folder_path: Path to folder containing .msg and .eml files
    
    Yields:
        Standardized email dicts (one at a time to avoid memory buildup)
    """
    if not folder_path.exists():
        logger.warning(f"Folder not found: {folder_path}")
        return
    
    # Find all .msg and .eml files
    count = 0
    for email_file in folder_path.rglob("*"):
        if email_file.suffix.lower() in [".msg", ".eml"]:
            extracted = extract_email(email_file)
            if extracted:
                count += 1
                yield extracted
                logger.debug(f"Extracted: {email_file.name}")
    
    logger.info(f"Extracted {count} emails from {folder_path}")


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.DEBUG)
    
    test_folder = Path("C:/Users/angela/OneDrive - New Mexico Mutual/Projects/ECM Replacement Research/Emails")
    if test_folder.exists():
        emails = extract_emails_from_folder(test_folder)
        print(f"Found {len(emails)} emails")
        if emails:
            print(f"First email: {emails[0]['title']}")
    else:
        print(f"Test folder not found: {test_folder}")

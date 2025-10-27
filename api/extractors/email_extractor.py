"""
Email extraction module for Outlook .msg and .eml files.

Extracts text from email messages, preserving:
- Subject line
- From, To, CC, Date
- Body text (plain + HTML)
- Attachment info

Workflow:
  1. Read .msg file (python-pptx or msg-extractor)
  2. Extract headers and body
  3. Combine into structured text
  4. Return standardized format
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

# ========================
# Email Extraction
# ========================

def extract_from_msg(file_path: Path) -> Optional[Dict]:
    """
    Extract text from Outlook .msg file.
    
    Args:
        file_path: Path to .msg file
    
    Returns:
        Standardized dict with text, title, source_type, metadata
        Returns None if extraction fails
    """
    try:
        from email import message_from_binary_file
        import olefile
    except ImportError:
        logger.error("olefile or email module not available for .msg extraction")
        return None

    try:
        # Open OLE file (Outlook .msg files are OLE containers)
        ole = olefile.OleFileIO(str(file_path))
        
        # Extract message stream
        if not ole.exists("__substg1.0_011D0102"):
            logger.warning(f"No message stream in {file_path}")
            ole.close()
            return None
        
        message_data = ole.openstream("__substg1.0_011D0102").read()
        ole.close()
        
        # Parse email message
        msg = message_from_binary_file(message_data)
        
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
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body = payload.decode("utf-8", errors="ignore")
                    else:
                        body = payload
                    break
        else:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode("utf-8", errors="ignore")
            else:
                body = payload
        
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

def extract_emails_from_folder(folder_path: Path) -> List[Dict]:
    """
    Extract all email files from a folder recursively.
    
    Args:
        folder_path: Path to folder containing .msg and .eml files
    
    Returns:
        List of standardized email dicts
    """
    emails = []
    
    if not folder_path.exists():
        logger.warning(f"Folder not found: {folder_path}")
        return emails
    
    # Find all .msg and .eml files
    for email_file in folder_path.rglob("*"):
        if email_file.suffix.lower() in [".msg", ".eml"]:
            extracted = extract_email(email_file)
            if extracted:
                emails.append(extracted)
                logger.debug(f"Extracted: {email_file.name}")
    
    logger.info(f"Extracted {len(emails)} emails from {folder_path}")
    return emails


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

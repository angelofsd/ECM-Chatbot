import os, sys, csv, hashlib, shutil, subprocess, datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple
from pypdf import PdfReader
from tqdm import tqdm

# =========================
# CONFIG: EDIT THESE PATHS
# =========================
SOURCE_DIR = r"C:\Users\angela\OneDrive - New Mexico Mutual\Projects\ECM Replacement Research"
OUTPUT_DIR = r"C:\ecm-staging\04_text_ready"         # OCR’d or passthrough PDFs go here
INVENTORY_CSV = r"C:\ecm-staging\inventory.csv"      # inventory+flags
MAX_WORKERS = 6                                       # parallelism for OCR/copy
SAMPLE_PAGES = 5                                      # pages to sample to decide OCR

# Department/ACL tag guesses based on path parts (edit as needed)
DEPT_TAGS = {"claims":"Claims", "underwriting":"Underwriting", "billing":"Billing",
             "legal":"Legal", "subrogation":"Subrogation", "integrion":"Integrion",
             "it":"IT", "policy":"Policy_and_Procedure", "p&p":"Policy_and_Procedure"}

# ocrmypdf options
OCR_ARGS = [
    "ocrmypdf",
    "--deskew",
    "--rotate-pages",
    "--skip-text",          # don't re-OCR text PDFs
    "--output-type", "pdfa",
    "--language", "eng",
]

# =========================

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def file_meta(path: Path) -> Tuple[int, str]:
    size = path.stat().st_size
    mt = datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    return size, mt

def guess_acl_tags(path: Path) -> Tuple[Optional[str], list]:
    # Guess department from any folder name segment
    parts = [p.lower() for p in path.parts]
    for key, val in DEPT_TAGS.items():
        if any(key in seg for seg in parts):
            return val, [val]
    return None, []

def pdf_needs_ocr(path: Path, sample_pages: int = SAMPLE_PAGES) -> bool:
    try:
        r = PdfReader(str(path))
        total_chars = 0
        for i, page in enumerate(r.pages):
            if i >= sample_pages:
                break
            txt = page.extract_text() or ""
            total_chars += len(txt.strip())
        # If zero text across the sample → treat as scanned
        return total_chars == 0
    except Exception:
        # unreadable/corrupt/password → try OCR path
        return True

def ensure_dest(out_root: Path, src_root: Path, src_path: Path, suffix: str = "_ocr") -> Path:
    rel = src_path.relative_to(src_root)
    out = out_root.joinpath(rel)
    out.parent.mkdir(parents=True, exist_ok=True)
    # if making an OCR’d variant, change filename appropriately
    if out.suffix.lower() == ".pdf" and suffix and not out.stem.endswith(suffix):
        out = out.with_name(out.stem + f"{suffix}" + out.suffix)
    return out

def run_ocr(src: Path, dst: Path) -> Tuple[bool, str]:
    cmd = OCR_ARGS + [str(src), str(dst)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if cp.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
            return True, ""
        return False, cp.stderr.strip() or cp.stdout.strip()
    except FileNotFoundError as e:
        return False, f"Executable not found (ocrmypdf/Tesseract/Ghostscript missing?): {e}"
    except Exception as e:
        return False, str(e)

def copy_pdf(src: Path, dst: Path) -> Tuple[bool, str]:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True, ""
    except Exception as e:
        return False, str(e)

def process_pdf(src_root: Path, out_root: Path, pdf_path: Path):
    size, mt = file_meta(pdf_path)
    sha = sha256_file(pdf_path)
    dept, acl = guess_acl_tags(pdf_path.parent)
    needs = pdf_needs_ocr(pdf_path)

    if needs:
        dst = ensure_dest(out_root, src_root, pdf_path, suffix="_ocr")
        ok, err = run_ocr(pdf_path, dst)
        action = "ocr" if ok else f"ocr_fail:{err[:120]}"
        out_path = str(dst) if ok else ""
    else:
        # Pass-through copy as-is (no suffix)
        rel = pdf_path.relative_to(src_root)
        dst = out_root.joinpath(rel)
        ok, err = copy_pdf(pdf_path, dst)
        action = "copy" if ok else f"copy_fail:{err[:120]}"
        out_path = str(dst) if ok else ""

    return {
        "source_path": str(pdf_path),
        "relative_path": str(pdf_path.relative_to(src_root)),
        "size_bytes": size,
        "sha256": sha,
        "last_modified": mt,
        "needs_ocr": "yes" if needs else "no",
        "action": action,
        "output_path": out_path,
        "department_guess": dept or "",
        "acl_tags": ";".join(acl) if acl else ""
    }

def main():
    src_root = Path(SOURCE_DIR).resolve()
    out_root = Path(OUTPUT_DIR).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    pdfs = [p for p in src_root.rglob("*.pdf") if p.is_file()]
    if not pdfs:
        print(f"No PDFs found under: {src_root}")
        return

    rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(process_pdf, src_root, out_root, p): p for p in pdfs}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Processing PDFs"):
            try:
                rows.append(fut.result())
            except Exception as e:
                p = futures[fut]
                size, mt = file_meta(p)
                sha = sha256_file(p)
                dept, acl = guess_acl_tags(p.parent)
                rows.append({
                    "source_path": str(p),
                    "relative_path": str(p.relative_to(src_root)),
                    "size_bytes": size,
                    "sha256": sha,
                    "last_modified": mt,
                    "needs_ocr": "unknown",
                    "action": f"exception:{str(e)[:120]}",
                    "output_path": "",
                    "department_guess": dept or "",
                    "acl_tags": ";".join(acl) if acl else ""
                })

    # Write inventory
    inv_path = Path(INVENTORY_CSV)
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_path", "relative_path", "size_bytes", "sha256", "last_modified",
        "needs_ocr", "action", "output_path", "department_guess", "acl_tags"
    ]
    with inv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Summary
    total = len(rows)
    ocrd = sum(1 for r in rows if r["action"] == "ocr")
    copied = sum(1 for r in rows if r["action"] == "copy")
    failed = sum(1 for r in rows if r["action"].startswith("ocr_fail") or r["action"].startswith("copy_fail") or r["action"].startswith("exception"))
    print(f"\nDone. Total: {total} | OCR’d: {ocrd} | Copied: {copied} | Failures: {failed}")
    print(f"Inventory: {inv_path}")
    print(f"Output root: {out_root}")

if __name__ == "__main__":
    main()

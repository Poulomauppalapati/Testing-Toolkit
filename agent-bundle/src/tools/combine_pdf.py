"""
combine_pdf.py
Combine multiple files (Office, images, PDFs) into one or more PDFs.

Reuses office_convert (xlsx/docx/csv/rtf/txt -> PDF) and image-to-PDF
conversion. Supports three modes:

    none   -> single combined output
    size   -> split when cumulative size exceeds N MB
    count  -> split into chunks of N items
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from pypdf import PdfReader, PdfWriter

from tools.office_convert import convert_to_pdf, is_office_extension

PDF_EXTS: Final[frozenset[str]] = frozenset({".pdf"})
IMAGE_EXTS: Final[frozenset[str]] = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif", ".webp",
})

BatchMode = Literal["none", "size", "count"]


@dataclass(slots=True)
class CombineResult:
    output_files: list[Path] = field(default_factory=list)
    n_inputs: int = 0
    n_pages_total: int = 0
    n_failed: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)


def _safe_name(s: str) -> str:
    bad = '<>:"/\\|?*'
    return "".join("_" if c in bad else c for c in s).strip(". ") or "out"


def _convert_one_to_pdf(
    src: Path, tmp_dir: Path, paper_size: str,
) -> tuple[Path | None, str]:
    """Convert a single input into a PDF located in tmp_dir.

    Returns (pdf_path, error_message). pdf_path is None on failure.
    """
    ext = src.suffix.lower()
    out_pdf = tmp_dir / f"{_safe_name(src.stem)}_{abs(hash(str(src)))}.pdf"
    try:
        if ext in PDF_EXTS:
            return src, ""  # passthrough
        if ext in IMAGE_EXTS:
            from PIL import Image
            with Image.open(src) as im:
                if im.mode in ("RGBA", "LA", "P"):
                    im = im.convert("RGB")
                im.save(out_pdf, "PDF", resolution=150.0)
            return out_pdf, ""
        if is_office_extension(ext):
            status, msg = convert_to_pdf(src, out_pdf, paper_size)
            if status == "FAILED":
                return None, msg
            return out_pdf, msg
        return None, f"Unsupported extension: {ext}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e!r}"


def _pdf_size_bytes(p: Path) -> int:
    try:
        return p.stat().st_size
    except Exception:
        return 0


def _pdf_page_count(p: Path) -> int:
    try:
        return len(PdfReader(str(p)).pages)
    except Exception:
        return 0


def _merge_pdfs(pdfs: list[Path], out_path: Path) -> int:
    writer = PdfWriter()
    total_pages = 0
    for p in pdfs:
        try:
            r = PdfReader(str(p))
            for page in r.pages:
                writer.add_page(page)
                total_pages += 1
        except Exception:
            pass
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        writer.write(f)
    return total_pages



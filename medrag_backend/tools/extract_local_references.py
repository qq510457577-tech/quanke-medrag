from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
FILES_DIR = ROOT / "files"
OUTPUT = ROOT / "extract" / "local_reference_drafts.json"


def extract_preview(pdf_path: Path, max_pages: int = 5, max_chars: int = 2500) -> str:
    reader = PdfReader(str(pdf_path))
    text_chunks = []
    for page in reader.pages[:max_pages]:
        text_chunks.append(page.extract_text() or "")
    return "\n".join(text_chunks).strip()[:max_chars]


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for pdf_path in sorted(FILES_DIR.glob("*.pdf")):
        payload.append(
            {
                "file": str(pdf_path.relative_to(ROOT)),
                "title_guess": pdf_path.stem.lstrip("_"),
                "preview_text": extract_preview(pdf_path),
            }
        )
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} draft references to {OUTPUT}")


if __name__ == "__main__":
    main()

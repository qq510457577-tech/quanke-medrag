from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from medrag_backend.app.config import REFERENCE_DIR, VECTOR_STORE_DIR
from medrag_backend.app.services.retrieval_service import build_vector_store

FILES_DIR = ROOT / "files"


def main() -> None:
    result = build_vector_store(files_dir=FILES_DIR, reference_dir=REFERENCE_DIR, output_dir=VECTOR_STORE_DIR)
    print(f"Built local vector store with {result['chunks']} chunks and {result['features']} features")


if __name__ == "__main__":
    main()

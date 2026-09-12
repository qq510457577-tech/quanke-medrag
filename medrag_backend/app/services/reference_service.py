from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from ..config import REFERENCE_DIR


class ReferenceService:
    def __init__(self) -> None:
        self.references = self._load_reference_catalog()

    def _load_reference_catalog(self) -> Dict[str, Dict]:
        catalog: Dict[str, Dict] = {}
        for path in sorted(Path(REFERENCE_DIR).glob("*.json")):
            items = json.loads(path.read_text(encoding="utf-8"))
            for item in items:
                catalog[item["id"]] = item
        return catalog

    def get_many(self, reference_ids: List[str]) -> List[Dict]:
        result: List[Dict] = []
        seen = set()
        for reference_id in reference_ids:
            item = self.references.get(reference_id)
            if item and reference_id not in seen:
                result.append(item)
                seen.add(reference_id)
        return result

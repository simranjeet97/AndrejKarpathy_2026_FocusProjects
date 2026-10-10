import os
import json
from typing import Any, Dict, List, Optional

_RUNBOOKS_PATH = os.path.join(os.path.dirname(__file__), "runbooks.json")

def load_all_runbooks() -> List[Dict[str, Any]]:
    if not os.path.exists(_RUNBOOKS_PATH):
        return []
    with open(_RUNBOOKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def search_runbook(service_name: str, symptom: str) -> Optional[Dict[str, Any]]:
    runbooks = load_all_runbooks()
    query_text = f"{service_name} {symptom}".lower()

    best_match = None
    max_score = 0

    for rb in runbooks:
        score = 0
        for kw in rb.get("service_match", []):
            if kw.lower() in query_text:
                score += 2
        for word in rb.get("title", "").lower().split():
            if len(word) > 3 and word in query_text:
                score += 1
        if score > max_score:
            max_score = score
            best_match = rb

    return best_match if max_score > 0 else (runbooks[0] if runbooks else None)

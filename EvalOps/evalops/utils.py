import json
import re
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

def truncate_text(text: str, max_len: int = 200) -> str:
    """
    Truncate text to a maximum length, appending '...' if truncated.
    """
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."

def flatten_json(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """
    Flatten a nested dictionary.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_json(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def parse_json_safe(text: str) -> Optional[Dict[str, Any]]:
    """
    Robustly parse JSON, stripping markdown fences and surrounding whitespace.
    """
    text_clean = text.strip()
    
    # Strip markdown fences if present
    if text_clean.startswith("```"):
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text_clean, re.DOTALL | re.IGNORECASE)
        if match:
            text_clean = match.group(1).strip()
            
    # Try direct parse
    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        pass
        
    # Try to extract the JSON object bounding braces
    try:
        start_idx = text_clean.find('{')
        end_idx = text_clean.rfind('}')
        if start_idx != -1 and end_idx != -1:
            candidate = text_clean[start_idx:end_idx + 1]
            return json.loads(candidate)
    except Exception:
        pass
        
    return None

def generate_run_id() -> str:
    """
    Generate a unique run ID in hex format.
    """
    return uuid.uuid4().hex

def timestamp_now() -> str:
    """
    Get current UTC timestamp in ISO 8601 format.
    """
    return datetime.utcnow().isoformat()

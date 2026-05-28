"""
log_parser.py — Extracts substitution fields from logTXT entries.

Expected message format (inside a GetClaimsData_ACB entry):
  GetClaimsData_ACB STEP:8 Original Drug: 00173087410,Drug Source: W,
  Claim DAW Code: 0 has been switched to CLAIM NDC: 00173087410,...
"""

import json
import re

# Matches the GetClaimsData_ACB switched-NDC message
_PATTERN = re.compile(
    r"GetClaimsData_ACB\s+STEP:\d+\s+"
    r"Original Drug:\s*(\d+),\s*Drug Source:\s*(\w+),\s*Claim DAW Code:\s*(\S+)\s+"
    r"has been switched to CLAIM NDC:\s*(\d+)",
    re.IGNORECASE,
)


def parse_log(log_text: str) -> dict | None:
    """
    Search log_text for the GetClaimsData_ACB substitution message and return
    extracted fields. Returns None if the pattern is not found.

    Handles two formats:
    1. JSON array of {"MessageDesc": "..."} objects
    2. Raw text containing the message directly
    """
    if not isinstance(log_text, str):
        return None

    # Try JSON array of {"MessageDesc": ...} objects
    try:
        entries = json.loads(log_text)
        if isinstance(entries, list):
            for entry in entries:
                msg = entry.get("MessageDesc", "")
                m = _PATTERN.search(msg)
                if m:
                    return _to_dict(m)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Fallback: search raw text
    m = _PATTERN.search(log_text)
    return _to_dict(m) if m else None


def _to_dict(m: re.Match) -> dict:
    return {
        "requested_ndc":     m.group(1).strip(),
        "drug_source":       m.group(2).strip(),
        "daw_code":          m.group(3).strip(),
        "log_alternate_ndc": m.group(4).strip(),
    }

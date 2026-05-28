"""
log_parser.py — Extracts substitution fields from logTXT entries.

Expected message format (found inside the logTXT):
  Requested NDC: 00002148480 Substituted with Alternate NDC: 00002148401
  For DAW Code: 0 Drug Source: W Substitution Indicator: B
"""

import json
import re

_PATTERN = re.compile(
    r"Requested NDC:\s*(\d+)\s+Substituted with Alternate NDC:\s*(\d+)\s+"
    r"For DAW Code:\s*(\S+)\s+Drug Source:\s*(\S+)\s+Substitution Indicator:\s*(\S+)",
    re.IGNORECASE,
)


def parse_log(log_text: str) -> dict | None:
    """
    Search log_text for the substitution message and return extracted fields.
    Returns None if the pattern is not found.

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
        "requested_ndc":          m.group(1).strip(),
        "log_alternate_ndc":      m.group(2).strip(),
        "daw_code":               m.group(3).strip(),
        "drug_source":            m.group(4).strip(),
        "substitution_indicator": m.group(5).strip(),
    }

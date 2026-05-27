# ============================================================
#  Alternate Drug Dashboard — Configuration
#  Edit this file before running the app
# ============================================================

# ── API Settings ──────────────────────────────────────────────────────────────
API_CONFIG = {
    # Full URL of the drug detail service
    # Replace with your real endpoint
    "base_url": "https://your-api-host.com",
    "endpoint": "/your-endpoint-path",

    # API Key — replace with your real key
    # Keep this private — never commit real keys to GitHub
    "api_key": "YOUR-API-KEY-HERE",

    # Header name used to send the API key
    "api_key_header": "x-api-key",

    # Request timeout in milliseconds (matches <Timeout> in XML request)
    "timeout_ms": 60000,

    # Request timeout in seconds (used by Python requests library)
    "timeout_seconds": 60,

    # Batch size — max NDCs per request (service accepts up to 10)
    "batch_size": 10,

    # ── Network / Security settings ───────────────────────────────────────────
    # Set to False if the API uses a self-signed or internal SSL certificate
    # WARNING: only disable in trusted internal networks
    "ssl_verify": False,

    # Corporate proxy settings — set if your network requires a proxy
    # Format: "http://proxy-host:port" or "http://user:pass@proxy-host:port"
    # Set to None if no proxy is needed
    "proxy_http":  None,   # e.g. "http://proxy.company.com:8080"
    "proxy_https": None,   # e.g. "http://proxy.company.com:8080"

    # ── Fixed request fields (from XML contract) ──────────────────────────────
    "channel":                    "YOUR-CHANNEL",
    "user_id":                    "YOUR-USER-ID",
    "format":                     "XML",
    "inq_type":                   "A",       # A = Alternate drug inquiry
    "switch_invalid_ndc":         "Y",       # Switch if NDC is invalid
    "alternative_indicator":      "Y",       # Return alternative drugs
    "substitution_indicator":     "G",       # Default fallback (overridden by CSV)
    "unit_dose_indicator":        "N",
    "test_mode":                  "N",       # Y = test mode, N = production
}

# ── Export Settings ───────────────────────────────────────────────────────────
EXPORT_CONFIG = {
    # Default file name for export (without extension)
    "default_filename": "alternate_results",
}

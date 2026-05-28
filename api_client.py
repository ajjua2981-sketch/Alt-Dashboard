"""
api_client.py — Handles all communication with the Drug Detail REST API.

TODO: Fill in the following before going live:
  1. Update base_url and endpoint in config.py
  2. Update the xmlns value in _build_xml_request()
  3. Update the NS value in _parse_xml_response()
  4. Update channel and user_id in config.py
"""

import ssl
import requests
from datetime import date
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from xml.etree.ElementTree import Element, SubElement, tostring

from config import API_CONFIG


class _TLS12Adapter(HTTPAdapter):
    """Force TLS 1.2 — required by servers that reject TLS 1.3 EOF handshakes."""
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context(ssl_version=ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        super().init_poolmanager(*args, **kwargs)


# ── Public function ───────────────────────────────────────────────────────────

def lookup_alternate_drugs(drugs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Takes a list of:
        { "ndc": "...", "dawCode": "...", "substitutionIndicator": "..." }

    Splits into batches of up to 10 and calls the XML API per batch.

    Returns:
        (results, errors)
        results : list of result dicts (one per input NDC)
        errors  : list of {"ndc": ..., "error": ...} for failed items
    """
    batch_size  = API_CONFIG["batch_size"]
    all_results = []
    all_errors  = []

    batches = [drugs[i:i + batch_size] for i in range(0, len(drugs), batch_size)]

    for batch in batches:
        results, errors = _call_api(batch)
        all_results.extend(results)
        all_errors.extend(errors)

    return all_results, all_errors


# ── Internal helpers ──────────────────────────────────────────────────────────

def _call_api(batch: list[dict]) -> tuple[list[dict], list[dict]]:
    """Call the XML API for a single batch. Returns (results, errors)."""
    url     = API_CONFIG["base_url"] + API_CONFIG["endpoint"]
    headers = {
        API_CONFIG["api_key_header"]: API_CONFIG["api_key"],
        "Content-Type": "application/xml",
        "Accept":        "application/xml",
    }
    xml_payload = _build_xml_request(batch)

    # Build proxy dict if configured
    proxies = {}
    if API_CONFIG.get("proxy_http"):
        proxies["http"]  = API_CONFIG["proxy_http"]
    if API_CONFIG.get("proxy_https"):
        proxies["https"] = API_CONFIG["proxy_https"]

    try:
        session = requests.Session()
        session.mount("https://", _TLS12Adapter())
        response = session.post(
            url,
            data=xml_payload,
            headers=headers,
            timeout=API_CONFIG["timeout_seconds"],
            verify=False,
            proxies=proxies if proxies else None,
        )
        response.raise_for_status()
        return _parse_xml_response(response.text, batch)

    except requests.exceptions.HTTPError as exc:
        error_msg = f"HTTP {exc.response.status_code}: {exc.response.text}"
        return [], [{"ndc": d["ndc"], "error": error_msg} for d in batch]

    except requests.exceptions.SSLError as exc:
        error_msg = f"SSL Error: {exc} — try setting ssl_verify=False in config.py if using internal certs"
        return [], [{"ndc": d["ndc"], "error": error_msg} for d in batch]

    except requests.exceptions.ProxyError as exc:
        error_msg = f"Proxy Error: {exc} — set proxy settings in config.py"
        return [], [{"ndc": d["ndc"], "error": error_msg} for d in batch]

    except requests.exceptions.ConnectionError as exc:
        error_msg = f"Connection Error: {exc}"
        return [], [{"ndc": d["ndc"], "error": error_msg} for d in batch]

    except requests.exceptions.Timeout:
        return [], [{"ndc": d["ndc"], "error": "Request timed out"} for d in batch]

    except Exception as exc:
        return [], [{"ndc": d["ndc"], "error": str(exc)} for d in batch]


def _build_xml_request(batch: list[dict]) -> bytes:
    """
    Builds the XML request body for the given batch.
    TODO: Update the xmlns value below with your real API namespace.
    """
    sub_indicator = batch[0].get("substitutionIndicator", API_CONFIG["substitution_indicator"])

    root = Element("DrugDetailRequest")
    root.set("xmlns", API_CONFIG.get("xmlns", ""))

    SubElement(root, "TestMode").text           = API_CONFIG["test_mode"]
    SubElement(root, "Channel").text            = API_CONFIG["channel"]
    SubElement(root, "UserId").text             = API_CONFIG["user_id"]
    SubElement(root, "Format").text             = API_CONFIG["format"]
    SubElement(root, "Timeout").text            = str(API_CONFIG["timeout_ms"])
    SubElement(root, "DateOfService").text      = date.today().strftime("%Y-%m-%d")
    SubElement(root, "InqType").text            = API_CONFIG["inq_type"]

    ndc_list = SubElement(root, "NDCList")
    for drug in batch:
        SubElement(ndc_list, "NDC").text = drug["ndc"]

    SubElement(root, "SwitchInvalidNDCIndicator").text = API_CONFIG["switch_invalid_ndc"]
    SubElement(root, "AlternativeIndicator").text      = API_CONFIG["alternative_indicator"]
    SubElement(root, "SubstitutionIndicator").text     = sub_indicator
    SubElement(root, "UnitDoseIndicator").text         = API_CONFIG["unit_dose_indicator"]

    return tostring(root, encoding="utf-8", xml_declaration=True)


def _parse_xml_response(xml_text: str, batch: list[dict]) -> tuple[list[dict], list[dict]]:
    """Parses the XML response into (results, errors) — always returns both lists."""
    import xml.etree.ElementTree as ET

    NS = API_CONFIG.get("xmlns", "")
    ns = f"{{{NS}}}" if NS else ""

    daw_lookup = {d["ndc"]: d.get("dawCode", "") for d in batch}

    try:
        root = ET.fromstring(xml_text)

        status_code = _get_ns_text(root, ns, "StatusCode")
        status_msg  = _get_ns_text(root, ns, "StatusMessage")
        if status_code and status_code != "0000":
            return [], [{"ndc": d["ndc"], "error": f"{status_code}: {status_msg}"} for d in batch]

        results      = []
        drug_records = root.find(f"{ns}DrugRecords")
        if drug_records is None:
            return [], [{"ndc": d["ndc"], "error": "No DrugRecords in response"} for d in batch]

        for drug_record in drug_records.findall(f"{ns}DrugRecord"):
            requested_ndc  = _get_ns_text(drug_record, ns, "NDC")
            requested_name = _get_ns_text(drug_record, ns, "LabelName")
            sub_indicator  = _get_ns_text(drug_record, ns, "SubstitutionIndicator")
            daw_code       = daw_lookup.get(requested_ndc, "")

            alt_record = drug_record.find(f"{ns}AlternativeDrugRecord")
            if alt_record is not None:
                alt_ndc  = _get_ns_text(alt_record, ns, "NDC")
                alt_name = _get_ns_text(alt_record, ns, "LabelName")
            else:
                alt_ndc  = ""
                alt_name = "No Alternate Found"

            results.append({
                "Requested NDC":          requested_ndc,
                "Requested Drug Name":    requested_name,
                "DAW Code":               daw_code,
                "Substitution Indicator": sub_indicator,
                "Alternate Drug NDC":     alt_ndc,
                "Alternate Drug Name":    alt_name,
            })

        return results, []

    except ET.ParseError as exc:
        return [], [{"ndc": d["ndc"], "error": f"XML parse error: {exc}"} for d in batch]


def _get_ns_text(element, ns: str, tag: str) -> str:
    """Extract text from an XML child element safely."""
    child = element.find(f"{ns}{tag}")
    return child.text.strip() if child is not None and child.text else ""


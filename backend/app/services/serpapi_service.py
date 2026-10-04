import logging
import os
import re
from urllib.parse import urlparse
import httpx
from typing import Any

logger = logging.getLogger(__name__)

SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"

TRUSTED_DOMAINS = {
    "medlineplus.gov": "MedlinePlus (National Library of Medicine)",
    "mayoclinic.org": "Mayo Clinic",
    "cdc.gov": "Centers for Disease Control and Prevention (CDC)",
    "nih.gov": "National Institutes of Health (NIH)",
    "ncbi.nlm.nih.gov": "National Center for Biotechnology Information (NCBI)",
    "clevelandclinic.org": "Cleveland Clinic",
    "nhs.uk": "National Health Service (NHS UK)",
    "health.harvard.edu": "Harvard Health Publishing",
    "hopkinsmedicine.org": "Johns Hopkins Medicine",
    "who.int": "World Health Organization (WHO)",
    "fda.gov": "U.S. Food and Drug Administration (FDA)",
    "webmd.com": "WebMD Health",
}


from pathlib import Path
from dotenv import load_dotenv

def _reload_env_if_needed():
    for candidate in (
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
    ):
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=True)


def get_serpapi_key() -> str | None:
    key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not key:
        _reload_env_if_needed()
        key = os.getenv("SERPAPI_API_KEY", "").strip()
    return key if key else None


def identify_source_name(url: str, raw_source: str = "") -> str:
    """Returns a recognizable, trustworthy institution name based on domain."""
    if not url:
        return raw_source or "Medical Resource"
    try:
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        for trusted_dom, label in TRUSTED_DOMAINS.items():
            if domain == trusted_dom or domain.endswith("." + trusted_dom):
                return label
        return raw_source or domain
    except Exception:
        return raw_source or "Medical Resource"


def extract_explicit_medical_topics(report_text: str, plan: dict[str, Any]) -> list[str]:
    """Extracts explicit medication and medical condition topics from the report and care plan.

    Note: Strictly extracts topics explicitly present in the report. Does not invent topics.
    """
    topics: list[str] = []

    medicines = plan.get("medicines") or []
    for med in medicines:
        if not isinstance(med, str):
            continue
        clean_med = re.sub(r"\[.*?\]", "", med).strip()
        first_token = clean_med.split()[0] if clean_med else ""
        first_token = re.sub(r"[^\w\-]", "", first_token)
        if len(first_token) >= 3 and first_token.lower() not in ("take", "avoid", "with", "oral", "tablet", "capsule", "mg", "daily"):
            if first_token not in topics:
                topics.append(first_token)

    common_conditions = [
        "hypertension",
        "high blood pressure",
        "type 2 diabetes",
        "diabetes",
        "hyperlipidemia",
        "high cholesterol",
        "asthma",
        "copd",
        "heart failure",
        "osteoarthritis",
        "arthritis",
        "pneumonia",
        "bronchitis",
        "anemia",
        "chronic kidney disease",
        "gastroesophageal reflux",
        "gerd",
    ]

    report_lower = (report_text or "").lower()
    for condition in common_conditions:
        if re.search(r"\b" + re.escape(condition) + r"\b", report_lower):
            title_cond = condition.title()
            if title_cond not in topics:
                topics.append(title_cond)

    return topics[:4]


async def search_medical_resources(topics: list[str]) -> list[dict[str, Any]]:
    """Uses SerpApi to search for educational resources from recognized, trustworthy institutions.

    Educational only. Strictly does not modify or generate medical advice.
    Gracefully returns an empty list if SerpApi is not configured or an error occurs.
    """
    api_key = get_serpapi_key()
    if not api_key:
        logger.info("SERPAPI_API_KEY is not set. Skipping external educational search.")
        return []

    if not topics:
        return []

    resources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    trusted_sites_query = " OR ".join([f"site:{dom}" for dom in (
        "medlineplus.gov",
        "mayoclinic.org",
        "cdc.gov",
        "nih.gov",
        "clevelandclinic.org",
        "nhs.uk",
        "health.harvard.edu"
    )])

    for topic in topics[:2]:
        query = f'"{topic}" patient education guide ({trusted_sites_query})'
        params = {
            "engine": "google",
            "q": query,
            "api_key": api_key,
            "num": 3,
            "hl": "en",
            "gl": "us",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(SERPAPI_SEARCH_URL, params=params)
                if res.is_error:
                    logger.warning("SerpApi returned error %s for query %s", res.status_code, topic)
                    continue

                data = res.json()
                organic_results = data.get("organic_results", [])
                for item in organic_results:
                    link = item.get("link", "").strip()
                    if not link or link in seen_urls:
                        continue

                    title = item.get("title", "").strip()
                    snippet = item.get("snippet", "").strip()
                    raw_source = item.get("source", "").strip()

                    source_name = identify_source_name(link, raw_source)
                    seen_urls.add(link)

                    resources.append({
                        "title": title or f"Educational Guide: {topic}",
                        "source": source_name,
                        "link": link,
                        "snippet": snippet,
                        "topic": topic,
                    })

                    if len(resources) >= 6:
                        break
        except Exception as exc:
            logger.warning("Error fetching SerpApi resources for topic '%s': %s", topic, exc)
            continue

        if len(resources) >= 6:
            break

    return resources

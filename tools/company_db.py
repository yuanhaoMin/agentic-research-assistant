import json
from typing import Any, Dict


def get_company_info(company_name: str, db_path: str) -> Dict[str, Any]:
    """
    Simulated internal DB lookup.
    db is a JSON list of company profiles.
    """
    with open(db_path, "r", encoding="utf-8") as f:
        companies = json.load(f)

    for c in companies:
        if c.get("name", "").lower() == company_name.lower():
            return c

    # Fallback
    return {
        "name": company_name,
        "industry": "Unknown",
        "headquarters": "Unknown",
        "website": "Unknown",
        "products": [],
        "partnerships": [],
        "risk_category": "unknown",
        "sensitive_projects": [],
    }

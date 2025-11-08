#!/usr/bin/env python3
import os
import sys
import time
import json
import datetime
from typing import Dict, List, Any

import requests

try:
    import yaml  # type: ignore
except Exception:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


API_URL = "https://api-gw.platform.linuxfoundation.org/project-service/v1/projects"
FOUNDATION_ID_CNCF = "a0941000002wBz4AAE"
PAGE_SIZE = 100
SLEEP_BETWEEN_CALLS_SECONDS = 0.2
OUTPUT_PATH = os.path.join(os.getcwd(), "pcc_projects.yaml")


def get_lfx_token() -> str:
    token = os.getenv("LFX_TOKEN", "").strip()
    if not token:
        print("Error: LFX_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return token


def fetch_page(session: requests.Session, offset: int, limit: int) -> Dict[str, Any]:
    params = {"offset": offset, "limit": limit}
    response = session.get(API_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def project_to_record(p: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": p.get("Name"),
        "slug": p.get("Slug"),
        "category": p.get("Category"),
        "status": p.get("Status"),
        "project_logo": p.get("ProjectLogo"),
        "repository_url": p.get("RepositoryURL"),
    }


def category_rank(category: Any) -> int:
    if category == "TAG":
        return 1
    if category == "Graduated":
        return 2
    if category == "Incubating":
        return 3
    if category == "Sandbox":
        return 4
    # Unknown/None go last
    return 99


def main() -> None:
    token = get_lfx_token()
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "project-status-audit/0.1 (+github actions)",
        }
    )

    offset = 0
    all_records: List[Dict[str, Any]] = []

    while True:
        data = fetch_page(session, offset=offset, limit=PAGE_SIZE)
        items: List[Dict[str, Any]] = data.get("Data") or []
        if not items:
            break

        for p in items:
            try:
                foundation = (p.get("Foundation") or {}).get("ID")
                if foundation != FOUNDATION_ID_CNCF:
                    continue
                # Keep both active and forming (Formation - Exploratory)
                record = project_to_record(p)
                all_records.append(record)
            except Exception:
                # Skip malformed entries but continue
                continue

        offset += len(items)
        time.sleep(SLEEP_BETWEEN_CALLS_SECONDS)

    # Sort for stable output
    all_records.sort(key=lambda r: (category_rank(r.get("category")), (r.get("name") or "").lower()))

    output: Dict[str, Any] = {
        "generated_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": "LFX PCC project-service",
        "foundation_id": FOUNDATION_ID_CNCF,
        "projects": all_records,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(output, f, sort_keys=False, allow_unicode=True)

    print(f"Wrote {len(all_records)} projects to {OUTPUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as http_err:
        # Attempt to show API error payload for easier debugging
        try:
            payload = http_err.response.json()
            print(json.dumps(payload, indent=2), file=sys.stderr)
        except Exception:
            pass
        raise



#!/usr/bin/env python3
import os
import sys
import time
from typing import Dict, Any, List, Tuple

import csv
import io
import requests

try:
    import yaml  # type: ignore
except Exception:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    print("Missing dependency: beautifulsoup4. Install with: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(2)

RAW_LANDSCAPE_URL = "https://raw.githubusercontent.com/cncf/landscape/master/landscape.yml"
CLOMONITOR_CNCF_URL = "https://raw.githubusercontent.com/cncf/clomonitor/main/data/cncf.yaml"
FOUNDATION_MAINTAINERS_CSV_URL = "https://raw.githubusercontent.com/cncf/foundation/main/project-maintainers.csv"
DEVSTATS_URL = "https://devstats.cncf.io/"
ARTWORK_README_URL = "https://raw.githubusercontent.com/cncf/artwork/main/README.md"
REPO_ROOT = os.getcwd()
PCC_YAML_PATH = os.path.join(REPO_ROOT, "pcc_projects.yaml")
AUDIT_OUTPUT_PATH = os.path.join(REPO_ROOT, "audit", "status_audit.md")


def ensure_dirs() -> None:
    os.makedirs(os.path.dirname(AUDIT_OUTPUT_PATH), exist_ok=True)


def download_landscape_yaml() -> Dict[str, Any]:
    resp = requests.get(RAW_LANDSCAPE_URL, timeout=60)
    resp.raise_for_status()
    return yaml.safe_load(resp.text)

def download_clomonitor_yaml() -> Any:
    resp = requests.get(CLOMONITOR_CNCF_URL, timeout=60)
    resp.raise_for_status()
    return yaml.safe_load(resp.text)

def download_foundation_maintainers_csv() -> List[Dict[str, str]]:
    resp = requests.get(FOUNDATION_MAINTAINERS_CSV_URL, timeout=60)
    resp.raise_for_status()
    text = resp.text
    # The CSV has a header row where first column header is empty, second is "Project"
    reader = csv.reader(io.StringIO(text))
    rows: List[Dict[str, str]] = []
    header = None
    for i, r in enumerate(reader):
        if i == 0:
            header = r
            continue
        # Map to fields by position we care about: 0=status, 1=project
        status = (r[0] if len(r) > 0 else "").strip()
        project = (r[1] if len(r) > 1 else "").strip()
        if not project:
            continue
        rows.append({"status": status, "project": project})
    return rows

def download_devstats_html() -> str:
    resp = requests.get(DEVSTATS_URL, timeout=60)
    resp.raise_for_status()
    return resp.text

def download_artwork_readme() -> str:
    resp = requests.get(ARTWORK_README_URL, timeout=60)
    resp.raise_for_status()
    return resp.text


def load_pcc_yaml() -> Dict[str, Any]:
    if not os.path.exists(PCC_YAML_PATH):
        print(f"Error: {PCC_YAML_PATH} not found. Generate it first.", file=sys.stderr)
        sys.exit(1)
    with open(PCC_YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def normalize_status(value: str) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    # Map common variants
    if v in ("graduated",):
        return "graduated"
    if v in ("incubating", "incubator"):
        return "incubating"
    if v in ("sandbox",):
        return "sandbox"
    if v in ("archived", "archive", "archieve", "retired"):
        return "archived"
    if v in ("formation - exploratory", "forming", "form", "exploratory"):
        return "forming"
    return v


def build_landscape_status_map(landscape_data: Dict[str, Any]) -> Dict[str, str]:
    name_to_status: Dict[str, str] = {}
    landscape_list: List[Any] = landscape_data.get("landscape") or []
    for cat in landscape_list:
        subcats = (cat.get("subcategories") or [])
        for sub in subcats:
            items = (sub.get("items") or [])
            for item in items:
                # Items may be nested lists/dicts; standardize on dicts with "name" and "project"
                name = (item.get("name") or "").strip()
                if not name:
                    continue
                status = normalize_status(item.get("project") or "")
                if not status:
                    # Non-CNCF or missing project status; skip
                    continue
                key = normalize_name(name)
                # Prefer first occurrence; duplicates are rare and usually identical
                if key not in name_to_status:
                    name_to_status[key] = status
    return name_to_status


def build_artwork_status_map(readme_text: str) -> Dict[str, str]:
    # Parse cncf/artwork README where projects are grouped under bullet headings.
    category_to_status = {
        "graduated projects": "graduated",
        "incubating projects": "incubating",
        "sandbox projects": "sandbox",
        "archived projects": "archived",
    }
    name_to_status: Dict[str, str] = {}
    current_status: str = ""

    def parse_bullet_text(line: str) -> str:
        # Extract text after the first '* '
        try:
            star_idx = line.index("*")
        except ValueError:
            return ""
        text = line[star_idx + 1 :].strip()
        # Handle markdown links: [Name](url)
        if text.startswith("[") and "]" in text:
            try:
                end = text.index("]")
                text = text[1:end].strip()
            except Exception:
                pass
        # Trim trailing double-space soft break markers
        text = text.split("  ")[0].strip()
        # Remove stray list markers or punctuation
        return text.strip("*-_ ").strip()

    lines = readme_text.splitlines()
    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        # Zero-indent bullets define categories
        if line.startswith("* "):
            cat = parse_bullet_text(line).lower()
            if cat in category_to_status:
                current_status = category_to_status[cat]
                continue
            else:
                # A new top-level bullet that isn't a known category ends the current section
                current_status = ""
        # Indented bullets under a current category are project names (including subprojects)
        if current_status and line.lstrip().startswith("* ") and not line.startswith("* "):
            name = parse_bullet_text(line)
            if name:
                key = normalize_name(name)
                if key and key not in name_to_status:
                    name_to_status[key] = current_status

    return name_to_status


def build_clomonitor_status_map(clomonitor_data: Any) -> Dict[str, str]:
    # clomonitor cncf.yaml is a list of project entries with fields:
    # - name (slug), display_name, maturity (graduated/incubating/sandbox), ...
    name_to_status: Dict[str, str] = {}
    if not isinstance(clomonitor_data, list):
        return name_to_status
    for entry in clomonitor_data:
        if not isinstance(entry, dict):
            continue
        display_name = (entry.get("display_name") or entry.get("name") or "").strip()
        if not display_name:
            continue
        maturity = normalize_status(entry.get("maturity") or "")
        if not maturity:
            continue
        key = normalize_name(display_name)
        if key not in name_to_status:
            name_to_status[key] = maturity
    return name_to_status


def build_foundation_status_map(entries: List[Dict[str, str]]) -> Dict[str, str]:
    name_to_status: Dict[str, str] = {}
    for e in entries:
        project = e.get("project") or ""
        status = e.get("status") or ""
        if not project or not status:
            continue
        key = normalize_name(project)
        norm_status = normalize_status(status)
        # Filter to statuses we track; skip steering/maintainers pseudo-projects if not in PCC
        if norm_status in ("graduated", "incubating", "sandbox", "archived", "forming"):
            if key not in name_to_status:
                name_to_status[key] = norm_status
    return name_to_status


def build_devstats_status_map(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    name_to_status: Dict[str, str] = {}
    valid_statuses = {"graduated", "incubating", "sandbox", "archived"}
    status_markers = {"Graduated", "Incubating", "Sandbox", "Archived"}

    # Helper: detect if a table row is a status heading row
    def row_status(tr) -> str:
        cells = tr.find_all(["th", "td"])
        for c in cells:
            text = (c.get_text() or "").strip()
            if text in status_markers:
                return normalize_status(text)
        return ""

    # Iterate over all table rows in document order; when a status row is found,
    # collect anchors from subsequent rows until the next status row.
    all_rows = soup.find_all("tr")
    i = 0
    while i < len(all_rows):
        current = all_rows[i]
        current_status = row_status(current)
        if current_status and current_status in valid_statuses:
            i += 1
            while i < len(all_rows):
                nxt = all_rows[i]
                nxt_status = row_status(nxt)
                if nxt_status and nxt_status in valid_statuses:
                    break
                # Collect project anchors in this row
                for a in nxt.find_all("a"):
                    name = (a.get_text() or "").strip()
                    if not name:
                        continue
                    key = normalize_name(name)
                    if key and key not in name_to_status:
                        name_to_status[key] = current_status
                i += 1
            continue
        i += 1

    return name_to_status


def collect_pcc_expected_statuses(pcc_data: Dict[str, Any]) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    categories: Dict[str, List[Dict[str, Any]]] = pcc_data.get("categories") or {}
    for cat_name, items in categories.items():
        norm_status = normalize_status(cat_name)
        if norm_status not in ("graduated", "incubating", "sandbox"):
            continue
        for item in items or []:
            name = item.get("name") or ""
            if name:
                pairs.append((name, norm_status))
    # Archived projects
    for item in pcc_data.get("archived_projects") or []:
        name = item.get("name") or ""
        if not name:
            continue
        pairs.append((name, "archived"))
    # Forming projects
    for item in pcc_data.get("forming_projects") or []:
        name = item.get("name") or ""
        if not name:
            continue
        pairs.append((name, "forming"))
    return pairs


def write_audit_markdown(
    combined_rows: List[Tuple[str, str, str, str, str, str, str]],
) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    lines: List[str] = []
    lines.append(f"# CNCF Project Status Audit")
    lines.append(f"Generated: {ts}")
    lines.append("")
    if not combined_rows:
        lines.append("_No mismatches found between PCC and external sources._")
    else:
        lines.append("| Project | PCC status | Landscape status | CLOMonitor status | Maintainers CSV status | DevStats status | Artwork status |")
        lines.append("|---|---|---|---|---|---|---|")
        for name, pcc_status, landscape_status, cm_status, m_status, d_status, a_status in sorted(combined_rows, key=lambda r: r[0].lower()):
            lines.append(f"| {name} | {pcc_status} | {landscape_status} | {cm_status} | {m_status} | {d_status} | {a_status} |")

    with open(AUDIT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ensure_dirs()
    pcc = load_pcc_yaml()
    landscape = download_landscape_yaml()
    clomonitor = download_clomonitor_yaml()
    maintainers_csv = download_foundation_maintainers_csv()
    devstats_html = download_devstats_html()
    artwork_readme = download_artwork_readme()
    landscape_map = build_landscape_status_map(landscape)
    clomonitor_map = build_clomonitor_status_map(clomonitor)
    maintainers_map = build_foundation_status_map(maintainers_csv)
    devstats_map = build_devstats_status_map(devstats_html)
    artwork_map = build_artwork_status_map(artwork_readme)
    expected = collect_pcc_expected_statuses(pcc)

    combined_rows: List[Tuple[str, str, str, str, str, str, str]] = []
    for name, pcc_status in expected:
        norm_pcc = normalize_status(pcc_status)
        l_status_raw = landscape_map.get(normalize_name(name))
        cm_status_raw = clomonitor_map.get(normalize_name(name))
        m_status_raw = maintainers_map.get(normalize_name(name))
        d_status_raw = devstats_map.get(normalize_name(name))
        a_status_raw = artwork_map.get(normalize_name(name))
        l_status = normalize_status(l_status_raw) if l_status_raw else ""
        cm_status = normalize_status(cm_status_raw) if cm_status_raw else ""
        m_status = normalize_status(m_status_raw) if m_status_raw else ""
        d_status = normalize_status(d_status_raw) if d_status_raw else ""
        a_status = normalize_status(a_status_raw) if a_status_raw else ""

        landscape_mismatch = bool(l_status) and (l_status != norm_pcc)
        clomonitor_mismatch = bool(cm_status) and (cm_status != norm_pcc)
        maintainers_mismatch = bool(m_status) and (m_status != norm_pcc)
        devstats_mismatch = bool(d_status) and (d_status != norm_pcc)
        artwork_mismatch = bool(a_status) and (a_status != norm_pcc)

        if landscape_mismatch or clomonitor_mismatch or maintainers_mismatch or devstats_mismatch or artwork_mismatch:
            combined_rows.append((name, norm_pcc, l_status, cm_status, m_status, d_status, a_status))

    write_audit_markdown(combined_rows)
    print(f"Wrote audit with {len(combined_rows)} mismatches to {AUDIT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()



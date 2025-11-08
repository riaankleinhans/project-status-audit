#!/usr/bin/env python3
import os
import sys
import time
from typing import Dict, Any, List, Tuple

import requests

try:
    import yaml  # type: ignore
except Exception:
    print("Missing dependency: PyYAML. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


RAW_LANDSCAPE_URL = "https://raw.githubusercontent.com/cncf/landscape/master/landscape.yml"
REPO_ROOT = os.getcwd()
PCC_YAML_PATH = os.path.join(REPO_ROOT, "pcc_projects.yaml")
AUDIT_OUTPUT_PATH = os.path.join(REPO_ROOT, "audit", "status_audit.md")


def ensure_dirs() -> None:
    os.makedirs(os.path.dirname(AUDIT_OUTPUT_PATH), exist_ok=True)


def download_landscape_yaml() -> Dict[str, Any]:
    resp = requests.get(RAW_LANDSCAPE_URL, timeout=60)
    resp.raise_for_status()
    return yaml.safe_load(resp.text)


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


def write_audit_markdown(mismatches: List[Tuple[str, str, str]]) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    lines: List[str] = []
    lines.append(f"# CNCF Project Status Audit")
    lines.append(f"Generated: {ts}")
    lines.append("")
    if not mismatches:
        lines.append("_No mismatches found between PCC and Landscape._")
    else:
        lines.append("| Project | PCC status | Landscape status |")
        lines.append("|---|---|---|")
        for name, pcc_status, landscape_status in sorted(mismatches, key=lambda r: r[0].lower()):
            lines.append(f"| {name} | {pcc_status} | {landscape_status} |")
    with open(AUDIT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    ensure_dirs()
    pcc = load_pcc_yaml()
    landscape = download_landscape_yaml()
    landscape_map = build_landscape_status_map(landscape)
    expected = collect_pcc_expected_statuses(pcc)

    mismatches: List[Tuple[str, str, str]] = []
    for name, pcc_status in expected:
        l_status = landscape_map.get(normalize_name(name))
        if not l_status:
            # Not found in landscape: skip per spec (only add when both exist and mismatch)
            continue
        if normalize_status(pcc_status) != normalize_status(l_status):
            mismatches.append((name, normalize_status(pcc_status), normalize_status(l_status)))

    write_audit_markdown(mismatches)
    print(f"Wrote audit with {len(mismatches)} mismatches to {AUDIT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()



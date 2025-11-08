# Project Status Audit
Project Status Audit

This repository generates a canonical list of CNCF project statuses from the LFX PCC API and audits that source of truth against multiple public datasets (CNCF Landscape, CLOMonitor, Foundation Maintainers CSV, and DevStats). Results are published as a unified human-readable table.

## What it does

- Fetches PCC projects from LFX and writes `pcc_projects.yaml` (source of truth)
  - Includes active CNCF projects grouped by category (`Graduated`, `Incubating`, `Sandbox`)
  - Includes `forming_projects` (status: “Formation - Exploratory”)
  - Includes `archived_projects` (anything not Active or Forming)
- Audits against external sources and writes `audit/status_audit.md`:
  - CNCF Landscape (`project:` maturity)
  - CLOMonitor (`maturity`)
  - Foundation Maintainers CSV (first column)
  - DevStats (projects grouped under page headings)
- The table includes only projects where any external source differs from PCC, with columns:
  - Project | PCC status | Landscape status | CLOMonitor status | Maintainers CSV status | DevStats status

## Files

- `scripts/fetch_pcc_projects.py`: Fetches LFX PCC and writes `pcc_projects.yaml`
- `scripts/audit_landscape_status.py`: Downloads/parses external sources and writes mismatch table
- `.github/workflows/sync-pcc-projects.yml`: Nightly/manual workflow that generates/upgrades files via PR
- `pcc_projects.yaml`: Generated, canonical PCC data (no timestamp to avoid noisy diffs)
- `audit/status_audit.md`: Generated audit results (only mismatches)

## Data sources

- Landscape: `https://raw.githubusercontent.com/cncf/landscape/master/landscape.yml`
- CLOMonitor: `https://raw.githubusercontent.com/cncf/clomonitor/main/data/cncf.yaml`
- Foundation Maintainers CSV: `https://raw.githubusercontent.com/cncf/foundation/main/project-maintainers.csv`
- DevStats: `https://devstats.cncf.io/`

## GitHub Actions (recommended)

1. Add a repo secret `LFX_TOKEN` with a valid LF PCC API token.
2. Ensure Actions permissions allow “Read and write permissions” and PR creation for the `GITHUB_TOKEN`.
3. Trigger the workflow:
   - GitHub → Actions → “Sync PCC projects YAML” → “Run workflow” (or wait for the nightly schedule)
4. Review the PR with updated `pcc_projects.yaml` and `audit/status_audit.md`.

## Run locally

Dependencies:
- Python 3.11+
- pip packages: `requests`, `pyyaml`, `beautifulsoup4`

Generate PCC YAML:

```bash
export LFX_TOKEN=your_lfx_token
python scripts/fetch_pcc_projects.py
```

Run the audits:

```bash
python scripts/audit_landscape_status.py
```

Outputs:
- `pcc_projects.yaml` at repo root
- `audit/status_audit.md` with a single table of mismatches

## Notes and assumptions

- PCC is the source of truth; we compare maturity/status labels from external sources to PCC categories:
  - Graduated, Incubating, Sandbox, Archived, Forming (Formation - Exploratory)
- TAGs are intentionally excluded from the PCC categories section.
- We do not commit the fetched landscape file to the repo; it’s downloaded in-memory during audits.
- DevStats parsing uses the page’s row headings (“Graduated”, “Incubating”, “Sandbox”, “Archived”) to derive statuses. 

## PCC projects export

This repo can generate a `pcc_projects.yaml` file listing CNCF projects sourced from the LFX PCC API.

### Setup

- Create a GitHub secret named `LFX_TOKEN` with an LF API token that has access to the PCC project-service.
- The GitHub Actions workflow `.github/workflows/sync-pcc-projects.yml` will use this secret to fetch and commit updates.

### Run locally

You can also run the generator locally:

1. Ensure Python 3.11+ is available.
2. Install dependencies: `pip install requests pyyaml`
3. Export your token and run:

```bash
export LFX_TOKEN=your_token_here
python scripts/fetch_pcc_projects.py
```

This will write `pcc_projects.yaml` at the repo root.

### Run in GitHub Actions

- Trigger manually via the "workflow_dispatch" event or wait for the scheduled run.
- The workflow commits changes to `pcc_projects.yaml` to the default branch if updates are detected.

### Notes

- Data is fetched from `project-service/v1/projects`, filtered to the CNCF foundation (ID `a0941000002wBz4AAE`), and includes both active and forming projects.
- Output structure:

```yaml
generated_at: 2025-01-01T00:00:00Z
source: LFX PCC project-service
foundation_id: a0941000002wBz4AAE
projects:
  - name: Example
    slug: example
    category: Sandbox
    status: Active
    project_logo: https://...
    repository_url: https://...
```

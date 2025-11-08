# project-status-audit
Project Status Audit

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

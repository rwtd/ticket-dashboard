# Repository Guidelines

## Project Structure & Module Organization
- `app.py` and `start_ui.py` run the Flask dashboard; analytics logic lives beside them in modules such as `enhanced_query_engine.py` and `conversation_manager.py`.
- UI assets stay in `templates/`, `widgets/`, and supporting HTML previews; shared settings live under `config/`.
- Sample data sits in `tickets/`, `chats/`, and `uploads/`; deployment and reference material live in `cloudrun/`, `scripts/`, `docs/`, and the root `Makefile`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` creates an isolated Python 3.8+ workspace.
- `pip install -r requirements.txt` installs the full stack; use `requirements.minimal.txt` for slim Docker runs.
- `python start_ui.py` serves the dashboard with conversational AI at `http://localhost:5000`.
- `python ticket_analytics.py --week 22072025` generates scheduled reports (swap `--day` or `--custom` as needed).
- `python test_agent_performance_enhancements.py` plus the companion scripts (`test_daily_tickets.py`, `test_enhanced_agent_performance_final.py`) validate agent and ticket charts and write HTML artefacts for review.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation, `snake_case` for functions, and `PascalCase` for classes such as `AgentPerformanceAnalyzer`.
- Keep docstrings concise, reserve inline comments for tricky data transforms, and centralize business logic in reusable modules rather than Flask routes.
- Match existing file patterns (`tickets/YYYY-MM-DD.csv`, lowercase-hyphen utilities) and prefer explicit type hints when touching analytics pipelines.

## Testing Guidelines
- Tests are executable scripts; run them directly with an activated venv and current CSV fixtures in `tickets/` and `chats/`.
- Refresh or mock data before asserting new metrics; note that scripts exit early when expected files are absent.
- Capture CLI output and attach generated HTML when requesting review of chart or UI changes.

## Commit & Pull Request Guidelines
- Mirror the Conventional Commit flavour already in history (`feat(analytics): …`, `fix(ui): …`) using an imperative summary and scoped prefix when helpful.
- Squash noisy commits before opening a PR and mention key modules touched plus any data requirements in the description.
- PRs should list test commands run, link the relevant issue, and include visuals (screenshots or GIFs) when altering dashboards or widgets.

## Deployment Notes
- Use `make PROJECT_ID=<gcp-project> REGION=<gcp-region> all` to build and deploy to Cloud Run, or invoke `scripts/deploy_cloud_run.sh` in automated flows.
- Keep environment variables (`WIDGETS_XFO`, `WIDGETS_FRAME_ANCESTORS`) aligned across `cloudbuild.yaml`, `Dockerfile`, and docs to prevent CSP regressions.

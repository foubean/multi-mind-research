# TODO v2: Service Deployment Roadmap

This roadmap keeps the current command-line workflow intact while adding a
service layer and a Vue single-page application. The goal is to evolve the
project from local scripts into a personal portfolio-management application
without replacing the existing LangGraph core.

## Architecture Direction

- Keep the current CLI entry points:
  - `run.py` for single-ticker analysis.
  - `run_graph.py` for multi-ticker portfolio analysis.
- Add a FastAPI backend that wraps the core workflow calls currently used by
  `run.py` and `run_graph.py`.
- Add a Vue single-page application for configuring ticker lists, starting
  workflow runs, viewing run status, and opening generated reports.
- Keep SQLite as the default local persistence layer.
- Keep HTML report generation as the primary report artifact.
- Keep paper trading limited to Alpaca Paper Trading.
- Add APScheduler later for long-running automated operation.

## Phase 1: Backend Service MVP

- [ ] Create a `backend/` package for FastAPI.
- [ ] Extract reusable workflow runner functions from `run.py`.
- [ ] Extract reusable portfolio graph runner functions from `run_graph.py`.
- [ ] Add `POST /runs/single` to start a single-ticker run.
- [ ] Add `POST /runs/graph` to start a multi-ticker graph run.
- [ ] Add `GET /runs/{run_id}` to read run metadata and status.
- [ ] Add `GET /runs` to list historical runs from SQLite.
- [ ] Add `GET /reports/{report_id}` or static report serving for generated HTML reports.
- [ ] Add `GET /snapshots/{run_id}` to list recoverable snapshots.
- [ ] Add `GET /logs/{run_id}` to read JSONL audit logs when available.
- [ ] Add backend startup checks for required config files and env files.
- [ ] Keep all secrets in `.env.openai` and `.env.alpaca`; do not expose them through API responses.

## Phase 2: Vue SPA MVP

- [ ] Create a `frontend/` Vue project.
- [ ] Add a run form for ticker list, analysis date, data provider, and market provider.
- [ ] Add a mode selector for single-ticker mode and multi-ticker graph mode.
- [ ] Add a run-history page backed by `GET /runs`.
- [ ] Add a run-detail page showing status, final decision, target weights, and links to reports.
- [ ] Add report viewer links that open generated HTML reports.
- [ ] Add snapshot/log tabs for audit and recovery inspection.
- [ ] Add a basic config view showing current non-secret runtime settings.
- [ ] Add clear UI warnings that paper trading is Alpaca Paper Trading, not live trading.

## Phase 3: Persistence and Audit Hardening

- [ ] Normalize run metadata tables for backend queries.
- [ ] Add API responses for checkpoint path, snapshot path, memory store path, and business storage path.
- [ ] Add run status transitions: `created`, `running`, `completed`, `failed`, `rejected`.
- [ ] Persist backend task errors with traceback summaries.
- [ ] Add API access to decision memory summaries.
- [ ] Add API access to `trade_outcomes`.
- [ ] Add report index records so reports can be listed without scanning the filesystem.

## Phase 4: Paper Trading Integration

- [ ] Add a backend endpoint to check Alpaca Paper account connectivity.
- [ ] Add read-only account context API: cash, equity, positions, and recent portfolio history.
- [ ] Show paper execution results in the Vue run-detail page.
- [ ] Ensure paper execution is only triggered when `[paper_trading].enable = true`.
- [ ] Add a confirmation step in the UI before submitting Alpaca Paper orders.
- [ ] Keep local simulated broker execution removed; Alpaca Paper remains the only paper execution provider.

## Phase 5: Long-Running Automation

- [ ] Add APScheduler to the backend.
- [ ] Add a scheduler configuration table or JSON config.
- [ ] Add scheduled multi-ticker graph runs.
- [ ] Add scheduled paper account mark-to-market updates.
- [ ] Add scheduled report generation and archival.
- [ ] Add scheduled decision-memory updates from realized or unrealized outcomes.
- [ ] Add future universe-maintenance jobs where Agents recommend adding or removing tickers.
- [ ] Add manual pause/resume controls for scheduled jobs.

## Phase 6: Future Production Path

- [ ] Keep SQLite for local single-user deployment.
- [ ] Add optional PostgreSQL support when concurrent jobs or multi-user access become necessary.
- [ ] Add Docker Compose for backend, frontend, and persistent volumes.
- [ ] Add structured backend logging.
- [ ] Add authentication only after the local single-user workflow is stable.
- [ ] Consider Redis/Celery or another queue only when workflow runs need robust background execution.


# WC Simulator 2026

Tournament simulator and data API for FIFA World Cup 2026 (48 teams).

This service is both:
- A standalone simulator (matches, matchdays, knockout rounds, full tournament).
- The primary data provider for WC Fantasy.

## What This Repository Contains

- FastAPI backend (Python 3.11)
- Vanilla JS SPA frontend
- Simulation engine and tournament logic
- Data ingestion scripts and seed tooling

## Stack

- Backend: FastAPI, asyncpg
- Database: PostgreSQL 16
- Frontend: Vanilla JS SPA
- Data: tournament files + EFEM-based player datasets
- Container: Docker multi-arch images

## Quick Start

```bash
make setup
make dev
```

App runs on: http://localhost:8001

## Environment Variables

- `WCS_DATABASE_URL`
- `WCS_TOURNAMENT_DIR`
- `WCS_CORS_ORIGINS`

## Core API Domains

Base path: `/api/v1`

- `/countries`, `/players`
- `/tournament/*`
- `/matches/*`
- `/simulate/*`
- `/squads/*`
- `/stats/*`
- `/health`

## Architecture Notes

- Fully async backend.
- PostgreSQL is the source of truth for runtime tournament state.
- Tournament configuration comes from `data/tournament/calendar.json` and `data/tournament/groups.json`.
- Designed for compatibility with WC Fantasy consumers.

## Project Structure

```text
wc-simulator/
├── src/
│   ├── backend/
│   │   ├── routes/
│   │   └── services/
│   └── frontend/
├── data/
├── scripts/
├── tests/
└── .github/workflows/
```

## CI/CD

- Builds and pushes `ghcr.io/jpamies/wc-simulator`.
- Updates infrastructure manifests in `k8s-homepi`.
- Flux reconciles deployment on cluster.

## Security (Public Repository)

This is a public repository. Follow these rules:
- Never commit credentials, tokens, PATs, or cluster-internal secrets.
- Keep production connection strings and runtime secrets outside git.
- Treat code defaults as local placeholders only.
- Use restrictive CORS in production environments.
- Rotate credentials if leaked and invalidate old values.

### Current Security Posture

- Runtime uses `WCS_DATABASE_URL` from environment when provided.
- `src/backend/config.py` includes a development fallback connection string.
- In production, values are injected by Kubernetes manifests in `k8s-homepi`.

Recommended hardening for public code:
- Replace sensitive fallback defaults with non-sensitive placeholders.
- Fail startup in production if `WCS_DATABASE_URL` is missing or weak.
- Restrict `WCS_CORS_ORIGINS` in production to known origins.

## Integration with WC Fantasy

WC Fantasy uses this API as source of truth for:
- Tournament calendar and matchdays
- Finished matches and player stats
- Player and country catalog data

## Related Repositories

- `wc-fanasy`: fantasy game that consumes this API.
- `k8s-homepi`: Kubernetes manifests and GitOps deployment.

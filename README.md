# WC Simulator 2026 ⚽

Simulador del Mundial de Fútbol 2026 (48 selecciones, formato FIFA). Aplicación independiente con frontend SPA y API REST que sirve como:

- **Simulador de torneo** — simula partidos individuales, fases o el torneo completo con motor xG/Poisson
- **Fuente de datos** — 244k jugadores (EFEM), 48 selecciones con convocatorias de 26 jugadores
- **API para terceros** — el [wc-fantasy](https://github.com/jpamies/wc-fantasy-draft) consume esta API para calendario, resultados y stats

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.11 + FastAPI |
| Base de datos | **PostgreSQL 16** (asyncpg) |
| Frontend | SPA vanilla JS (sin framework, sin build step) |
| Datos | EFEM API (244k jugadores, fotos CDN, atributos detallados) |
| Deploy | Docker multi-arch (amd64+arm64) → K3s (Flux CD GitOps) |
| CI/CD | GitHub Actions → GHCR → auto-update k8s-homepi → Flux reconcilia |
| Registro | `ghcr.io/jpamies/wc-simulator` |

## Inicio rápido

```bash
# Crear entorno y arrancar
make setup
make dev
# → http://localhost:8001
```

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `WCS_DATABASE_URL` | `postgresql://wcadmin:...@localhost:5432/wc_simulator` | PostgreSQL connection string |
| `WCS_TOURNAMENT_DIR` | `data/tournament` | Directorio con calendar.json y groups.json |
| `WCS_CORS_ORIGINS` | `*` | CORS origins (separados por coma) |

## Base de datos (PostgreSQL)

9 tablas:

| Tabla | Propósito |
|-------|-----------|
| `countries` | 48 selecciones (code, name, flag, confederation, group) |
| `players` | Jugadores con atributos (position, club, strength, pace/shooting/passing/dribbling/defending/physic, market_value, photo) |
| `matchdays` | Jornadas del calendario (phase, status) |
| `matches` | Partidos individuales (home/away, scores, penalties, status, is_simulated) |
| `player_match_stats` | Stats individuales por partido (goals, assists, cards, saves, rating, minutes, clean_sheet) |
| `group_standings` | Clasificación de grupos materializada (P, W, D, L, GF, GA, Pts) |
| `simulations` | Metadata de simulaciones |
| `squad_selections` | Convocatorias de 26 jugadores por selección |
| `squad_stats` | Estadísticas pre-computadas por convocatoria (avg_strength, total_value) |

Wrapper: `PgConnection` con pool asyncpg (min=2, max=10), logging de queries lentas (>100ms).

## API Endpoints

Base: `/api/v1`

### Datos (`/api/v1/`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/countries` | Lista de selecciones |
| GET | `/countries/{code}` | Detalle de selección |
| GET | `/countries/{code}/players` | Plantilla completa |
| GET | `/players` | Búsqueda de jugadores (query: country, position, search, sort, limit, offset) |
| GET | `/players/{id}` | Detalle de jugador con atributos |

### Torneo (`/api/v1/tournament/`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/tournament/overview` | Resumen del torneo (equipos, partidos, fase, grupos) |
| GET | `/tournament/calendar` | **Calendario completo** con matchdays + partidos (usado por wc-fantasy) |
| GET | `/tournament/standings` | Clasificación de grupos |

### Partidos (`/api/v1/matches/`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/matches` | Lista de partidos (query: matchday_id, country, status) |
| GET | `/matches/finished-with-stats` | **Partidos terminados con stats** (usado por wc-fantasy sync) |
| GET | `/matches/{id}` | Detalle de partido |
| PATCH | `/matches/{id}/result` | Registrar resultado real |
| POST | `/matches/{id}/stats` | Registrar stats de jugadores |
| GET | `/matches/{id}/stats` | Obtener stats de jugadores |

### Simulación (`/api/v1/simulate/`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/simulate/next-match` | Simular el siguiente partido programado |
| POST | `/simulate/matchday/{id}` | Simular todos los partidos de una jornada |
| POST | `/simulate/matches` | Simular partidos específicos o por fase |
| POST | `/simulate/group-stage` | Simular toda la fase de grupos |
| POST | `/simulate/generate-bracket` | Generar cuadro de eliminatorias (R32→Final) |
| POST | `/simulate/knockout-round/{phase}` | Simular una ronda eliminatoria |
| POST | `/simulate/full-tournament` | Simular torneo completo |
| POST | `/simulate/reset` | Borrar resultados simulados |

### Convocatorias (`/api/v1/squads/`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/squads` | Lista de todas las convocatorias |
| GET | `/squads/all-players` | Todos los jugadores convocados (1248 = 48×26) |
| GET | `/squads/{country}` | Convocatoria de una selección |
| PUT | `/squads/{country}` | Establecer convocatoria manual |
| POST | `/squads/{country}/auto` | Auto-seleccionar mejores 26 |
| POST | `/squads/auto-all` | Auto-seleccionar todas las convocatorias |

### Estadísticas (`/api/v1/stats/`)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/stats/top-scorers` | Máximos goleadores |
| GET | `/stats/top-assists` | Máximos asistentes |
| GET | `/stats/top-rated` | Mejores ratings |
| GET | `/stats/top-cards` | Más tarjetas |
| GET | `/stats/top-keepers` | Mejores porteros |
| GET | `/stats/team-stats` | Stats agregados por equipo |
| GET | `/stats/player/{id}` | Stats individuales del torneo (summary + historial de partidos) |

### Health
| Método | Ruta |
|--------|------|
| GET | `/api/v1/health` |

## Motor de simulación

El motor genera resultados realistas basados en:

- **Fuerza del equipo**: top jugadores por posición → strength compuesto
- **Expected Goals (xG)**: modelo ataque vs defensa+portero, con control de mediocampo
- **Distribución Poisson**: para samplear goles desde el xG
- **Home advantage**: +8% xG para el local
- **Stats individuales**: goles, asistencias, tarjetas, saves... distribuidos por posición y fuerza
- **Sustituciones**: timing realista alineado con goles/asistencias
- **Tarjetas**: ponderadas por contexto (equipo perdedor comete más faltas)
- **Penalties**: simulación de tanda con sudden death

### Formato del torneo (FIFA 2026)

- 48 selecciones en 12 grupos de 4
- Top 2 + 8 mejores terceros → Round of 32
- Bracket determinista FIFA: R32 → R16 → QF → SF → 3er puesto + Final

## Fuentes de datos

### Jugadores — Capa de abstracción (`PlayerDataSourceFactory`)

| Fuente | Ficheros | Descripción |
|--------|----------|-------------|
| **EFEM** (primaria) | `data/raw/efeme/*.json` | 244k jugadores, atributos detallados, fotos CDN, club logos |
| Raw (fallback) | `data/raw/players/*.json` | Formato legacy simplificado |

Los datos EFEM no están en el repo (>100MB) — se descargan via GitHub Release en `Dockerfile.seed`.

Fotos: CDN `https://d2utsopg4ciewu.cloudfront.net/{efem_id}.png`
Banderas: `https://flagcdn.com/w40/{country_code_lower}.png`

### Torneo
- `data/tournament/calendar.json` — 8 matchdays (GS1-3, R32, R16, QF, SF, FINAL), 104 partidos
- `data/tournament/groups.json` — 12 grupos de 4 selecciones

## Deploy

### Docker

| Dockerfile | Imagen | Plataformas | Propósito |
|-----------|--------|-------------|-----------|
| `Dockerfile` | `ghcr.io/jpamies/wc-simulator` | amd64 + arm64 | App principal (FastAPI + frontend + data/tournament/) |
| `Dockerfile.seed` | `ghcr.io/jpamies/wc-simulator-seed` | arm64 | Seeder DB (descarga EFEM data de GitHub Release, ejecuta import) |

### CI/CD (GitHub Actions)

1. Push a `main` → `build-image.yml` construye imagen multi-arch
2. Push a GHCR con tags `latest` + SHA del commit
3. **Auto-deploy**: clona `k8s-homepi`, actualiza `deployment.yaml` con nueva imagen, push → Flux reconcilia

### Kubernetes (k8s-homepi)

- **Deployment**: 1 réplica, 256Mi-2Gi RAM, 100m-1000m CPU
- **Service**: ClusterIP puerto **8001** (target 8000)
- **PostgreSQL**: StatefulSet separado (`postgres:16-alpine`, 2Gi PVC)
- **Seed Job**: Job manual para importar datos EFEM → PostgreSQL
- **DNS interno**: `wc-simulator.default.svc.cluster.local:8001`

## Estructura del proyecto

```
wc-simulator/
├── .github/workflows/
│   ├── build-image.yml          # CI: build + deploy app principal
│   └── build-seed.yml           # CI: build seed image (manual)
├── src/
│   ├── backend/
│   │   ├── main.py              # FastAPI app, middleware, lifespan
│   │   ├── config.py            # Env vars (WCS_ prefix)
│   │   ├── database.py          # asyncpg pool + PgConnection + schema DDL
│   │   ├── models.py            # Pydantic request/response schemas
│   │   ├── routes/
│   │   │   ├── data.py          # /countries, /players
│   │   │   ├── matches.py       # /matches CRUD + stats
│   │   │   ├── simulation.py    # /simulate endpoints
│   │   │   ├── tournament.py    # /tournament overview/calendar/standings
│   │   │   ├── squads.py        # /squads management
│   │   │   └── stats.py         # /stats leaderboards + player/{id}
│   │   └── services/
│   │       ├── data_import.py          # EFEM/Raw JSON → PostgreSQL
│   │       ├── simulation_engine.py    # Poisson xG match simulator
│   │       ├── tournament_engine.py    # Standings + FIFA bracket logic
│   │       ├── player_data_source.py   # Abstract player data interface
│   │       └── player_data_sources/
│   │           ├── efem_source.py      # EFEM API adapter
│   │           └── raw_source.py       # Legacy raw adapter
│   └── frontend/                # Vanilla JS SPA
│       ├── index.html
│       ├── css/styles.css
│       └── js/
├── data/
│   ├── tournament/              # calendar.json, groups.json
│   └── raw/                     # EFEM JSONs (no en git, descargados en seed)
├── scripts/                     # Utilidades de datos
├── Dockerfile                   # App principal
├── Dockerfile.seed              # Seeder de DB
├── Makefile                     # dev, setup, docker-build
└── requirements.txt             # fastapi, uvicorn, pydantic, asyncpg
```

## Middleware

| Middleware | Propósito |
|-----------|---------|
| CORS | Origins configurables via `WCS_CORS_ORIGINS` |
| TimingMiddleware | Header `X-Response-Time`, log de requests >200ms |
| NoCacheStaticMiddleware | No-cache para HTML, 5min cache para assets |

## Integración con wc-fantasy

El fantasy consume estos endpoints clave:
- `GET /api/v1/tournament/calendar` — Calendario completo (jornadas + partidos)
- `GET /api/v1/matches/finished-with-stats` — Resultados con stats individuales (para sync)
- `GET /api/v1/matches?matchday_id=X&status=finished` — Partidos terminados de una jornada
- `GET /api/v1/squads/all-players` — Todos los jugadores convocados (1248)
- `GET /api/v1/players/{id}` — Detalle de jugador
- `GET /api/v1/stats/player/{id}` — Stats del torneo de un jugador
- `GET /api/v1/countries` — Lista de selecciones

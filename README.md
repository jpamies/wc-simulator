# WC Simulator 2026 ⚽

Simulador del Mundial de Fútbol 2026. Aplicación independiente con frontend SPA y API REST que sirve como:

- **Simulador de torneo** — simula partidos individuales, fases o el torneo completo
- **Fuente de datos** — plantillas, calendario, resultados (reales y simulados)
- **API para terceros** — el [wc-fantasy](https://github.com/jpamies/wc-fantasy) y otras aplicaciones consumen esta API

## Stack

- **Backend**: Python 3.11 + FastAPI + SQLite (aiosqlite)
- **Frontend**: SPA vanilla JS (sin framework, sin build step)
- **Deploy**: Docker multi-arch → Kubernetes (Flux CD)

## Inicio rápido

```bash
# Crear entorno y arrancar
make setup
make dev
# → http://localhost:8001
```

## API Endpoints

Base: `/api/v1`

### Datos
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/countries` | Lista de selecciones |
| GET | `/countries/{code}` | Detalle de selección |
| GET | `/countries/{code}/players` | Plantilla completa |
| GET | `/players` | Búsqueda de jugadores (query: country, position, search, sort) |
| GET | `/players/{id}` | Detalle de jugador |

### Torneo
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/tournament/overview` | Resumen del torneo |
| GET | `/tournament/calendar` | Calendario completo con partidos |
| GET | `/tournament/standings` | Clasificación de grupos |

### Partidos
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/matches` | Lista de partidos (query: matchday_id, country, status) |
| GET | `/matches/{id}` | Detalle de partido |
| PATCH | `/matches/{id}/result` | Registrar resultado real |
| POST | `/matches/{id}/stats` | Registrar stats de jugadores |
| GET | `/matches/{id}/stats` | Obtener stats de jugadores |

### Simulación
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/simulate/matches` | Simular partidos específicos o por fase |
| POST | `/simulate/group-stage` | Simular toda la fase de grupos |
| POST | `/simulate/generate-bracket` | Generar cuadro de eliminatorias |
| POST | `/simulate/knockout-round/{phase}` | Simular ronda eliminatoria |
| POST | `/simulate/full-tournament` | Simular torneo completo |
| POST | `/simulate/reset` | Borrar resultados simulados |

### Health
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check |

## Motor de simulación

El motor genera resultados realistas basados en:

- **Fuerza del equipo**: calculada a partir del `market_value` de los jugadores (escala logarítmica → strength 30-99)
- **Expected Goals (xG)**: modelo ataque vs defensa+portero del rival
- **Distribución Poisson**: para samplear goles reales desde el xG
- **Home advantage**: +8% para el equipo local
- **Stats individuales**: goles, asistencias, tarjetas, saves... distribuidos probabilísticamente por posición y fuerza del jugador
- **Penalties en eliminatorias**: simulación de tanda de penaltis si hay empate

## Datos incluidos

- 23 selecciones con plantillas completas (fuente: Transfermarkt)
- Calendario de fase de grupos (3 jornadas)
- Bracket de eliminatorias (generado dinámicamente)
- Estructura de grupos del Mundial 2026

## Integración con wc-fantasy

El fantasy consume la API del simulador para obtener:

- **Plantillas**: `GET /countries/{code}/players` — jugadores con posición, club, valor de mercado
- **Calendario**: `GET /tournament/calendar` — jornadas y partidos
- **Resultados**: `GET /matches?status=finished` — resultados reales y simulados
- **Stats de jugadores**: `GET /matches/{id}/stats` — estadísticas individuales por partido
- **Clasificación**: `GET /tournament/standings` — tablas de grupos

## Deploy

El proyecto se despliega automáticamente en el cluster Kubernetes gestionado por Flux:

1. Push a `main` → GitHub Actions builds multi-arch Docker image
2. CI actualiza `k8s-homepi/apps/wc-simulator/deployment.yaml` con el nuevo tag
3. Flux detecta el cambio y despliega automáticamente

## Estructura

```
wc-simulator/
├── src/
│   ├── backend/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configuración (env vars)
│   │   ├── database.py       # SQLite schema + helpers
│   │   ├── models.py         # Pydantic schemas
│   │   ├── routes/
│   │   │   ├── tournament.py # Overview, calendar, standings
│   │   │   ├── data.py       # Countries, players
│   │   │   ├── matches.py    # Match CRUD + stats
│   │   │   └── simulation.py # Simulate endpoints
│   │   └── services/
│   │       ├── simulation_engine.py  # Match simulation logic
│   │       ├── tournament_engine.py  # Standings, bracket progression
│   │       └── data_import.py        # Load JSON → SQLite
│   └── frontend/
│       ├── index.html
│       ├── css/styles.css
│       └── js/
│           ├── api.js, router.js, app.js
│           └── pages/ (home, calendar, standings, teams, match, simulate)
├── data/
│   ├── tournament/    # calendar.json, groups.json
│   └── transfermarkt/ # {country}.json (23 files)
├── Dockerfile
├── Makefile
└── .github/workflows/build-image.yml
```

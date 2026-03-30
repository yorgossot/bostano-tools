# YeOrgio

A plant tracking database for my garden. It's meant to be used and managed by OpenClaw.

## The Name

ΓεΌργιο (YeOrgio) = Γιώργος (Yorgos) + γεωργία (agriculture/farming) + όργιο (orgy)

## Tech

- Python 3 (no external dependencies)
- SQLite database (`data/yeorgio.db`)
- CLI via `yeorgio.py`

## Data Directory

All state lives in `data/`:

```
data/
  yeorgio.db    # SQLite database
  photos/       # Event photos (copied here on log)
```

Photos attached via `log --photo` are copied into `data/photos/` and stored with relative paths. The original files are not modified.

## Setup

```bash
python3 init_db.py
```

This creates `data/yeorgio.db` with all tables and seeds the default locations and awning state. Safe to re-run.


## Database Schema

### `locations` — where plants live

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | Primary key |
| name | TEXT | Unique name |
| zone | TEXT | `indoor` or `outdoor` |
| below_awning | INTEGER | 1 if sheltered when awning is up |
| description | TEXT | Optional |
| created_at | TEXT | Auto-set |

Default locations:

- **Indoor:** Kitchen, Living room, Bedroom, Bathroom
- **Outdoor:** Railing, Railing below awning, Apartment wall, Apartment wall below awning, East wall, West wall

### `plants` — the plants themselves

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | Primary key |
| name | TEXT | Personal name (e.g. "Moisis", "Tirion") |
| plant_type | TEXT | Type of plant (e.g. "Cypress", "Jasmine") |
| species | TEXT | Botanical species |
| variety | TEXT | Cultivar/variety |
| location_id | INTEGER | FK to locations |
| parent_id | INTEGER | FK to plants (for cuttings/divisions) |
| source | TEXT | Free text origin ("seed", "nursery", "gift from Maria") |
| status | TEXT | `alive`, `struggling`, `dead`, `dormant`, `propagating`, `unknown` |
| date_planted | TEXT | ISO 8601 date |
| date_died | TEXT | Auto-set when status changes to dead |
| notes | TEXT | Free text |
| created_at | TEXT | Auto-set |
| updated_at | TEXT | Auto-set, bumped on update |

### `events` — care log

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | Primary key |
| plant_id | INTEGER | FK to plants |
| event_type | TEXT | See types below |
| notes | TEXT | Free text |
| created_at | TEXT | Timestamp |

Event types: `watering`, `fertilizing`, `pruning`, `harvest`, `repotting`, `pest_treatment`, `propagation`, `transplant`, `observation`, `other`

### `event_photos` — photos attached to events

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | Primary key |
| event_id | INTEGER | FK to events |
| photo_path | TEXT | File path to photo |
| created_at | TEXT | Timestamp |

Multiple photos can be attached to a single event.

### `config` — global state

Key-value store. Currently stores:

| Column | Type | Notes |
|---|---|---|
| key | TEXT | Primary key |
| value | TEXT | |
| updated_at | TEXT | Auto-set, bumped on update |

Currently stores:

| Key | Values | Notes |
|---|---|---|
| awning | `up` / `down` | Affects `--exposed` and `--sheltered` filters |

## CLI Reference

All commands: `python3 yeorgio.py <command>`

### `add` — Add a plant

```bash
yeorgio.py add "Moisis" --plant-type "Opuntia" --location "Kitchen"
yeorgio.py add "Tirion" --plant-type "Cypress" --source "cutting" --status propagating
```

| Argument | Required | Notes |
|---|---|---|
| `name` | Yes | Positional — personal name for the plant |
| `--plant-type` | No | Type of plant (e.g. "Jasmine", "Cypress") |
| `--species` | No | Botanical species |
| `--variety` | No | Cultivar |
| `--location` | No | Location name (auto-created if new, defaults to outdoor zone) |
| `--parent` | No | Parent plant ID (for cuttings) |
| `--source` | No | Free text origin |
| `--status` | No | Default: `alive` |
| `--date-planted` | No | Default: today |
| `--notes` | No | |

### `list` — List plants

```bash
yeorgio.py list                    # All non-dead plants
yeorgio.py list --indoor           # Indoor only
yeorgio.py list --outdoor          # Outdoor only
yeorgio.py list --exposed          # Outdoor, not sheltered by awning
yeorgio.py list --sheltered        # Indoor + below awning (when up)
yeorgio.py list --status propagating
yeorgio.py list --location "Kitchen"
yeorgio.py list --all              # Include dead plants
```

Output columns: `ID`, `Name`, `Plant Type`, `Species`, `Location`, `Status`, `Planted`

Dead plants are hidden by default.

### `show` — Show plant details

```bash
yeorgio.py show 1
```

Displays all fields plus the last 10 events.

### `log` — Log a care event

```bash
yeorgio.py log 1 watering --notes "Deep soak"
yeorgio.py log 3 observation --photo "/path/to/img.jpg" --photo "/path/to/img2.jpg"
yeorgio.py log 2 propagation --notes "Took 3 cuttings"
yeorgio.py log 1 watering --date "2026-03-25 09:00"
```

| Argument | Required | Notes |
|---|---|---|
| `plant_id` | Yes | Positional |
| `event_type` | Yes | Positional — see event types above |
| `--notes` | No | Free text |
| `--photo` | No | Path to photo file (repeatable) |
| `--date` | No | Override timestamp (`YYYY-MM-DD HH:MM`). Default: now |

Photos are copied into `data/photos/` as `{event_id}_{filename}`.

### `events` — View event history

```bash
yeorgio.py events                  # Last 20 events
yeorgio.py events --plant 1        # Events for plant #1
yeorgio.py events --type watering  # Only watering events
yeorgio.py events --limit 50
```

Output includes event ID and any attached photo paths.

### `edit-event` — Edit an event

```bash
yeorgio.py edit-event 1 --type propagation
yeorgio.py edit-event 1 --notes "Updated notes"
```

| Argument | Required | Notes |
|---|---|---|
| `event_id` | Yes | Positional |
| `--type` | No | New event type |
| `--notes` | No | New notes |

### `delete-event` — Delete an event

```bash
yeorgio.py delete-event 1
```

Deletes an event and its associated photos (both database records and files).

### `add-photo` — Append photos to an event

```bash
yeorgio.py add-photo 1 /path/to/img.jpg
yeorgio.py add-photo 1 img1.jpg img2.jpg  # Multiple photos
```

Photos are copied into `data/photos/` with the event ID prefix. If a file with the same name exists, a suffix is added automatically.

### `update` — Update a plant

```bash
yeorgio.py update 1 --status dead --notes "RIP"
yeorgio.py update 2 --location "Bedroom" --name "Sunny"
yeorgio.py update 3 --plant-type "Jasmine"
```

Any field can be updated. Setting status to `dead` auto-fills `date_died`.

### `locations` — Manage locations

```bash
yeorgio.py locations                          # List all with plant counts
yeorgio.py locations add "Greenhouse" --zone outdoor
```

### `awning` — Check or set awning state

```bash
yeorgio.py awning          # Check: "Awning is down"
yeorgio.py awning up       # Set to up
yeorgio.py awning down     # Set to down
```

The awning state changes the behavior of `list --exposed` and `list --sheltered`:

| Awning | `--exposed` shows | `--sheltered` shows |
|---|---|---|
| **down** | All outdoor plants | Indoor plants only |
| **up** | Outdoor plants NOT below awning | Indoor + below-awning plants |

## Propagation Workflow

```bash
# Take a cutting from an existing plant
yeorgio.py add "Pothos Baby" --plant-type "Pothos" --parent 5 --status propagating --location "Kitchen"
yeorgio.py log 6 propagation --notes "Water propagation, 3 nodes"

# Once rooted, transplant and update status
yeorgio.py log 6 transplant --notes "Roots at 2cm, moved to soil"
yeorgio.py update 6 --status alive --location "Bedroom"
```

## Daily Check

`check_actions.py` scans all living plants and flags actions needed:

- **Overdue watering** — per-type thresholds (e.g. 21 days for cacti, 14 days default)
- **Post-transplant watering** — flags plants ~4 days after transplant/repotting
- **Note reminders** — parses "in X days" or "(March 26)" patterns from event notes
- **Propagation check-ins** — weekly reminders for propagating plants

The daily check is triggered by an OpenClaw cron job which runs `check_actions.py` and delivers the result via Telegram.

---

Growing in Athens

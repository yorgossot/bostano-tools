# YeOrgio

A plant tracking database for my garden. Managed by OpenClaw.

ΓεΌργιο (YeOrgio) = Γιώργος (Yorgos) + γεωργία (agriculture/farming) + όργιο (orgy)

## Usage

```bash
cd /root/openclaw-agents/bostano/.openclaw/projects/bostano-tools/yeorgio
python3 yeorgio.py <command> [options]
```

Python 3, no external dependencies. Database: `data/yeorgio.db`. Photos: `data/photos/`.

Setup (already done, safe to re-run): `python3 init_db.py`

## Key Concepts

**Statuses:** `alive`, `struggling`, `dead`, `dormant`, `propagating`, `unknown`

**Event types:** `watering`, `fertilizing`, `pruning`, `harvest`, `repotting`, `pest_treatment`, `propagation`, `transplant`, `observation`, `other`

**Awning:** outdoor locations have a `below_awning` flag. When awning is `up`, below-awning plants count as sheltered. When `down`, all outdoor plants are exposed. This affects `list --exposed` / `--sheltered`.

**Parentage:** plants can track a parent via `--parent` (for cuttings/divisions).

## Commands

### add — Add a plant

```bash
yeorgio.py add "Moisis" --plant-type "Opuntia" --location "Kitchen"
yeorgio.py add "Tirion" --plant-type "Cypress" --source "cutting" --status propagating --parent 5
```

Options: `--plant-type`, `--species`, `--variety`, `--location` (auto-created if new), `--parent` (plant ID), `--source`, `--status`, `--date-planted`, `--notes`

### list — List plants

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

Dead plants hidden by default. Output: ID, Name, Plant Type, Species, Location, Status, Planted.

### show — Show plant details

```bash
yeorgio.py show 1
```

All fields plus last 10 events with photo paths.

### log — Log a care event

```bash
yeorgio.py log 1 watering --notes "Deep soak"
yeorgio.py log 3 observation --photo /path/to/img.jpg --photo /path/to/img2.jpg
yeorgio.py log 1 watering --date "2026-03-25 09:00"
```

Options: `--notes`, `--photo` (repeatable, copied to `data/photos/`), `--date` (override timestamp)

### events — View event history

```bash
yeorgio.py events                  # Last 20 events
yeorgio.py events --plant 1        # Events for plant #1
yeorgio.py events --type watering  # Only watering events
yeorgio.py events --limit 50
```

### edit-event / delete-event

```bash
yeorgio.py edit-event 1 --type propagation --notes "Updated"
yeorgio.py delete-event 1          # Also deletes associated photo files
```

### add-photo — Append photos to an event

```bash
yeorgio.py add-photo 1 /path/to/img.jpg
yeorgio.py add-photo 1 img1.jpg img2.jpg
```

### update — Update a plant

```bash
yeorgio.py update 1 --status dead --notes "RIP"
yeorgio.py update 2 --location "Bedroom" --name "Sunny"
```

Any field can be updated. Setting status to `dead` auto-fills `date_died`.

### locations — Manage locations

```bash
yeorgio.py locations                          # List all with plant counts
yeorgio.py locations add "Greenhouse" --zone outdoor
```

### awning — Check or set awning state

```bash
yeorgio.py awning          # Check current state
yeorgio.py awning up       # Set to up
yeorgio.py awning down     # Set to down
```

## Propagation Workflow

```bash
yeorgio.py add "Pothos Baby" --plant-type "Pothos" --parent 5 --status propagating --location "Kitchen"
yeorgio.py log 6 propagation --notes "Water propagation, 3 nodes"
# Once rooted:
yeorgio.py log 6 transplant --notes "Roots at 2cm, moved to soil"
yeorgio.py update 6 --status alive --location "Bedroom"
```

## Daily Check

`check_actions.py` scans all living plants and flags: overdue watering (per-type thresholds), post-transplant watering (~4 days after), note-based reminders ("in X days" / "(March 26)"), and weekly propagation check-ins. Triggered by OpenClaw cron, delivered via Telegram.

---

Growing in Athens

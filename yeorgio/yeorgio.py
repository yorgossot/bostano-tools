#!/usr/bin/env python3
"""YeOrgio plant tracker CLI.

All commands operate on yeorgio.db in the same directory as this script.
Run `python3 init_db.py` first to create the database.
"""

import argparse
import shutil
import sqlite3
import os
import sys
from datetime import date, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "yeorgio.db")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")

STATUSES = ["alive", "struggling", "dead", "dormant", "propagating", "unknown"]

EVENT_TYPES = [
    "watering",
    "fertilizing",
    "pruning",
    "harvest",
    "repotting",
    "pest_treatment",
    "propagation",
    "transplant",
    "observation",
    "other",
]


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_db():
    """Return a connection with FK enforcement and Row factory."""
    if not os.path.exists(DB_PATH):
        print("Database not found. Run: python3 init_db.py")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def print_table(headers, rows):
    """Print rows as an aligned text table. Shows "No results." if empty."""
    if not rows:
        print("No results.")
        return
    col_widths = [len(h) for h in headers]
    str_rows = []
    for row in rows:
        str_row = [str(v) if v is not None else "--" for v in row]
        str_rows.append(str_row)
        for i, v in enumerate(str_row):
            col_widths[i] = max(col_widths[i], len(v))
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in col_widths]))
    for row in str_rows:
        print(fmt.format(*row))


def get_or_create_location(conn, name):
    """Look up a location by name (case-insensitive). Create it if missing."""
    row = conn.execute(
        "SELECT id FROM locations WHERE LOWER(name) = LOWER(?)", (name,)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO locations (name, zone) VALUES (?, 'outdoor')", (name,)
    )
    conn.commit()
    return cur.lastrowid


def get_awning_up(conn):
    """Return True if the awning is currently up."""
    row = conn.execute("SELECT value FROM config WHERE key = 'awning'").fetchone()
    return row and row["value"] == "up"


# ── Commands ──────────────────────────────────────────────────────────────────


def cmd_add(args):
    """Add a new plant to the database."""
    conn = get_db()
    location_id = None
    if args.location:
        location_id = get_or_create_location(conn, args.location)
    date_planted = args.date_planted or date.today().isoformat()
    cur = conn.execute(
        """INSERT INTO plants
               (name, plant_type, species, variety, location_id,
                parent_id, source, status, date_planted, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            args.name,
            args.plant_type,
            args.species,
            args.variety,
            location_id,
            args.parent,
            args.source,
            args.status,
            date_planted,
            args.notes,
        ),
    )
    conn.commit()
    print(f"Added plant #{cur.lastrowid}: {args.name}")
    conn.close()


def cmd_list(args):
    """List plants with optional filters.

    By default, dead plants are hidden. Use --all to include them.
    --exposed and --sheltered are awning-aware: they check the current awning
    state from the config table to determine which outdoor plants are covered.
    """
    conn = get_db()
    query = """
        SELECT p.id, p.name, p.plant_type, p.species, l.name AS location, p.status, p.date_planted
        FROM plants p
        LEFT JOIN locations l ON p.location_id = l.id
    """
    conditions = []
    params = []

    # Status filter (dead hidden by default)
    if not args.all:
        if args.status:
            conditions.append("p.status = ?")
            params.append(args.status)
        else:
            conditions.append("p.status != 'dead'")
    elif args.status:
        conditions.append("p.status = ?")
        params.append(args.status)

    # Location name filter
    if args.location:
        conditions.append("LOWER(l.name) = LOWER(?)")
        params.append(args.location)

    # Zone filters
    if args.indoor:
        conditions.append("l.zone = 'indoor'")
    elif args.outdoor:
        conditions.append("l.zone = 'outdoor'")

    # Awning-aware filters
    if args.exposed:
        if get_awning_up(conn):
            conditions.append("l.zone = 'outdoor' AND l.below_awning = 0")
        else:
            # Awning down: all outdoor plants are exposed
            conditions.append("l.zone = 'outdoor'")
    elif args.sheltered:
        if get_awning_up(conn):
            conditions.append("(l.zone = 'indoor' OR l.below_awning = 1)")
        else:
            # Awning down: only indoor plants are sheltered
            conditions.append("l.zone = 'indoor'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY p.id"

    rows = conn.execute(query, params).fetchall()
    print_table(
        ["ID", "Name", "Plant Type", "Species", "Location", "Status", "Planted"],
        [
            (
                r["id"],
                r["name"],
                r["plant_type"],
                r["species"],
                r["location"],
                r["status"],
                r["date_planted"],
            )
            for r in rows
        ],
    )
    conn.close()


def cmd_show(args):
    """Show full details for a single plant, including recent events."""
    conn = get_db()
    plant = conn.execute(
        """SELECT p.*, l.name AS location_name, parent.name AS parent_name
           FROM plants p
           LEFT JOIN locations l ON p.location_id = l.id
           LEFT JOIN plants parent ON p.parent_id = parent.id
           WHERE p.id = ?""",
        (args.plant_id,),
    ).fetchone()
    if not plant:
        print(f"Plant #{args.plant_id} not found.")
        sys.exit(1)

    parent_display = (
        f"{plant['parent_name']} (#{plant['parent_id']})"
        if plant["parent_id"]
        else "--"
    )
    print(f"Plant #{plant['id']}: {plant['name']}")
    for label, val in [
        ("Plant type", plant["plant_type"]),
        ("Species", plant["species"]),
        ("Variety", plant["variety"]),
        ("Location", plant["location_name"]),
        ("Parent", parent_display),
        ("Source", plant["source"]),
        ("Status", plant["status"]),
        ("Date planted", plant["date_planted"]),
        ("Date died", plant["date_died"]),
        ("Notes", plant["notes"]),
    ]:
        print(f"  {label + ':':<16}{val or '--'}")

    events = conn.execute(
        "SELECT * FROM events WHERE plant_id = ? ORDER BY created_at DESC LIMIT 10",
        (args.plant_id,),
    ).fetchall()
    if events:
        print("\nRecent events:")
        for e in events:
            ts = e["created_at"][:16] if e["created_at"] else "--"
            notes = e["notes"] or ""
            print(f"  {ts}  {e['event_type']:<16}{notes}")
            photos = conn.execute(
                "SELECT photo_path FROM event_photos WHERE event_id = ?",
                (e["id"],),
            ).fetchall()
            for p in photos:
                print(f"                              photo: {p['photo_path']}")
    conn.close()


def cmd_log(args):
    """Log a care event for a plant."""
    conn = get_db()
    plant = conn.execute(
        "SELECT id, name FROM plants WHERE id = ?", (args.plant_id,)
    ).fetchone()
    if not plant:
        print(f"Plant #{args.plant_id} not found.")
        sys.exit(1)
    ts = args.date or datetime.now().strftime("%Y-%m-%d %H:%M")
    cur = conn.execute(
        "INSERT INTO events (plant_id, event_type, notes, created_at) VALUES (?, ?, ?, ?)",
        (args.plant_id, args.event_type, args.notes, ts),
    )
    event_id = cur.lastrowid
    if args.photo:
        os.makedirs(PHOTOS_DIR, exist_ok=True)
        for path in args.photo:
            filename = f"{event_id}_{os.path.basename(path)}"
            dest = os.path.join(PHOTOS_DIR, filename)
            shutil.copy2(path, dest)
            rel_path = os.path.join("data", "photos", filename)
            conn.execute(
                "INSERT INTO event_photos (event_id, photo_path) VALUES (?, ?)",
                (event_id, rel_path),
            )
    conn.commit()
    print(f"Logged {args.event_type} for {plant['name']} (event #{event_id})")
    conn.close()


def cmd_edit_event(args):
    """Edit an existing event (type and/or notes)."""
    conn = get_db()
    event = conn.execute(
        "SELECT * FROM events WHERE id = ?", (args.event_id,)
    ).fetchone()
    if not event:
        print(f"Event #{args.event_id} not found.")
        sys.exit(1)

    fields = {}
    if args.type is not None:
        fields["event_type"] = args.type
    if args.notes is not None:
        fields["notes"] = args.notes

    if not fields:
        print("Nothing to update.")
        return

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE events SET {set_clause} WHERE id = ?",
        list(fields.values()) + [args.event_id],
    )
    conn.commit()
    print(f"Updated event #{args.event_id}")
    conn.close()


def cmd_delete_event(args):
    """Delete an event and its associated photos."""
    conn = get_db()
    event = conn.execute(
        """SELECT e.id, p.name AS plant_name, e.event_type
           FROM events e
           JOIN plants p ON e.plant_id = p.id
           WHERE e.id = ?""",
        (args.event_id,),
    ).fetchone()
    if not event:
        print(f"Event #{args.event_id} not found.")
        sys.exit(1)

    # Get photo paths before deleting (so we can delete files)
    photos = conn.execute(
        "SELECT photo_path FROM event_photos WHERE event_id = ?",
        (args.event_id,),
    ).fetchall()

    # Delete from database (FK cascade should handle event_photos, but be explicit)
    conn.execute("DELETE FROM event_photos WHERE event_id = ?", (args.event_id,))
    conn.execute("DELETE FROM events WHERE id = ?", (args.event_id,))
    conn.commit()

    # Delete photo files from disk
    deleted_files = 0
    for p in photos:
        photo_path = os.path.join(SCRIPT_DIR, p["photo_path"])
        if os.path.exists(photo_path):
            os.remove(photo_path)
            deleted_files += 1

    print(
        f"Deleted event #{args.event_id} ({event['event_type']} for {event['plant_name']})"
    )
    if deleted_files:
        print(f"  Removed {deleted_files} photo file(s)")
    conn.close()


def cmd_add_photo(args):
    """Append photos to an existing event."""
    conn = get_db()
    event = conn.execute(
        """SELECT e.id, p.name AS plant_name
           FROM events e
           JOIN plants p ON e.plant_id = p.id
           WHERE e.id = ?""",
        (args.event_id,),
    ).fetchone()
    if not event:
        print(f"Event #{args.event_id} not found.")
        sys.exit(1)

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    added = 0
    for path in args.photo:
        if not os.path.exists(path):
            print(f"Photo not found: {path}")
            continue
        filename = f"{args.event_id}_{os.path.basename(path)}"
        dest = os.path.join(PHOTOS_DIR, filename)
        # Avoid overwriting: add suffix if file exists
        base, ext = os.path.splitext(filename)
        suffix = 1
        while os.path.exists(dest):
            filename = f"{base}_{suffix}{ext}"
            dest = os.path.join(PHOTOS_DIR, filename)
            suffix += 1
        shutil.copy2(path, dest)
        rel_path = os.path.join("data", "photos", filename)
        conn.execute(
            "INSERT INTO event_photos (event_id, photo_path, created_at) VALUES (?, ?, datetime('now'))",
            (args.event_id, rel_path),
        )
        added += 1
    conn.commit()
    print(f"Added {added} photo(s) to event #{args.event_id} ({event['plant_name']})")
    conn.close()


def cmd_events(args):
    """View event history across all plants, with optional filters."""
    conn = get_db()
    query = """
        SELECT e.id, e.created_at, p.name AS plant, e.event_type, e.notes
        FROM events e
        JOIN plants p ON e.plant_id = p.id
    """
    conditions = []
    params = []
    if args.plant:
        conditions.append("e.plant_id = ?")
        params.append(args.plant)
    if args.type:
        conditions.append("e.event_type = ?")
        params.append(args.type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY e.created_at DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(query, params).fetchall()
    print_table(
        ["ID", "Date", "Plant", "Type", "Notes"],
        [
            (
                r["id"],
                r["created_at"][:16] if r["created_at"] else "--",
                r["plant"],
                r["event_type"],
                r["notes"],
            )
            for r in rows
        ],
    )

    # Show photos for each event
    for r in rows:
        photos = conn.execute(
            "SELECT photo_path FROM event_photos WHERE event_id = ? ORDER BY created_at",
            (r["id"],),
        ).fetchall()
        for p in photos:
            print(f"      Event #{r['id']} photo: {p['photo_path']}")

    conn.close()


def cmd_update(args):
    """Update one or more fields on an existing plant.

    Auto-sets date_died when status changes to 'dead'.
    Always bumps updated_at.
    """
    conn = get_db()
    plant = conn.execute(
        "SELECT * FROM plants WHERE id = ?", (args.plant_id,)
    ).fetchone()
    if not plant:
        print(f"Plant #{args.plant_id} not found.")
        sys.exit(1)

    fields = {}
    if args.name is not None:
        fields["name"] = args.name
    if args.plant_type is not None:
        fields["plant_type"] = args.plant_type
    if args.species is not None:
        fields["species"] = args.species
    if args.variety is not None:
        fields["variety"] = args.variety
    if args.parent is not None:
        fields["parent_id"] = args.parent
    if args.source is not None:
        fields["source"] = args.source
    if args.status is not None:
        fields["status"] = args.status
        if args.status == "dead" and not plant["date_died"]:
            fields["date_died"] = date.today().isoformat()
    if args.date_planted is not None:
        fields["date_planted"] = args.date_planted
    if args.notes is not None:
        fields["notes"] = args.notes
    if args.location is not None:
        fields["location_id"] = get_or_create_location(conn, args.location)

    if not fields:
        print("Nothing to update.")
        return

    fields["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(
        f"UPDATE plants SET {set_clause} WHERE id = ?",
        list(fields.values()) + [args.plant_id],
    )
    conn.commit()
    print(f"Updated plant #{args.plant_id}")
    conn.close()


def cmd_locations(args):
    """List all locations (with plant counts), or add a new one."""
    conn = get_db()
    if args.loc_command == "add":
        name = args.loc_name
        zone = args.zone or "outdoor"
        try:
            conn.execute(
                "INSERT INTO locations (name, zone) VALUES (?, ?)", (name, zone)
            )
            conn.commit()
            print(f"Added location: {name} ({zone})")
        except sqlite3.IntegrityError:
            print(f"Location '{name}' already exists.")
    else:
        rows = conn.execute("""
            SELECT l.id, l.name, l.zone, COUNT(p.id) AS plants
            FROM locations l
            LEFT JOIN plants p ON p.location_id = l.id AND p.status != 'dead'
            GROUP BY l.id
            ORDER BY l.zone, l.name
        """).fetchall()
        print_table(
            ["ID", "Location", "Zone", "Plants"],
            [(r["id"], r["name"], r["zone"], r["plants"]) for r in rows],
        )
    conn.close()


def cmd_awning(args):
    """Check or set the awning state (up/down).

    The awning state affects --exposed and --sheltered filters on `list`.
    When up, "below awning" locations are considered sheltered.
    When down, all outdoor locations are exposed.
    """
    conn = get_db()
    if args.state:
        conn.execute(
            """INSERT INTO config (key, value, updated_at)
               VALUES ('awning', ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')""",
            (args.state, args.state),
        )
        conn.commit()
        print(f"Awning is now {args.state}")
    else:
        row = conn.execute("SELECT value FROM config WHERE key = 'awning'").fetchone()
        print(f"Awning is {row['value'] if row else 'unknown'}")
    conn.close()


# ── Argument parsing ──────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="YeOrgio plant tracker")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Add a plant")
    p_add.add_argument("name", help="Personal name for the plant")
    p_add.add_argument("--plant-type", help="Type of plant (e.g. 'Jasmine', 'Cypress')")
    p_add.add_argument("--species", help="Botanical species")
    p_add.add_argument("--variety", help="Variety or cultivar")
    p_add.add_argument("--location", help="Location name (auto-created if new)")
    p_add.add_argument(
        "--parent", type=int, help="Parent plant ID (for cuttings/divisions)"
    )
    p_add.add_argument("--source", help="Free-text origin (e.g. 'seed', 'nursery')")
    p_add.add_argument("--status", choices=STATUSES, default="alive")
    p_add.add_argument("--date-planted", help="YYYY-MM-DD (default: today)")
    p_add.add_argument("--notes")

    # list
    p_list = sub.add_parser("list", help="List plants")
    p_list.add_argument("--status", choices=STATUSES, help="Filter by status")
    p_list.add_argument("--location", help="Filter by location name")
    p_list.add_argument("--indoor", action="store_true", help="Indoor plants only")
    p_list.add_argument("--outdoor", action="store_true", help="Outdoor plants only")
    p_list.add_argument(
        "--exposed", action="store_true", help="Outdoor plants not sheltered by awning"
    )
    p_list.add_argument(
        "--sheltered",
        action="store_true",
        help="Indoor + below-awning plants (when awning is up)",
    )
    p_list.add_argument("--all", action="store_true", help="Include dead plants")

    # show
    p_show = sub.add_parser("show", help="Show plant details + recent events")
    p_show.add_argument("plant_id", type=int)

    # log
    p_log = sub.add_parser("log", help="Log a care event")
    p_log.add_argument("plant_id", type=int)
    p_log.add_argument("event_type", choices=EVENT_TYPES)
    p_log.add_argument("--notes")
    p_log.add_argument(
        "--photo", action="append", help="Path to photo file (repeatable)"
    )
    p_log.add_argument("--date", help="Override timestamp (YYYY-MM-DD HH:MM)")

    # events
    p_events = sub.add_parser("events", help="View event history")
    p_events.add_argument("--plant", type=int, help="Filter by plant ID")
    p_events.add_argument("--type", choices=EVENT_TYPES, help="Filter by type")
    p_events.add_argument("--limit", type=int, default=20)

    # edit-event
    p_edit_event = sub.add_parser("edit-event", help="Edit an event")
    p_edit_event.add_argument("event_id", type=int)
    p_edit_event.add_argument("--type", choices=EVENT_TYPES, help="New event type")
    p_edit_event.add_argument("--notes", help="New notes")

    # delete-event
    p_delete_event = sub.add_parser("delete-event", help="Delete an event")
    p_delete_event.add_argument("event_id", type=int)

    # add-photo
    p_add_photo = sub.add_parser("add-photo", help="Append photos to an event")
    p_add_photo.add_argument("event_id", type=int)
    p_add_photo.add_argument("photo", nargs="+", help="Path to photo file(s)")

    # update
    p_update = sub.add_parser("update", help="Update a plant")
    p_update.add_argument("plant_id", type=int)
    p_update.add_argument("--name", help="Personal name")
    p_update.add_argument(
        "--plant-type", help="Type of plant (e.g. 'Jasmine', 'Cypress')"
    )
    p_update.add_argument("--species")
    p_update.add_argument("--variety")
    p_update.add_argument("--location")
    p_update.add_argument("--parent", type=int, help="Parent plant ID")
    p_update.add_argument("--source")
    p_update.add_argument("--status", choices=STATUSES)
    p_update.add_argument("--date-planted")
    p_update.add_argument("--notes")

    # locations
    p_loc = sub.add_parser("locations", help="List or add locations")
    loc_sub = p_loc.add_subparsers(dest="loc_command")
    p_loc_add = loc_sub.add_parser("add", help="Add a location")
    p_loc_add.add_argument("loc_name", help="Location name")
    p_loc_add.add_argument("--zone", choices=["indoor", "outdoor"], default="outdoor")

    # awning
    p_awning = sub.add_parser("awning", help="Check or set awning state")
    p_awning.add_argument(
        "state", nargs="?", choices=["up", "down"], help="Omit to check current state"
    )

    args = parser.parse_args()
    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "show": cmd_show,
        "log": cmd_log,
        "events": cmd_events,
        "edit-event": cmd_edit_event,
        "delete-event": cmd_delete_event,
        "add-photo": cmd_add_photo,
        "update": cmd_update,
        "locations": cmd_locations,
        "awning": cmd_awning,
    }
    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

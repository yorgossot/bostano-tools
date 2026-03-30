#!/usr/bin/env python3
"""Initialize the YeOrgio database.

Creates yeorgio.db in the same directory as this script with five tables:
locations, plants, config, events, event_photos. Seeds default locations and awning state.

Safe to re-run — uses IF NOT EXISTS and INSERT OR IGNORE throughout.
"""

import sqlite3
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "yeorgio.db")


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # ── Locations ─────────────────────────────────────────────────────────
    # Each location belongs to a zone (indoor/outdoor) and may be sheltered
    # by the retractable awning.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            zone TEXT NOT NULL DEFAULT 'outdoor'
                CHECK(zone IN ('indoor', 'outdoor')),
            below_awning INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Plants ────────────────────────────────────────────────────────────
    # parent_id links cuttings/divisions back to the mother plant.
    # source is free text for non-plant origins ("seed", "nursery", etc.).
    # name = personal name (e.g. "Moisis", "Tirion")
    # plant_type = type of plant (e.g. "Cypress", "Jasmine")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            plant_type TEXT,
            species TEXT,
            variety TEXT,
            location_id INTEGER REFERENCES locations(id),
            parent_id INTEGER REFERENCES plants(id),
            source TEXT,
            status TEXT NOT NULL DEFAULT 'alive'
                CHECK(status IN ('alive', 'struggling', 'dead',
                                 'dormant', 'propagating', 'unknown')),
            date_planted TEXT,
            date_died TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Config ────────────────────────────────────────────────────────────
    # Key-value store for global state (e.g. awning up/down).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Events ────────────────────────────────────────────────────────────
    # Care log entries tied to a plant. Photos are stored in event_photos.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL REFERENCES plants(id),
            event_type TEXT NOT NULL CHECK(event_type IN (
                'watering', 'fertilizing', 'pruning', 'harvest',
                'repotting', 'pest_treatment', 'propagation', 'transplant',
                'observation', 'other'
            )),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Event photos ───────────────────────────────────────────────────────
    # Allows multiple photos per event.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(id),
            photo_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Seed locations ────────────────────────────────────────────────────
    default_locations = [
        # (name, zone, below_awning)
        ("Kitchen", "indoor", False),
        ("Living room", "indoor", False),
        ("Bedroom", "indoor", False),
        ("Bathroom", "indoor", False),
        ("Railing", "outdoor", False),
        ("Railing below awning", "outdoor", True),
        ("Apartment wall", "outdoor", False),
        ("Apartment wall below awning", "outdoor", True),
        ("East wall", "outdoor", False),
        ("West wall", "outdoor", False),
    ]
    for name, zone, below_awning in default_locations:
        cur.execute(
            "INSERT OR IGNORE INTO locations (name, zone, below_awning) VALUES (?, ?, ?)",
            (name, zone, int(below_awning)),
        )

    # ── Seed config ───────────────────────────────────────────────────────
    cur.execute(
        "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
        ("awning", "down"),
    )

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()

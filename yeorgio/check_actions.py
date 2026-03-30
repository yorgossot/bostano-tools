#!/usr/bin/env python3
"""
Daily action checker for YeOrgio.
Checks plants and events, returns any actionable items.
"""

import sqlite3
import re
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "yeorgio.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_all_plants(conn):
    """Get all non-dead plants."""
    cursor = conn.execute("""
        SELECT id, name, plant_type, status, location_id
        FROM plants
        WHERE status != 'dead'
    """)
    return cursor.fetchall()


def get_events_for_plant(conn, plant_id):
    """Get all events for a plant, ordered by date."""
    cursor = conn.execute(
        """
        SELECT event_type, notes, created_at
        FROM events
        WHERE plant_id = ?
        ORDER BY created_at DESC
    """,
        (plant_id,),
    )
    return cursor.fetchall()


def parse_date(date_str):
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        # Try date-only format
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except:
            return None


def extract_reminder_from_notes(notes):
    """Extract reminder dates from event notes.

    Looks for patterns like:
    - "Water in 4 days (March 26)"
    - "March 26" as explicit date
    - "in X days" patterns
    """
    if not notes:
        return None

    reminders = []

    # Look for explicit dates in parentheses like "(March 26)" or "(26 March)"
    month_names = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    # Pattern: (Month DD) or (DD Month)
    date_pattern = r"\((\d{1,2})\s+(\w+)\)|\((\w+)\s+(\d{1,2})\)"
    for match in re.finditer(date_pattern, notes, re.IGNORECASE):
        if match.group(1) and match.group(2):  # (DD Month)
            day = int(match.group(1))
            month_str = match.group(2).lower()
        else:  # (Month DD)
            month_str = match.group(3).lower()
            day = int(match.group(4))

        if month_str in month_names:
            month = month_names[month_str]
            year = datetime.now().year
            try:
                reminder_date = datetime(year, month, day)
                # If date is in the past by more than a year, assume next year
                if reminder_date < datetime.now() - timedelta(days=180):
                    reminder_date = datetime(year + 1, month, day)
                reminders.append(reminder_date)
            except ValueError:
                pass

    # Look for "in X days" pattern relative to event date
    in_days_pattern = r"in\s+(\d+)\s+days?"
    for match in re.finditer(in_days_pattern, notes, re.IGNORECASE):
        days = int(match.group(1))
        # This would need the event date to calculate - handled separately
        reminders.append(("in_days", days))

    return reminders if reminders else None


# Watering thresholds by plant type (days)
# If not watered in this many days, flag as needing attention
WATERING_THRESHOLDS = {
    "Opuntia": 21,  # Cactus - very drought tolerant
    "Aloe": 14,  # Succulent - drought tolerant
    "Olive tree": 21,  # Drought tolerant
    "Olive": 21,  # Drought tolerant
    "default": 14,  # Default: 2 weeks
}


def get_watering_threshold(plant_type):
    return WATERING_THRESHOLDS.get(plant_type, WATERING_THRESHOLDS["default"])


def check_plant_actions(conn, plant_id, plant_name, plant_type, status, today):
    """Check if a plant needs any action.

    Returns list of action items.
    """
    actions = []
    events = get_events_for_plant(conn, plant_id)

    if not events:
        return actions

    # Check 1: Overdue watering (only for alive plants, not propagating/dormant)
    if status == "alive":
        last_watering = None
        for event in events:
            if event[0] == "watering":
                last_watering = parse_date(event[2])
                break

        threshold = get_watering_threshold(plant_type)
        if last_watering:
            days_since = (today - last_watering).days
            if days_since >= threshold:
                actions.append(
                    {
                        "plant": plant_name,
                        "type": "watering",
                        "message": f"{plant_name} ({plant_type}) not watered in {days_since} days",
                    }
                )
        else:
            # Never watered - check if planted more than threshold ago
            for event in events:
                if event[0] in ("observation", "transplant", "repotting"):
                    first_event = parse_date(event[2])
                    if first_event:
                        days_since = (today - first_event).days
                        if days_since >= threshold:
                            actions.append(
                                {
                                    "plant": plant_name,
                                    "type": "watering",
                                    "message": f"{plant_name} ({plant_type}) never watered ({days_since} days tracked)",
                                }
                            )
                    break

    # Check 2: Post-transplant watering (4 days after transplant/repotting)
    for event in events:
        event_type, notes, created_at = event
        event_date = parse_date(created_at)

        if event_type in ("transplant", "repotting") and event_date:
            days_since = (today - event_date).days
            if 3 <= days_since <= 5:  # Around 4 days
                # Check if already watered since
                watered_since = any(
                    e[0] == "watering"
                    and parse_date(e[2])
                    and parse_date(e[2]) > event_date
                    for e in events
                )
                if not watered_since:
                    actions.append(
                        {
                            "plant": plant_name,
                            "type": "watering",
                            "message": f"{plant_name} ({plant_type}) was transplanted {days_since} days ago - time to water",
                        }
                    )
            break  # Only check most recent transplant

    # Check 3: Explicit reminders in notes
    for event in events:
        event_type, notes, created_at = event
        event_date = parse_date(created_at)
        reminders = extract_reminder_from_notes(notes)

        if reminders:
            for reminder in reminders:
                if isinstance(reminder, tuple) and reminder[0] == "in_days":
                    # "in X days" relative to event
                    days = reminder[1]
                    reminder_date = (
                        event_date + timedelta(days=days) if event_date else None
                    )
                    if reminder_date and reminder_date.date() == today.date():
                        actions.append(
                            {
                                "plant": plant_name,
                                "type": "reminder",
                                "message": f"{plant_name} ({plant_type}): reminder from {event_type} - today!",
                            }
                        )
                elif isinstance(reminder, datetime):
                    # Explicit date
                    if reminder.date() == today.date():
                        actions.append(
                            {
                                "plant": plant_name,
                                "type": "reminder",
                                "message": f"{plant_name} ({plant_type}): reminder from {event_type} - today!",
                            }
                        )

    # Check 4: Propagating plants - check if it's been a while
    if status == "propagating":
        for event in events:
            if event[0] == "propagation":
                event_date = parse_date(event[2])
                if event_date:
                    days_since = (today - event_date).days
                    if days_since >= 7 and days_since % 7 == 0:  # Weekly check
                        actions.append(
                            {
                                "plant": plant_name,
                                "type": "propagation",
                                "message": f"{plant_name} ({plant_type}): propagating for {days_since} days - check progress",
                            }
                        )
                break

    return actions


def main():
    today = datetime.now()
    conn = get_connection()

    plants = get_all_plants(conn)
    all_actions = []

    for plant_id, name, plant_type, status, location_id in plants:
        actions = check_plant_actions(conn, plant_id, name, plant_type, status, today)
        all_actions.extend(actions)

    conn.close()

    if all_actions:
        print(f"🌱 {len(all_actions)} action(s) needed:\n")
        for action in all_actions:
            print(f"• {action['message']}")
    else:
        print("✅ All plants are happy - no actions needed today.")


if __name__ == "__main__":
    main()

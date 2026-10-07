from datetime import UTC, datetime
from sqlite3 import IntegrityError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from .run_store import QueueFull, enqueue, snapshot


def next_due(config, after=None):
    try:
        zone = ZoneInfo(config["timezone"])
    except ZoneInfoNotFoundError as error:
        raise ValueError("Unknown IANA time zone.") from error
    if not croniter.is_valid(config["cron"]) or len(config["cron"].split()) != 5:
        raise ValueError("Use a five-field cron expression.")
    base = (after or datetime.now(UTC)).astimezone(zone)
    return croniter(config["cron"], base).get_next(datetime).astimezone(UTC).isoformat()


def tick(db):
    for config in db.list_catalog("schedules"):
        if not config["enabled"]:
            continue
        with db.connect() as connection:
            state = connection.execute(
                "SELECT next_due FROM schedule_state WHERE id=?", (config["id"],)
            ).fetchone()
        if not state:
            with db.connect() as connection:
                connection.execute(
                    "INSERT INTO schedule_state VALUES(?,?)", (config["id"], next_due(config))
                )
            continue
        due = state["next_due"]
        if datetime.fromisoformat(due) > datetime.now(UTC):
            continue
        try:
            enqueue(db, snapshot(db, config["plan_id"]), schedule_key=f"{config['id']}:{due}")
        except IntegrityError:
            # Recovery after enqueue committed but next_due did not: never enqueue twice.
            pass
        except QueueFull:
            db.audit(None, "schedule.queue_full", config["id"])
            continue
        except (KeyError, ValueError):
            db.audit(None, "schedule.configuration_error", config["id"])
        # Missed intervals are collapsed to one run, not replayed as a burst.
        with db.connect() as connection:
            connection.execute(
                "UPDATE schedule_state SET next_due=? WHERE id=?", (next_due(config), config["id"])
            )

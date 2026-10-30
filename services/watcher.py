"""
MediTrack Watcher Service
Handles background polling, time parsing/normalization, and desktop notifications.
"""

import re
import threading
from datetime import datetime, date
from win11toast import notify as win_notify
from config import ALERT_WINDOW_MINUTES, WATCHER_INTERVAL_SECONDS, logger
from database import get_medications_for_user, get_schedules_for_medication

def _parse_single_time(time_str):
    if not time_str or not isinstance(time_str, str):
        return None

    cleaned = time_str.strip().upper()
    cleaned = re.sub(r"\s*:\s*", ":", cleaned)
    cleaned = cleaned.strip("()")

    formats = [
        "%H:%M",       # 14:30 or 08:30
        "%I:%M %p",    # 02:30 PM
        "%I:%M%p",     # 02:30PM
        "%I %p",       # 2 PM
        "%I%p",        # 2PM
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%H:%M")
        except ValueError:
            continue

    parts = cleaned.split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"

    return None

def normalize_time(time_str):
    """
    Parses one or multiple comma/semicolon-separated time strings.
    Returns sorted, unique 'HH:MM, HH:MM, ...' string, or None if invalid.
    """
    if not time_str or not isinstance(time_str, str):
        return None

    raw_items = re.split(r"[,;]+", time_str.strip())
    normalized_list = []
    for item in raw_items:
        clean_item = item.strip()
        if not clean_item:
            continue
        parsed = _parse_single_time(clean_item)
        if not parsed:
            return None
        normalized_list.append(parsed)

    if not normalized_list:
        return None

    # Deduplicate and sort chronologically
    sorted_unique = sorted(list(set(normalized_list)))
    return ", ".join(sorted_unique)

def should_alert(scheduled_time_str, current_dt=None, window_minutes=ALERT_WINDOW_MINUTES):
    """
    Returns True if current_dt is at or after scheduled_time today,
    but within window_minutes after the scheduled time.
    E.g., if scheduled for 08:00, triggers between 08:00 and 08:15.
    Prevents missed alerts if machine was busy, sleeping, or locked during the exact minute.
    """
    if not scheduled_time_str:
        return False
    if current_dt is None:
        current_dt = datetime.now()

    parts = scheduled_time_str.split(":")
    if len(parts) != 2:
        return False
    try:
        sched_h, sched_m = int(parts[0]), int(parts[1])
    except ValueError:
        return False

    sched_dt = current_dt.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
    diff_seconds = (current_dt - sched_dt).total_seconds()
    return 0 <= diff_seconds <= (window_minutes * 60)

def send_alert(med, scheduled_time=None):
    """
    Fires a native Windows 11 toast notification for a due medication.
    med tuple: (id, user_id, name, dosage, time, frequency, created_at, recipient_id, recipient_name, ...)
    """
    time_display = f" at {scheduled_time}" if scheduled_time else ""
    recipient_name = med[8] if len(med) > 8 else None

    if recipient_name:
        title = f"MediTrack · {recipient_name}"
        message_text = f"Time to give {med[2]} ({med[3]}) to {recipient_name}{time_display}"
    else:
        title = "MediTrack Reminder"
        message_text = f"Time to take {med[2]} ({med[3]}){time_display}"

    logger.info(f"[send_alert] {message_text}")
    try:
        win_notify(title, message_text, scenario="reminder")
    except Exception as e:
        logger.error(f"[send_alert] Failed to deliver toast notification: {e}")

def start_watcher(current_user, stop_event=None, already_notified=None):
    """
    Launches the background daemon thread that polls medication schedules.
    Returns (thread, stop_event).
    """
    if stop_event is None:
        stop_event = threading.Event()
    if already_notified is None:
        already_notified = set()

    def watcher_loop():
        while not stop_event.is_set():
            if current_user.get("id") is not None:
                now_dt = datetime.now()
                now_str = now_dt.strftime("%H:%M")
                today_str = date.today().isoformat()
                meds = get_medications_for_user(current_user["id"])
                logger.debug(f"[watcher] now={now_str}, checking {len(meds)} medication(s)...")

                for med in meds:
                    med_id = med[0]
                    # Query individual schedule slots from normalized table
                    schedules = get_schedules_for_medication(med_id)
                    slot_times = [s[2] for s in schedules] if schedules else []
                    if not slot_times and med[4]:
                        slot_times = [t.strip() for t in re.split(r"[,;]+", med[4]) if t.strip()]

                    for t in slot_times:
                        normalized_t = _parse_single_time(t) or t
                        key = (today_str, med_id, normalized_t)
                        if should_alert(normalized_t, current_dt=now_dt, window_minutes=ALERT_WINDOW_MINUTES) and key not in already_notified:
                            send_alert(med, scheduled_time=normalized_t)
                            already_notified.add(key)
            stop_event.wait(WATCHER_INTERVAL_SECONDS)

    watcher_thread = threading.Thread(target=watcher_loop, daemon=True, name="WatcherDaemon")
    watcher_thread.start()
    return watcher_thread, stop_event

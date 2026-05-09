import logging
import re
from datetime import datetime, timedelta
from database import get_db_connection
from state_service import reset_user_state
from human_responses import (
    get_booking_confirmation,
    get_reschedule_confirmation,
    get_cancellation_confirmation,
    get_no_active_booking_response,
    get_cancellation_error_response,
    get_missing_info_message,
    get_slot_unavailable_message,
    get_no_alternatives_message,
    get_booking_error_response,
    get_invalid_datetime_response,
    get_past_datetime_response,
    get_outside_working_hours_response,
    get_booking_already_exists_response,
)

logger = logging.getLogger(__name__)


def _normalize_booking_request(chat_id: str, state: dict | None) -> tuple[str, dict]:
    """Return a safe chat_id and booking payload with defaults."""
    normalized_chat_id = str(chat_id).strip() if chat_id is not None else ""
    safe_state = dict(state or {})
    safe_state["chat_id"] = normalized_chat_id
    safe_state["service"] = (safe_state.get("service") or "").strip()
    safe_state["full_name"] = (safe_state.get("full_name") or "Клиент").strip()
    safe_state["phone"] = (safe_state.get("phone") or "").strip()
    safe_state["preferred_datetime"] = (safe_state.get("preferred_datetime") or "").strip()
    return normalized_chat_id, safe_state


def _format_working_days(settings: dict) -> str:
    day_map = {
        "0": "пн",
        "1": "вт",
        "2": "ср",
        "3": "чт",
        "4": "пт",
        "5": "сб",
        "6": "вс",
    }
    days = [
        day_map.get(item.strip())
        for item in str(settings.get("working_days") or "0,1,2,3,4,5").split(",")
        if day_map.get(item.strip())
    ]
    return ", ".join(days) if days else "по рабочим дням"


def _format_alternative_lines(slots: list[str]) -> str:
    return "\n".join(
        [f"{index + 1}. {format_slot_for_display(slot)}" for index, slot in enumerate(slots)]
    )


def _get_slot_issue_message(appointment_at: str, clinic_id: int, duration: int, exclude_booking_id: int | None = None) -> tuple[str, str, list[str]]:
    """Build a human-friendly message for unavailable or invalid slots."""
    if not is_within_working_hours(appointment_at, clinic_id, duration):
        settings = get_clinic_settings(clinic_id)
        appointment_dt = _parse_slot_datetime(appointment_at)
        alternatives = find_alternative_slots(
            appointment_at,
            clinic_id,
            duration_minutes=duration,
            exclude_booking_id=exclude_booking_id,
        )

        if appointment_dt and not _is_working_day(appointment_dt, clinic_id):
            weekday_names = ["понедельник", "вторник", "среду", "четверг", "пятницу", "субботу", "воскресенье"]
            schedule_text = (
                f"{_format_working_days(settings)}, "
                f"с {settings.get('work_start', '10:00')} до {settings.get('work_end', '19:00')}"
            )
            message = (
                f"В {weekday_names[appointment_dt.weekday()]} клиника не работает. "
                f"Мы принимаем: {schedule_text}."
            )
            if alternatives:
                message += f"\n\nМогу предложить:\n\n{_format_alternative_lines(alternatives)}"
            else:
                message += "\n\nВыберите, пожалуйста, другой рабочий день."
            return message, "outside_working_days", alternatives

        message = get_outside_working_hours_response(
            settings.get("work_start", "10:00"),
            settings.get("work_end", "19:00"),
        )
        if alternatives:
            message += f"\n\nБлижайшие варианты:\n\n{_format_alternative_lines(alternatives)}"
        return message, "outside_hours", alternatives

    alternatives = find_alternative_slots(
        appointment_at,
        clinic_id,
        duration_minutes=duration,
        exclude_booking_id=exclude_booking_id,
    )
    if alternatives:
        alt_lines = _format_alternative_lines(alternatives)
        return get_slot_unavailable_message(alt_lines), "slot_taken", alternatives

    return get_no_alternatives_message(), "slot_taken", []


def get_slot_issue_message(appointment_at: str, clinic_id: int, duration: int, exclude_booking_id: int | None = None) -> tuple[str, str, list[str]]:
    return _get_slot_issue_message(appointment_at, clinic_id, duration, exclude_booking_id)

_VALID_CONVERSATION_STATUSES = {"active", "waiting_operator", "booked", "closed", "completed", "lost", "cancelled", "no_show"}
_VALID_MESSAGE_SENDER_TYPES = {"user", "bot", "operator"}


def _normalize_crm_text(value, drop_placeholders: bool = False) -> str:
    text = str(value).strip() if value is not None else ""
    if drop_placeholders and text.lower() in {"клиент", "client", "none", "null", "—", "-"}:
        return ""
    return text


def _is_valid_crm_chat_id(chat_id: str) -> bool:
    normalized = _normalize_crm_text(chat_id)
    if not normalized:
        return False
    if normalized.startswith("-"):
        normalized = normalized[1:]
    return normalized.isdigit()


def _has_meaningful_conversation_payload(
    full_name: str = None,
    phone: str = None,
    last_user_message: str = None,
    last_bot_reply: str = None,
    has_booking: int = None,
    needs_operator: int = None,
) -> bool:
    return any([
        _normalize_crm_text(full_name, drop_placeholders=True),
        _normalize_crm_text(phone),
        _normalize_crm_text(last_user_message),
        _normalize_crm_text(last_bot_reply),
        bool(has_booking),
        bool(needs_operator),
    ])


# ========================
# Clinic Management Functions
# ========================

def get_default_clinic() -> int:
    """
    Get the default clinic ID.
    
    Returns:
        Clinic ID of the default clinic (1), creating it if necessary
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM clinics WHERE id = 1")
    row = cursor.fetchone()
    
    if not row:
        cursor.execute("""
        INSERT INTO clinics (id, name, timezone, work_start, work_end, slot_step_minutes, is_active)
        VALUES (1, 'Клиника', 'Asia/Almaty', '10:00', '19:00', 30, 1)
        """)
        conn.commit()
    
    conn.close()
    return 1


def assign_user_to_clinic(chat_id: str, clinic_id: int = None) -> int:
    """
    Assign a user to the default clinic.
    
    If user is not in user_state table yet, this will ensure they're assigned.
    For now, all users are assigned to clinic 1.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Clinic ID (currently always 1)
    """
    if clinic_id is None:
        clinic_id = get_default_clinic()
    try:
        clinic_id = int(clinic_id or get_default_clinic())
    except (TypeError, ValueError):
        clinic_id = get_default_clinic()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Update clinic_id in user_state if user exists
    cursor.execute("""
    UPDATE user_state
    SET clinic_id = ?
    WHERE chat_id = ?
    """, (clinic_id, chat_id))
    
    conn.commit()
    conn.close()
    
    return clinic_id


def get_clinic_by_chat_id(chat_id: str) -> int:
    """
    Get the clinic ID for a specific user.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Clinic ID, or default clinic (1) if user not found
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT clinic_id FROM user_state
    WHERE chat_id = ?
    """, (chat_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return row[0]
    
    # If user not found, assign them to default clinic
    return assign_user_to_clinic(chat_id)


def get_active_booking_by_chat_id(chat_id: str):
    """
    Get the nearest active booking for a specific user.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Dictionary with booking data, or None if no active booking exists
    """
    normalized_chat_id = str(chat_id).strip() if chat_id is not None else ""
    if not normalized_chat_id:
        return None

    clinic_id = get_clinic_by_chat_id(normalized_chat_id)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at, clinic_id
    FROM bookings
    WHERE chat_id = ? AND clinic_id = ? AND status = 'active'
    ORDER BY CASE WHEN appointment_at >= ? THEN 0 ELSE 1 END, appointment_at ASC, created_at DESC
    LIMIT 1
    """, (normalized_chat_id, clinic_id, now_str))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "chat_id": row[1],
        "service": row[2],
        "full_name": row[3],
        "phone": row[4],
        "appointment_at": row[5],
        "status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "clinic_id": row[9],
    }


def get_service_by_id(service_id: int, clinic_id: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, clinic_id, name, price, duration_minutes, is_active
        FROM services
        WHERE id = ? AND clinic_id = ?
        LIMIT 1
    """, (service_id, clinic_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "clinic_id": row[1],
        "name": row[2],
        "price": row[3],
        "duration_minutes": row[4],
        "is_active": row[5],
    }
    
    

def get_active_booking_by_appointment(appointment_at: str, clinic_id: int = 1):
    """
    Check if there's an active booking at the given appointment time.

    Args:
        appointment_at: Appointment datetime string
        clinic_id: Clinic ID (default 1)

    Returns:
        Dictionary with booking data, or None if slot is available
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at, clinic_id
    FROM bookings
    WHERE appointment_at = ? AND clinic_id = ? AND status = 'active'
    LIMIT 1
    """, (appointment_at, clinic_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "chat_id": row[1],
        "service": row[2],
        "full_name": row[3],
        "phone": row[4],
        "appointment_at": row[5],
        "status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
        "clinic_id": row[9],
    }


def get_all_occupied_slots(date_str: str, clinic_id: int = 1) -> set:
    """
    Get all occupied slots for a specific date in a clinic.

    Args:
        date_str: Date in format "YYYY-MM-DD"
        clinic_id: Clinic ID (default 1)

    Returns:
        Set of occupied times as "HH:MM" strings
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT appointment_at FROM bookings
    WHERE status = 'active' AND clinic_id = ? AND appointment_at LIKE ?
    """, (clinic_id, date_str + "%"))

    occupied_times = set()
    for row in cursor.fetchall():
        appointment = row[0]  # format: "2026-03-26 14:00"
        if " " in appointment:
            time_part = appointment.split(" ")[1]  # extract "14:00"
            occupied_times.add(time_part)

    conn.close()
    return occupied_times


def find_alternative_slots(preferred_datetime: str, clinic_id: int = 1, limit: int = 3) -> list:
    """
    Find alternative available slots near the requested datetime in a clinic.

    Args:
        preferred_datetime: Requested datetime in format "YYYY-MM-DD HH:MM"
        clinic_id: Clinic ID (default 1)
        limit: Maximum number of alternatives to return (default 3)

    Returns:
        List of available slot strings like ["2026-03-26 15:00", "2026-03-26 16:00", "2026-03-27 09:00"]
    """
    if not preferred_datetime or " " not in preferred_datetime:
        return []

    try:
        requested_time = datetime.fromisoformat(preferred_datetime)
    except (ValueError, TypeError):
        return []

    working_hours_start = 9   # 09:00
    working_hours_end = 18    # 18:00
    slot_duration_minutes = 60

    available_slots = []

    # Generate candidate slots: same day first (later times), then earlier times, then next day
    current_date = requested_time.date()
    current_time = requested_time.time()
    current_hour = current_time.hour

    # Phase 1: Same day, later times (from requested hour to 18:00)
    for check_date in [current_date]:
        occupied = get_all_occupied_slots(check_date.isoformat(), clinic_id)
        
        for hour in range(current_hour, working_hours_end + 1):
            if len(available_slots) >= limit:
                break
                
            slot_time = f"{hour:02d}:00"
            slot_datetime = f"{check_date.isoformat()} {slot_time}"
            
            if slot_time not in occupied:
                available_slots.append(slot_datetime)
        
        if len(available_slots) >= limit:
            break

    # Phase 2: Same day, earlier times (from 09:00 to requested hour)
    if len(available_slots) < limit:
        occupied = get_all_occupied_slots(current_date.isoformat(), clinic_id)
        
        for hour in range(working_hours_start, current_hour):
            if len(available_slots) >= limit:
                break
                
            slot_time = f"{hour:02d}:00"
            slot_datetime = f"{current_date.isoformat()} {slot_time}"
            
            if slot_time not in occupied:
                available_slots.append(slot_datetime)

    # Phase 3: Next day (if still not enough)
    if len(available_slots) < limit:
        next_date = current_date + timedelta(days=1)
        occupied = get_all_occupied_slots(next_date.isoformat(), clinic_id)
        
        for hour in range(working_hours_start, working_hours_end + 1):
            if len(available_slots) >= limit:
                break
                
            slot_time = f"{hour:02d}:00"
            slot_datetime = f"{next_date.isoformat()} {slot_time}"
            
            if slot_time not in occupied:
                available_slots.append(slot_datetime)

    return available_slots[:limit]


def format_slot_for_display(slot_datetime: str) -> str:
    """
    Format a slot datetime for user display in Russian.

    Args:
        slot_datetime: Datetime in format "YYYY-MM-DD HH:MM"

    Returns:
        Formatted string like "26 марта в 15:00"
    """
    if not slot_datetime or " " not in slot_datetime:
        return slot_datetime

    try:
        dt = datetime.fromisoformat(slot_datetime)
    except (ValueError, TypeError):
        return slot_datetime

    months = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]

    date_part = dt.date()
    time_part = dt.time()

    month_name = months[date_part.month - 1]
    formatted = f"{date_part.day} {month_name} в {time_part.strftime('%H:%M')}"

    return formatted


def format_phone_for_display(phone: str) -> str:
    """
    Format phone number for display.
    
    Keeps phone as-is but ensures safe display.
    For Kazakh numbers, can display as-is (simple safe approach).

    Args:
        phone: Phone number string
        
    Returns:
        Formatted phone number or original if cannot parse
    """
    if not phone:
        return "—"
    
    phone = phone.strip()
    if not phone:
        return "—"
    
    return phone


def _parse_slot_datetime(appointment_at: str):
    if not appointment_at:
        return None
    try:
        return datetime.fromisoformat(appointment_at)
    except (ValueError, TypeError):
        return None


def _normalize_working_days(value) -> str:
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = str(value or "").split(",")

    days = sorted({
        int(str(item).strip())
        for item in raw_items
        if str(item).strip().isdigit() and 0 <= int(str(item).strip()) <= 6
    })
    if not days:
        days = [0, 1, 2, 3, 4, 5]
    return ",".join(str(day) for day in days)


def _is_working_day(target_dt: datetime, clinic_id: int = 1) -> bool:
    settings = get_clinic_settings(clinic_id)
    working_days = {
        int(item)
        for item in str(settings.get("working_days") or "0,1,2,3,4,5").split(",")
        if item.strip().isdigit()
    }
    return target_dt.weekday() in working_days


def get_service_duration(clinic_id: int, service_name: str) -> int:
    if not service_name:
        return 60
    service = get_service_by_name(service_name, clinic_id)
    if not service:
        return 60
    return service.get('duration_minutes', 60) or 60


def is_within_working_hours(appointment_at: str, clinic_id: int = 1, duration_minutes: int = 60) -> bool:
    """
    Check if an appointment time is within clinic working hours and the full duration fits.

    Args:
        appointment_at: Appointment time in "YYYY-MM-DD HH:MM" format
        clinic_id: Clinic ID
        duration_minutes: Service duration

    Returns:
        True if appointment fits within working hours
    """
    try:
        appointment_start = datetime.fromisoformat(appointment_at)
        appointment_end = appointment_start + timedelta(minutes=duration_minutes)
    except (ValueError, TypeError):
        return False

    if not _is_working_day(appointment_start, clinic_id):
        return False

    settings = get_clinic_settings(clinic_id)

    work_start = settings.get('work_start', '10:00')
    work_end = settings.get('work_end', '19:00')

    try:
        work_start_hour = int(work_start.split(':')[0])
        work_start_minute = int(work_start.split(':')[1]) if ':' in work_start else 0
        work_end_hour = int(work_end.split(':')[0])
        work_end_minute = int(work_end.split(':')[1]) if ':' in work_end else 0
    except (ValueError, IndexError):
        work_start_hour, work_start_minute = 10, 0
        work_end_hour, work_end_minute = 19, 0

    # Create datetime objects for the appointment day
    day_start = appointment_start.replace(hour=work_start_hour, minute=work_start_minute, second=0, microsecond=0)
    day_end = appointment_start.replace(hour=work_end_hour, minute=work_end_minute, second=0, microsecond=0)

    return appointment_start >= day_start and appointment_end <= day_end


def check_slot_available(appointment_at: str, clinic_id: int = 1, duration_minutes: int = 60, exclude_booking_id: int = None) -> bool:
    """
    Check if a booking slot is available in a clinic with duration awareness and working hours validation.

    Returns True only if:
    1. The appointment is within working hours
    2. No active booking overlaps the requested time window

    Args:
        appointment_at: Requested appointment time in "YYYY-MM-DD HH:MM" format
        clinic_id: Clinic ID
        duration_minutes: Service duration in minutes
        exclude_booking_id: Booking ID to exclude from conflict check (for rescheduling)

    Returns:
        True if slot is available
    """
    # First check if appointment is within working hours
    if not is_within_working_hours(appointment_at, clinic_id, duration_minutes):
        return False

    requested_start = _parse_slot_datetime(appointment_at)
    if not requested_start:
        return False

    requested_end = requested_start + timedelta(minutes=duration_minutes)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, appointment_at, duration_minutes
    FROM bookings
    WHERE clinic_id = ? AND status = 'active'
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        existing_id, existing_appointment, existing_duration = row

        if exclude_booking_id and existing_id == exclude_booking_id:
            continue

        existing_start = _parse_slot_datetime(existing_appointment)
        if not existing_start:
            continue

        existing_duration = existing_duration or 60
        existing_end = existing_start + timedelta(minutes=existing_duration)

        if requested_start < existing_end and existing_start < requested_end:
            return False

    return True


def find_alternative_slots(preferred_datetime: str, clinic_id: int = 1, duration_minutes: int = 60, limit: int = 3, exclude_booking_id: int = None) -> list:
    """
    Find next available slots near the requested datetime.

    Returns up to 'limit' alternative slots, prioritizing:
    1. Same day, later times
    2. Next day, from start of working hours
    3. Following days if needed

    Args:
        preferred_datetime: Preferred datetime in "YYYY-MM-DD HH:MM" format
        clinic_id: Clinic ID
        duration_minutes: Service duration in minutes
        limit: Maximum number of alternatives to return
        exclude_booking_id: Booking ID to ignore when suggesting alternatives during reschedule

    Returns:
        List of available slots as "YYYY-MM-DD HH:MM" strings
    """
    preferred_start = _parse_slot_datetime(preferred_datetime)
    if not preferred_start:
        return []

    settings = get_clinic_settings(clinic_id)
    slot_step = settings.get('slot_step_minutes', 30)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, appointment_at, duration_minutes FROM bookings
    WHERE clinic_id = ? AND status = 'active'
    """, (clinic_id,))
    bookings_rows = cursor.fetchall()
    conn.close()

    occupied_intervals = []
    for row in bookings_rows:
        booking_id, appointment_value, duration_value = row
        if exclude_booking_id and booking_id == exclude_booking_id:
            continue
        ex_start = _parse_slot_datetime(appointment_value)
        if not ex_start:
            continue
        ex_duration = duration_value or 60
        occupied_intervals.append((ex_start, ex_start + timedelta(minutes=ex_duration)))

    def is_slot_free(candidate_start):
        """Check if a time slot is free considering duration."""
        candidate_end = candidate_start + timedelta(minutes=duration_minutes)
        for ex_start, ex_end in occupied_intervals:
            if candidate_start < ex_end and ex_start < candidate_end:
                return False
        return True

    def is_within_working_hours(candidate):
        """Check if candidate time is within clinic working hours."""
        if not _is_working_day(candidate, clinic_id):
            return False

        work_start = settings.get('work_start', '10:00')
        work_end = settings.get('work_end', '19:00')

        try:
            start_hour = int(work_start.split(':')[0])
            start_minute = int(work_start.split(':')[1]) if ':' in work_start else 0
            end_hour = int(work_end.split(':')[0])
            end_minute = int(work_end.split(':')[1]) if ':' in work_end else 0
        except (ValueError, IndexError):
            start_hour, start_minute = 10, 0
            end_hour, end_minute = 19, 0

        day_start = candidate.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        day_end = candidate.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        return candidate >= day_start and candidate + timedelta(minutes=duration_minutes) <= day_end

    suggestions = []
    current_date = preferred_start.date()

    # Strategy 1: Same day, later times (after preferred time)
    candidate = preferred_start.replace(second=0, microsecond=0)
    # Align to next slot boundary
    minutes_past_hour = candidate.minute % slot_step
    if minutes_past_hour > 0:
        candidate += timedelta(minutes=slot_step - minutes_past_hour)

    # Look for slots later in the same day
    while len(suggestions) < limit:
        if is_within_working_hours(candidate) and is_slot_free(candidate):
            suggestions.append(candidate.strftime('%Y-%m-%d %H:%M'))

        candidate += timedelta(minutes=slot_step)

        # If we've gone past working hours, break
        if not is_within_working_hours(candidate):
            break

    # Strategy 2: Next day(s) from start of working hours
    days_ahead = 1
    max_days_ahead = 7  # Don't look too far ahead

    while len(suggestions) < limit and days_ahead <= max_days_ahead:
        next_date = current_date + timedelta(days=days_ahead)
        day_slots = generate_available_slots(next_date.strftime('%Y-%m-%d'), clinic_id, duration_minutes)

        # Take the first few slots from the next day
        slots_needed = limit - len(suggestions)
        suggestions.extend(day_slots[:slots_needed])

        days_ahead += 1

    return suggestions[:limit]


def generate_available_slots(date_str: str, clinic_id: int = 1, duration_minutes: int = 60) -> list:
    """
    Generate all available slots for a specific date in a clinic.

    Returns a list of available time slots in "YYYY-MM-DD HH:MM" format,
    already filtered for conflicts, working hours, and ensuring the full
    service duration fits within working hours.

    Args:
        date_str: Date in format "YYYY-MM-DD"
        clinic_id: Clinic ID (default 1)
        duration_minutes: Service duration to check for (default 60)

    Returns:
        List of available slots as strings
    """
    try:
        # Parse the date
        date_obj = datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        return []

    if not _is_working_day(datetime.combine(date_obj, datetime.min.time()), clinic_id):
        return []

    # Get clinic settings
    settings = get_clinic_settings(clinic_id)
    work_start = settings.get('work_start', '10:00')
    work_end = settings.get('work_end', '19:00')
    slot_step = settings.get('slot_step_minutes', 30)

    # Parse working hours
    try:
        work_start_hour = int(work_start.split(':')[0])
        work_start_minute = int(work_start.split(':')[1]) if ':' in work_start else 0
        work_end_hour = int(work_end.split(':')[0])
        work_end_minute = int(work_end.split(':')[1]) if ':' in work_end else 0
    except (ValueError, IndexError):
        work_start_hour, work_start_minute = 10, 0
        work_end_hour, work_end_minute = 19, 0

    # Create datetime objects for the day
    day_start = datetime.combine(date_obj, datetime.min.time().replace(hour=work_start_hour, minute=work_start_minute))
    day_end = datetime.combine(date_obj, datetime.min.time().replace(hour=work_end_hour, minute=work_end_minute))

    # Get all existing bookings for this date
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT appointment_at, duration_minutes
    FROM bookings
    WHERE clinic_id = ? AND status = 'active' AND appointment_at LIKE ?
    """, (clinic_id, date_str + "%"))

    existing_bookings = cursor.fetchall()
    conn.close()

    # Create list of occupied time intervals
    occupied_intervals = []
    for booking in existing_bookings:
        appointment_str, duration = booking
        try:
            booking_start = datetime.fromisoformat(appointment_str)
            booking_end = booking_start + timedelta(minutes=duration or 60)
            occupied_intervals.append((booking_start, booking_end))
        except (ValueError, TypeError):
            continue

    # Generate all possible slots
    available_slots = []
    current_time = day_start

    while current_time < day_end:
        # Check if this entire service duration fits within working hours
        service_end = current_time + timedelta(minutes=duration_minutes)
        if service_end > day_end:
            current_time += timedelta(minutes=slot_step)
            continue

        # Check if this service conflicts with any existing booking
        is_available = True

        for booking_start, booking_end in occupied_intervals:
            # Check for any overlap
            if current_time < booking_end and booking_start < service_end:
                is_available = False
                break

        if is_available:
            available_slots.append(current_time.strftime('%Y-%m-%d %H:%M'))

        # Move to next slot
        current_time += timedelta(minutes=slot_step)

    return available_slots


def create_booking(chat_id: str, state: dict) -> dict:
    """Create a new booking for a user and return a structured result."""
    normalized_chat_id, safe_state = _normalize_booking_request(chat_id, state)
    logger.info(
        "BOOKING_CREATE start chat_id=%s service=%s time=%s",
        normalized_chat_id or "?",
        safe_state.get("service", ""),
        safe_state.get("preferred_datetime", ""),
    )

    if not normalized_chat_id:
        logger.warning("BOOKING_CREATE invalid chat_id=%r", chat_id)
        return {
            "success": False,
            "booking_id": None,
            "message": get_booking_error_response(),
            "error": "invalid_chat_id",
        }

    clinic_id = get_clinic_by_chat_id(normalized_chat_id)
    appointment_at = safe_state.get("preferred_datetime", "")
    service_name = safe_state.get("service", "")
    duration = get_service_duration(clinic_id, service_name)

    existing_booking = get_active_booking_by_chat_id(normalized_chat_id)
    if existing_booking:
        appointment_text = format_slot_for_display(existing_booking.get("appointment_at", ""))
        service_text = existing_booking.get("service", "визит")
        logger.info(
            "BOOKING_CREATE blocked duplicate chat_id=%s booking_id=%s",
            normalized_chat_id,
            existing_booking.get("id"),
        )
        return {
            "success": False,
            "booking_id": existing_booking.get("id"),
            "message": get_booking_already_exists_response(appointment_text, service_text),
            "error": "active_booking_exists",
            "status": "active_booking_exists",
        }

    missing_fields = []
    if not service_name:
        missing_fields.append("услугу")
    if not safe_state.get("phone"):
        missing_fields.append("номер телефона")
    if not appointment_at:
        missing_fields.append("дату и время")

    if missing_fields:
        logger.warning("BOOKING_CREATE missing_fields chat_id=%s fields=%s", normalized_chat_id, missing_fields)
        return {
            "success": False,
            "booking_id": None,
            "message": get_missing_info_message(", ".join(missing_fields)),
            "error": "missing_fields",
        }

    appointment_dt = _parse_slot_datetime(appointment_at)
    if not appointment_dt:
        return {
            "success": False,
            "booking_id": None,
            "message": get_invalid_datetime_response(),
            "error": "invalid_datetime",
        }

    if appointment_dt <= datetime.now():
        return {
            "success": False,
            "booking_id": None,
            "message": get_past_datetime_response(),
            "error": "past_datetime",
        }

    if not check_slot_available(appointment_at, clinic_id, duration_minutes=duration):
        message, error_code, alternatives = _get_slot_issue_message(appointment_at, clinic_id, duration)
        logger.info(
            "BOOKING_CREATE prevented chat_id=%s time=%s reason=%s",
            normalized_chat_id,
            appointment_at,
            error_code,
        )
        return {
            "success": False,
            "booking_id": None,
            "message": message,
            "error": error_code,
            "status": error_code,
            "alternative_slots": alternatives,
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        doctor = find_available_doctor(
            clinic_id,
            safe_state.get("service", ""),
            appointment_at,
            duration
        )

        doctor_id = doctor["id"] if doctor else None

        cursor.execute("""
        INSERT INTO bookings (
            clinic_id, chat_id, service, full_name, phone, appointment_at,
            duration_minutes, doctor_id, status, created_at, updated_at, source_channel
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
        """, (
            clinic_id,
            normalized_chat_id,
            safe_state.get("service", ""),
            safe_state.get("full_name", "Клиент"),
            safe_state.get("phone", ""),
            appointment_at,
            duration,
            doctor_id,
            now,
            now,
            safe_state.get("source_channel", ""),
        ))

        booking_id = cursor.lastrowid
        conn.commit()
        conn.close()

        mark_conversation_booked(clinic_id, normalized_chat_id)
        message = get_booking_confirmation(format_slot_for_display(appointment_at), service_name)

        logger.info(
            "BOOKING_CREATE success booking_id=%s chat_id=%s time=%s",
            booking_id,
            normalized_chat_id,
            appointment_at,
        )
        return {
            "success": True,
            "booking_id": booking_id,
            "message": message,
            "error": None,
        }
    except Exception:
        logger.exception("BOOKING_CREATE failed chat_id=%s", normalized_chat_id)
        return {
            "success": False,
            "booking_id": None,
            "message": get_booking_error_response(),
            "error": "create_failed",
        }


def update_booking(booking_id: int, state: dict) -> dict:
    """Update an existing active booking and return a structured result."""
    _, safe_state = _normalize_booking_request(state.get("chat_id"), state)
    logger.info(
        "BOOKING_RESCHEDULE start booking_id=%s chat_id=%s time=%s",
        booking_id,
        safe_state.get("chat_id", ""),
        safe_state.get("preferred_datetime", ""),
    )

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT clinic_id, chat_id, status FROM bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        logger.warning("BOOKING_RESCHEDULE missing booking_id=%s", booking_id)
        return {
            "success": False,
            "booking_id": booking_id,
            "message": get_no_active_booking_response(),
            "error": "booking_not_found",
        }

    clinic_id, booking_chat_id, booking_status = row
    normalized_chat_id = safe_state.get("chat_id") or str(booking_chat_id or "").strip()
    appointment_at = safe_state.get("preferred_datetime", "")
    service_name = safe_state.get("service") or ""
    duration = get_service_duration(clinic_id, service_name)

    if booking_status != "active":
        return {
            "success": False,
            "booking_id": booking_id,
            "message": get_no_active_booking_response(),
            "error": "booking_not_active",
        }

    if not appointment_at:
        return {
            "success": False,
            "booking_id": booking_id,
            "message": get_missing_info_message("дату и время"),
            "error": "missing_datetime",
        }

    appointment_dt = _parse_slot_datetime(appointment_at)
    if not appointment_dt:
        return {
            "success": False,
            "booking_id": booking_id,
            "message": get_invalid_datetime_response(),
            "error": "invalid_datetime",
        }

    if appointment_dt <= datetime.now():
        return {
            "success": False,
            "booking_id": booking_id,
            "message": get_past_datetime_response(),
            "error": "past_datetime",
        }

    if not check_slot_available(appointment_at, clinic_id, duration_minutes=duration, exclude_booking_id=booking_id):
        message, error_code, alternatives = _get_slot_issue_message(appointment_at, clinic_id, duration, exclude_booking_id=booking_id)
        logger.info(
            "BOOKING_RESCHEDULE prevented booking_id=%s chat_id=%s time=%s reason=%s",
            booking_id,
            normalized_chat_id,
            appointment_at,
            error_code,
        )
        return {
            "success": False,
            "booking_id": booking_id,
            "message": message,
            "error": error_code,
            "status": error_code,
            "alternative_slots": alternatives,
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
        UPDATE bookings
        SET service = ?, full_name = ?, phone = ?, appointment_at = ?, duration_minutes = ?, updated_at = ?
        WHERE id = ? AND status = 'active'
        """, (
            service_name,
            safe_state.get("full_name", "Клиент"),
            safe_state.get("phone", ""),
            appointment_at,
            duration,
            now,
            booking_id,
        ))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected <= 0:
            logger.warning("BOOKING_RESCHEDULE no rows updated booking_id=%s chat_id=%s", booking_id, normalized_chat_id)
            return {
                "success": False,
                "booking_id": booking_id,
                "message": get_no_active_booking_response(),
                "error": "booking_not_active",
            }

        mark_conversation_booked(clinic_id, normalized_chat_id)
        message = get_reschedule_confirmation(format_slot_for_display(appointment_at))
        logger.info(
            "BOOKING_RESCHEDULE success booking_id=%s chat_id=%s time=%s",
            booking_id,
            normalized_chat_id,
            appointment_at,
        )
        return {
            "success": True,
            "booking_id": booking_id,
            "message": message,
            "error": None,
        }
    except Exception:
        logger.exception("BOOKING_RESCHEDULE failed booking_id=%s chat_id=%s", booking_id, normalized_chat_id)
        return {
            "success": False,
            "booking_id": booking_id,
            "message": get_booking_error_response(),
            "error": "reschedule_failed",
        }


def reschedule_booking_by_chat_id(chat_id: str, new_datetime: str, state: dict | None = None) -> dict:
    """Find the active booking for a chat and reschedule it to a new time."""
    normalized_chat_id, safe_state = _normalize_booking_request(chat_id, state)
    safe_state["preferred_datetime"] = (new_datetime or "").strip()

    if not normalized_chat_id:
        logger.warning("BOOKING_RESCHEDULE invalid chat_id=%r", chat_id)
        return {
            "success": False,
            "booking_id": None,
            "message": get_booking_error_response(),
            "error": "invalid_chat_id",
        }

    active_booking = get_active_booking_by_chat_id(normalized_chat_id)
    if not active_booking:
        logger.info("BOOKING_RESCHEDULE skipped no active booking chat_id=%s", normalized_chat_id)
        reset_user_state(normalized_chat_id)
        return {
            "success": False,
            "booking_id": None,
            "message": get_no_active_booking_response(),
            "error": "no_active_booking",
        }

    if not safe_state.get("service"):
        safe_state["service"] = active_booking.get("service", "")
    if not safe_state.get("full_name") or safe_state.get("full_name") == "Клиент":
        safe_state["full_name"] = active_booking.get("full_name", "Клиент") or "Клиент"
    if not safe_state.get("phone"):
        safe_state["phone"] = active_booking.get("phone", "")
    safe_state["chat_id"] = normalized_chat_id

    return update_booking(active_booking["id"], safe_state)


def create_or_update_booking(chat_id: str, state: dict) -> dict:
    """Create a new booking only; rescheduling is handled by the explicit reschedule flow."""
    normalized_chat_id, safe_state = _normalize_booking_request(chat_id, state)

    if not normalized_chat_id:
        return {
            "success": False,
            "booking_id": None,
            "message": get_booking_error_response(),
            "error": "invalid_chat_id",
        }

    if not safe_state.get("preferred_datetime"):
        return {
            "success": False,
            "booking_id": None,
            "message": get_missing_info_message("дату и время"),
            "error": "missing_datetime",
        }

    existing_booking = get_active_booking_by_chat_id(normalized_chat_id)
    if existing_booking:
        appointment_text = format_slot_for_display(existing_booking.get("appointment_at", "")) or existing_booking.get("appointment_at", "")
        service_name = existing_booking.get("service", "визит")
        logger.info(
            "BOOKING_ROUTE blocked duplicate chat_id=%s booking_id=%s",
            normalized_chat_id,
            existing_booking.get("id"),
        )
        return {
            "success": False,
            "booking_id": existing_booking.get("id"),
            "message": f"У вас уже есть запись на {appointment_text} ({service_name}). Если хотите изменить время, напишите новое время или попросите перенести запись.",
            "error": "active_booking_exists",
            "status": "active_booking_exists",
        }

    logger.info(
        "BOOKING_ROUTE create chat_id=%s time=%s",
        normalized_chat_id,
        safe_state.get("preferred_datetime", ""),
    )
    return create_booking(normalized_chat_id, safe_state)


def get_all_active_bookings() -> list:
    """
    Get all active bookings from the database.

    Returns:
        List of booking dictionaries with all booking data
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at
    FROM bookings
    WHERE status = 'active'
    ORDER BY appointment_at ASC
    """)

    bookings = []
    for row in cursor.fetchall():
        booking = {
            "id": row[0],
            "chat_id": row[1],
            "service": row[2],
            "full_name": row[3],
            "phone": row[4],
            "appointment_at": row[5],
            "status": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }
        bookings.append(booking)

    conn.close()
    return bookings


def get_conversation_by_chat_id(clinic_id: int, chat_id: str):
    normalized_chat_id = _normalize_crm_text(chat_id)
    if not normalized_chat_id:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, clinic_id, chat_id, full_name, phone, last_user_message, last_bot_reply,
           status, needs_operator, has_booking, is_lost, follow_up_sent, created_at, updated_at,
           bot_paused_until,
           (
               SELECT sender_type FROM messages m
               WHERE m.conversation_id = conversations.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_sender_type,
           (
               SELECT text FROM messages m
               WHERE m.conversation_id = conversations.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message,
           (
               SELECT created_at FROM messages m
               WHERE m.conversation_id = conversations.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message_at
    FROM conversations
    WHERE clinic_id = ? AND chat_id = ?
    LIMIT 1
    """, (clinic_id, normalized_chat_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    latest_sender = row[15] or ("user" if row[5] else "bot" if row[6] else "")
    latest_message = row[16] or row[5] or row[6] or ""
    latest_message_at = row[17] or row[13]

    return {
        "id": row[0],
        "clinic_id": row[1],
        "chat_id": row[2],
        "full_name": row[3],
        "phone": row[4],
        "last_user_message": row[5],
        "last_bot_reply": row[6],
        "status": row[7],
        "needs_operator": row[8],
        "has_booking": row[9],
        "is_lost": row[10],
        "follow_up_sent": row[11],
        "created_at": row[12],
        "updated_at": row[13],
        "bot_paused_until": row[14],
        "latest_sender_type": latest_sender,
        "latest_message": latest_message,
        "latest_message_at": latest_message_at,
        "last_activity_at": latest_message_at or row[13],
    }


def upsert_conversation(clinic_id: int, chat_id: str, full_name: str = None, phone: str = None,
                        last_user_message: str = None, last_bot_reply: str = None,
                        status: str = None, needs_operator: int = None,
                        has_booking: int = None, is_lost: int = None,
                        follow_up_sent: int = None, bot_paused_until: str = None):
    normalized_chat_id = _normalize_crm_text(chat_id)
    if not _is_valid_crm_chat_id(normalized_chat_id):
        logger.info("CRM skip conversation update for invalid chat_id=%r", chat_id)
        return None

    normalized_name = _normalize_crm_text(full_name, drop_placeholders=True) if full_name is not None else None
    normalized_phone = _normalize_crm_text(phone) if phone is not None else None
    normalized_user_message = _normalize_crm_text(last_user_message) if last_user_message is not None else None
    normalized_bot_reply = _normalize_crm_text(last_bot_reply) if last_bot_reply is not None else None
    normalized_status = _normalize_crm_text(status) if status is not None else None
    if normalized_status and normalized_status not in _VALID_CONVERSATION_STATUSES:
        normalized_status = "active"

    if follow_up_sent is not None:
        follow_up_sent = 1 if follow_up_sent else 0

    now = datetime.now().isoformat()
    conversation = get_conversation_by_chat_id(clinic_id, normalized_chat_id)
    has_meaningful_payload = _has_meaningful_conversation_payload(
        full_name=normalized_name,
        phone=normalized_phone,
        last_user_message=normalized_user_message,
        last_bot_reply=normalized_bot_reply,
        has_booking=has_booking,
        needs_operator=needs_operator,
    )

    if conversation:
        updates = []
        params = []

        if normalized_name:
            updates.append("full_name = ?")
            params.append(normalized_name)
        if normalized_phone:
            updates.append("phone = ?")
            params.append(normalized_phone)
        if normalized_user_message:
            updates.append("last_user_message = ?")
            params.append(normalized_user_message)
        if normalized_bot_reply:
            updates.append("last_bot_reply = ?")
            params.append(normalized_bot_reply)
        if normalized_status is not None:
            updates.append("status = ?")
            params.append(normalized_status)
        if needs_operator is not None:
            updates.append("needs_operator = ?")
            params.append(1 if needs_operator else 0)
        if has_booking is not None:
            updates.append("has_booking = ?")
            params.append(1 if has_booking else 0)
        if is_lost is not None:
            updates.append("is_lost = ?")
            params.append(1 if is_lost else 0)
        if follow_up_sent is not None:
            updates.append("follow_up_sent = ?")
            params.append(follow_up_sent)
        if bot_paused_until is not None:
            updates.append("bot_paused_until = ?")
            params.append(bot_paused_until)

        if not updates:
            return conversation

        updates.append("updated_at = ?")
        params.append(now)
        query = f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?"
        params.append(conversation["id"])

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        conn.commit()
        conn.close()

        return get_conversation_by_chat_id(clinic_id, normalized_chat_id)

    if not has_meaningful_payload:
        logger.info("CRM skip empty conversation create for chat_id=%s", normalized_chat_id)
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO conversations (
        clinic_id, chat_id, full_name, phone,
        last_user_message, last_bot_reply, status,
        needs_operator, has_booking, is_lost, follow_up_sent,
        bot_paused_until, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        clinic_id,
        normalized_chat_id,
        normalized_name or "",
        normalized_phone or "",
        normalized_user_message or "",
        normalized_bot_reply or "",
        normalized_status or ("booked" if has_booking else "active"),
        1 if needs_operator else 0,
        1 if has_booking else 0,
        1 if is_lost else 0,
        follow_up_sent if follow_up_sent is not None else (1 if has_booking else 0),
        bot_paused_until or "",
        now,
        now,
    ))
    conn.commit()
    conn.close()

    return get_conversation_by_chat_id(clinic_id, normalized_chat_id)


def add_doctor(full_name: str, profession: str, clinic_id: int = 1) -> bool:
    full_name = (full_name or "").strip()
    profession = (profession or "").strip().lower()

    if not full_name or not profession:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("""
    INSERT INTO doctors (clinic_id, full_name, profession, is_active, created_at, updated_at)
    VALUES (?, ?, ?, 1, ?, ?)
    """, (clinic_id, full_name, profession, now, now))

    conn.commit()
    conn.close()
    return True


def get_or_create_conversation(clinic_id: int, chat_id: str):
    conv = get_conversation_by_chat_id(clinic_id, chat_id)
    if conv:
        return conv
    return upsert_conversation(clinic_id, chat_id)


def update_conversation_from_user_message(clinic_id: int, chat_id: str,
                                          full_name: str = None, phone: str = None,
                                          user_message: str = None):
    existing = get_conversation_by_chat_id(clinic_id, chat_id)
    active_booking = get_active_booking_by_chat_id(str(chat_id).strip())
    has_booking = 1 if active_booking else 0
    needs_operator = 1 if existing and existing.get("needs_operator") else 0

    existing_status = (existing.get("status") if existing else "") or ""
    terminal_statuses = {"cancelled", "completed", "no_show", "closed"}
    if has_booking:
        status = "booked"
    elif existing_status in terminal_statuses:
        status = existing_status
    else:
        status = "waiting_operator" if needs_operator else "active"

    is_lost = 1 if (existing and (existing.get("is_lost") or existing_status == "no_show")) else 0
    follow_up_sent = 1 if has_booking or existing_status in terminal_statuses else (existing.get("follow_up_sent") if existing else 0)

    conv = upsert_conversation(
        clinic_id=clinic_id,
        chat_id=chat_id,
        full_name=full_name,
        phone=phone,
        last_user_message=user_message,
        status=status,
        needs_operator=needs_operator,
        has_booking=has_booking,
        is_lost=is_lost,
        follow_up_sent=follow_up_sent,
    )
    if conv and _normalize_crm_text(user_message):
        store_message(conv["id"], chat_id, "user", user_message)
    return conv


def update_conversation_bot_reply(clinic_id: int, chat_id: str, bot_reply: str):
    conv = upsert_conversation(
        clinic_id=clinic_id,
        chat_id=chat_id,
        last_bot_reply=bot_reply,
    )
    if conv and _normalize_crm_text(bot_reply):
        store_message(conv["id"], chat_id, "bot", bot_reply)
    return conv


def mark_conversation_waiting_operator(clinic_id: int, chat_id: str, bot_paused_until: str = None):
    return upsert_conversation(
        clinic_id=clinic_id,
        chat_id=chat_id,
        needs_operator=1,
        status="waiting_operator",
        is_lost=0,
        follow_up_sent=0,
        bot_paused_until=bot_paused_until,
    )


def mark_conversation_booked(clinic_id: int, chat_id: str):
    return upsert_conversation(
        clinic_id=clinic_id,
        chat_id=chat_id,
        has_booking=1,
        needs_operator=0,
        status="booked",
        is_lost=0,
        follow_up_sent=1,
    )


def close_conversation(conversation_id: int) -> bool:
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE conversations
    SET status = 'closed', needs_operator = 0, follow_up_sent = 1, updated_at = ?
    WHERE id = ?
    """, (now, conversation_id))

    rows = cursor.rowcount
    conn.commit()
    conn.close()
    return rows > 0


def mark_conversation_lost(conversation_id: int) -> bool:
    """Mark a conversation as no-show in the CRM.

    Backward compatibility: the function name stays the same because older routes
    and data flows still reference `lost`, but new writes use `no_show`.
    """
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE conversations
    SET status = 'no_show', is_lost = 1, needs_operator = 0, has_booking = 0, follow_up_sent = 1, updated_at = ?
    WHERE id = ?
    """, (now, conversation_id))

    rows = cursor.rowcount
    conn.commit()
    conn.close()
    return rows > 0

def get_doctor_by_id(doctor_id: int, clinic_id: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, clinic_id, full_name, profession, is_active
    FROM doctors
    WHERE id = ? AND clinic_id = ?
    LIMIT 1
    """, (doctor_id, clinic_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "clinic_id": row[1],
        "full_name": row[2],
        "profession": row[3],
        "is_active": row[4],
    }


def update_doctor(doctor_id: int, full_name: str, profession: str, clinic_id: int = 1) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("""
    UPDATE doctors
    SET full_name = ?, profession = ?, updated_at = ?
    WHERE id = ? AND clinic_id = ?
    """, (full_name.strip(), profession.strip().lower(), now, doctor_id, clinic_id))

    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def get_doctor_by_id(doctor_id: int, clinic_id: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, clinic_id, full_name, profession, is_active
    FROM doctors
    WHERE id = ? AND clinic_id = ?
    LIMIT 1
    """, (doctor_id, clinic_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "clinic_id": row[1],
        "full_name": row[2],
        "profession": row[3],
        "is_active": row[4],
    }
    
def deactivate_doctor(doctor_id: int, clinic_id: int = 1) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("""
    UPDATE doctors
    SET is_active = 0, updated_at = ?
    WHERE id = ? AND clinic_id = ?
    """, (now, doctor_id, clinic_id))

    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed

def clear_conversation_operator_flag(conversation_id: int) -> bool:
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE conversations
    SET needs_operator = 0,
        status = CASE WHEN has_booking = 1 THEN 'booked' ELSE 'active' END,
        bot_paused_until = NULL,
        updated_at = ?
    WHERE id = ?
    """, (now, conversation_id))

    rows = cursor.rowcount
    conn.commit()
    conn.close()
    return rows > 0


def get_operator_inbox(clinic_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.id, c.chat_id, c.full_name, c.phone, c.last_user_message, c.last_bot_reply,
           c.status, c.needs_operator, c.has_booking, c.is_lost, c.created_at, c.updated_at,
           (
               SELECT sender_type FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_sender_type,
           (
               SELECT text FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message,
           (
               SELECT created_at FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message_at
    FROM conversations c
    WHERE c.clinic_id = ?
      AND c.needs_operator = 1
      AND c.is_lost = 0
      AND c.status IN ('waiting_operator', 'active', 'booked')
      AND COALESCE(TRIM(c.chat_id), '') <> ''
      AND (
          COALESCE(TRIM(c.last_user_message), '') <> ''
          OR COALESCE(TRIM(c.last_bot_reply), '') <> ''
          OR COALESCE(TRIM(c.phone), '') <> ''
          OR COALESCE(TRIM(c.full_name), '') <> ''
      )
    ORDER BY COALESCE(latest_message_at, c.updated_at) DESC, c.id DESC
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "chat_id": row[1],
            "full_name": row[2],
            "phone": row[3],
            "last_user_message": row[4],
            "last_bot_reply": row[5],
            "status": row[6],
            "needs_operator": row[7],
            "has_booking": row[8],
            "is_lost": row[9],
            "created_at": row[10],
            "updated_at": row[11],
            "latest_sender_type": row[12] or ("user" if row[4] else "bot" if row[5] else ""),
            "latest_message": row[13] or row[4] or row[5] or "",
            "latest_message_at": row[14] or row[11],
            "last_activity_at": row[14] or row[11],
        }
        for row in rows
    ]


def get_conversations_needing_operator(clinic_id: int) -> list:
    # synonym for operator inbox between service and API layer
    return get_operator_inbox(clinic_id)


def get_leads_without_booking(clinic_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.id, c.clinic_id, c.chat_id, c.full_name, c.phone, c.last_user_message,
           c.last_bot_reply, c.status, c.needs_operator, c.has_booking, c.is_lost,
           c.created_at, c.updated_at,
           (
               SELECT sender_type FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_sender_type,
           (
               SELECT text FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message,
           (
               SELECT created_at FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message_at
    FROM conversations c
    WHERE c.clinic_id = ?
      AND c.has_booking = 0
      AND c.is_lost = 0
      AND c.status IN ('active', 'waiting_operator')
      AND COALESCE(TRIM(c.chat_id), '') <> ''
      AND (
          COALESCE(TRIM(c.last_user_message), '') <> ''
          OR COALESCE(TRIM(c.last_bot_reply), '') <> ''
          OR COALESCE(TRIM(c.phone), '') <> ''
          OR COALESCE(TRIM(c.full_name), '') <> ''
      )
    ORDER BY COALESCE(latest_message_at, c.updated_at) DESC, c.id DESC
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "clinic_id": row[1],
            "chat_id": row[2],
            "full_name": row[3],
            "phone": row[4],
            "last_user_message": row[5],
            "last_bot_reply": row[6],
            "status": row[7],
            "needs_operator": row[8],
            "has_booking": row[9],
            "is_lost": row[10],
            "created_at": row[11],
            "updated_at": row[12],
            "latest_sender_type": row[13] or ("user" if row[5] else "bot" if row[6] else ""),
            "latest_message": row[14] or row[5] or row[6] or "",
            "latest_message_at": row[15] or row[12],
            "last_activity_at": row[15] or row[12],
        }
        for row in rows
    ]


def get_all_conversations(clinic_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.id, c.clinic_id, c.chat_id, c.full_name, c.phone, c.last_user_message,
           c.last_bot_reply, c.status, c.needs_operator, c.has_booking, c.is_lost,
           c.created_at, c.updated_at,
           (
               SELECT sender_type FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_sender_type,
           (
               SELECT text FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message,
           (
               SELECT created_at FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message_at
    FROM conversations c
    WHERE c.clinic_id = ?
      AND COALESCE(TRIM(c.chat_id), '') <> ''
      AND (
          c.has_booking = 1
          OR c.needs_operator = 1
          OR c.is_lost = 1
          OR COALESCE(TRIM(c.last_user_message), '') <> ''
          OR COALESCE(TRIM(c.last_bot_reply), '') <> ''
          OR COALESCE(TRIM(c.phone), '') <> ''
          OR COALESCE(TRIM(c.full_name), '') <> ''
      )
    ORDER BY COALESCE(latest_message_at, c.updated_at) DESC, c.id DESC
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "clinic_id": row[1],
            "chat_id": row[2],
            "full_name": row[3],
            "phone": row[4],
            "last_user_message": row[5],
            "last_bot_reply": row[6],
            "status": row[7],
            "needs_operator": row[8],
            "has_booking": row[9],
            "is_lost": row[10],
            "created_at": row[11],
            "updated_at": row[12],
            "latest_sender_type": row[13] or ("user" if row[5] else "bot" if row[6] else ""),
            "latest_message": row[14] or row[5] or row[6] or "",
            "latest_message_at": row[15] or row[12],
            "last_activity_at": row[15] or row[12],
        }
        for row in rows
    ]


def get_lost_conversations(clinic_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.id, c.clinic_id, c.chat_id, c.full_name, c.phone, c.last_user_message,
           c.last_bot_reply, c.status, c.needs_operator, c.has_booking, c.is_lost,
           c.created_at, c.updated_at,
           (
               SELECT sender_type FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_sender_type,
           (
               SELECT text FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message,
           (
               SELECT created_at FROM messages m
               WHERE m.conversation_id = c.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message_at
    FROM conversations c
    WHERE c.clinic_id = ?
      AND c.is_lost = 1
      AND COALESCE(TRIM(c.chat_id), '') <> ''
      AND (
          COALESCE(TRIM(c.last_user_message), '') <> ''
          OR COALESCE(TRIM(c.phone), '') <> ''
          OR COALESCE(TRIM(c.full_name), '') <> ''
          OR COALESCE(TRIM(c.last_bot_reply), '') <> ''
      )
    ORDER BY COALESCE(latest_message_at, c.updated_at) DESC, c.id DESC
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "clinic_id": row[1],
            "chat_id": row[2],
            "full_name": row[3],
            "phone": row[4],
            "last_user_message": row[5],
            "last_bot_reply": row[6],
            "status": row[7],
            "needs_operator": row[8],
            "has_booking": row[9],
            "is_lost": row[10],
            "created_at": row[11],
            "updated_at": row[12],
            "latest_sender_type": row[13] or ("user" if row[5] else "bot" if row[6] else ""),
            "latest_message": row[14] or row[5] or row[6] or "",
            "latest_message_at": row[15] or row[12],
            "last_activity_at": row[15] or row[12],
        }
        for row in rows
    ]


def format_booking_for_display(booking: dict) -> str:
    """
    Format a booking dictionary for human-readable display in Russian.

    Args:
        booking: Booking dictionary with booking data

    Returns:
        Formatted string like: "ID 5: Иван Сидоров | +79123456789 | чистка | 26 марта в 15:00"
    """
    booking_id = booking.get("id", "?")
    full_name = booking.get("full_name", "—")
    phone = booking.get("phone", "—")
    service = booking.get("service", "—")
    appointment_at = booking.get("appointment_at", "—")

    # Format appointment_at if it's in datetime format
    if appointment_at and " " in appointment_at:
        appointment_at_display = format_slot_for_display(appointment_at)
    else:
        appointment_at_display = appointment_at

    return f"ID {booking_id}: {full_name} | {phone} | {service} | {appointment_at_display}"


def get_booking_by_id(booking_id: int):
    """Return one booking by ID for admin actions."""
    if not booking_id or int(booking_id) <= 0:
        return None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, clinic_id, chat_id, service, full_name, phone, appointment_at,
               duration_minutes, status, created_at, updated_at,
               reminder_24h_sent, reminder_2h_sent, source_channel
        FROM bookings
        WHERE id = ?
        """, (booking_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "clinic_id": row[1],
            "chat_id": row[2],
            "service": row[3],
            "full_name": row[4],
            "phone": row[5],
            "appointment_at": row[6],
            "duration_minutes": row[7],
            "status": row[8],
            "created_at": row[9],
            "updated_at": row[10],
            "reminder_24h_sent": row[11],
            "reminder_2h_sent": row[12],
            "source_channel": row[13] or "",
        }
    except Exception as e:
        logger.exception("BOOKING_GET_BY_ID failed booking_id=%s: %s", booking_id, e)
        return None


def confirm_booking_by_id(booking_id: int) -> dict:
    """Confirm a booking from an admin command."""
    booking = get_booking_by_id(booking_id)
    if not booking:
        return {"success": False, "booking": None, "message": "Запись не найдена.", "error": "not_found"}

    if booking.get("status") == "active":
        return {"success": True, "booking": booking, "message": "Запись уже подтверждена.", "error": None}

    if booking.get("status") not in {"pending", "pending_admin"}:
        return {
            "success": False,
            "booking": booking,
            "message": f"Нельзя подтвердить запись со статусом {booking.get('status')}.",
            "error": "invalid_status",
        }

    try:
        now = datetime.now().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE bookings
        SET status = 'active', updated_at = ?
        WHERE id = ? AND status IN ('pending', 'pending_admin')
        """, (now, booking_id))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected <= 0:
            return {"success": False, "booking": booking, "message": "Запись не удалось подтвердить.", "error": "not_updated"}

        updated_booking = get_booking_by_id(booking_id) or booking
        upsert_conversation(
            clinic_id=updated_booking.get("clinic_id", 1),
            chat_id=updated_booking.get("chat_id", ""),
            has_booking=1,
            status="booked",
            follow_up_sent=1,
        )
        logger.info("BOOKING_CONFIRM admin booking_id=%s", booking_id)
        return {"success": True, "booking": updated_booking, "message": "Запись подтверждена.", "error": None}
    except Exception as e:
        logger.exception("BOOKING_CONFIRM failed booking_id=%s: %s", booking_id, e)
        return {"success": False, "booking": booking, "message": "Не удалось подтвердить запись.", "error": "confirm_failed"}


def cancel_active_booking_by_chat_id(chat_id: str) -> dict:
    """Cancel the current active booking for a chat and return a user-ready result."""
    normalized_chat_id = str(chat_id).strip() if chat_id is not None else ""
    logger.info("BOOKING_CANCEL start chat_id=%s", normalized_chat_id or "?")

    if not normalized_chat_id:
        logger.warning("BOOKING_CANCEL invalid chat_id=%r", chat_id)
        return {
            "success": False,
            "booking_id": None,
            "message": get_cancellation_error_response(),
            "error": "invalid_chat_id",
            "booking": None,
        }

    booking = get_active_booking_by_chat_id(normalized_chat_id)
    if not booking:
        logger.info("BOOKING_CANCEL skipped no active booking chat_id=%s", normalized_chat_id)
        reset_user_state(normalized_chat_id)
        return {
            "success": False,
            "booking_id": None,
            "message": get_no_active_booking_response(),
            "error": "no_active_booking",
            "booking": None,
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
        UPDATE bookings
        SET status = 'cancelled', updated_at = ?
        WHERE id = ? AND status = 'active'
        """, (now, booking["id"]))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected <= 0:
            logger.warning(
                "BOOKING_CANCEL already inactive chat_id=%s booking_id=%s",
                normalized_chat_id,
                booking.get("id"),
            )
            reset_user_state(normalized_chat_id)
            return {
                "success": False,
                "booking_id": booking.get("id"),
                "message": get_no_active_booking_response(),
                "error": "already_cancelled",
                "booking": booking,
            }

        upsert_conversation(
            clinic_id=booking.get("clinic_id", 1),
            chat_id=normalized_chat_id,
            has_booking=0,
            needs_operator=0,
            is_lost=0,
            status="cancelled",
            follow_up_sent=1,
        )
        reset_user_state(normalized_chat_id)

        appointment_display = format_slot_for_display(booking.get("appointment_at", ""))
        logger.info(
            "BOOKING_CANCEL success chat_id=%s booking_id=%s time=%s",
            normalized_chat_id,
            booking.get("id"),
            booking.get("appointment_at", ""),
        )
        return {
            "success": True,
            "booking_id": booking.get("id"),
            "message": get_cancellation_confirmation(appointment_display, booking.get("service", "")),
            "error": None,
            "booking": booking,
        }
    except Exception:
        logger.exception("BOOKING_CANCEL failed chat_id=%s booking_id=%s", normalized_chat_id, booking.get("id") if booking else None)
        reset_user_state(normalized_chat_id)
        return {
            "success": False,
            "booking_id": booking.get("id") if booking else None,
            "message": get_cancellation_error_response(),
            "error": "cancel_failed",
            "booking": booking,
        }


def cancel_booking_by_id(booking_id: int) -> bool:
    """
    Cancel a booking by ID (admin action).

    Args:
        booking_id: ID of the booking to cancel

    Returns:
        True if successful, False if booking not found or already cancelled
    """
    if not booking_id or int(booking_id) <= 0:
        return False

    try:
        now = datetime.now().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT chat_id, clinic_id FROM bookings WHERE id = ?", (booking_id,))
        booking_row = cursor.fetchone()

        cursor.execute("""
        UPDATE bookings
        SET status = 'cancelled', updated_at = ?
        WHERE id = ? AND status = 'active'
        """, (now, booking_id))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        if rows_affected > 0 and booking_row:
            upsert_conversation(
                clinic_id=booking_row[1] or 1,
                chat_id=booking_row[0],
                has_booking=0,
                needs_operator=0,
                is_lost=0,
                status="cancelled",
                follow_up_sent=1,
            )
            return True

        return False
    except Exception as e:
        print(f"ERROR cancel_booking_by_id: {e}")
        return False


def mark_booking_completed(booking_id: int) -> bool:
    """
    Mark a booking as completed (admin action) and sync CRM status.

    Args:
        booking_id: ID of the booking

    Returns:
        True if successful, False if booking not found
    """
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT chat_id, clinic_id FROM bookings WHERE id = ?", (booking_id,))
    booking_row = cursor.fetchone()

    cursor.execute("""
    UPDATE bookings
    SET status = 'completed', updated_at = ?
    WHERE id = ?
    """, (now, booking_id))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    if rows_affected > 0 and booking_row:
        upsert_conversation(
            clinic_id=booking_row[1] or 1,
            chat_id=booking_row[0],
            has_booking=0,
            needs_operator=0,
            is_lost=0,
            status="completed",
            follow_up_sent=1,
        )
        return True

    return False


def mark_booking_no_show(booking_id: int) -> bool:
    """
    Mark a booking as no_show (admin action) and sync CRM status.

    Args:
        booking_id: ID of the booking

    Returns:
        True if successful, False if booking not found
    """
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT chat_id, clinic_id FROM bookings WHERE id = ?", (booking_id,))
    booking_row = cursor.fetchone()

    cursor.execute("""
    UPDATE bookings
    SET status = 'no_show', updated_at = ?
    WHERE id = ?
    """, (now, booking_id))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    if rows_affected > 0 and booking_row:
        upsert_conversation(
            clinic_id=booking_row[1] or 1,
            chat_id=booking_row[0],
            has_booking=0,
            needs_operator=0,
            is_lost=1,
            status="no_show",
            follow_up_sent=1,
        )
        return True

    return False


def mark_reminder_24h_sent(booking_id: int) -> bool:
    """
    Mark a booking's 24-hour reminder as sent.

    Args:
        booking_id: ID of the booking

    Returns:
        True if update was successful, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE bookings
    SET reminder_24h_sent = 1
    WHERE id = ?
    """, (booking_id,))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_affected > 0


def mark_reminder_2h_sent(booking_id: int) -> bool:
    """
    Mark a booking's 2-hour reminder as sent.

    Args:
        booking_id: ID of the booking

    Returns:
        True if update was successful, False otherwise
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE bookings
    SET reminder_2h_sent = 1
    WHERE id = ?
    """, (booking_id,))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_affected > 0


def get_bookings_needing_24h_reminder() -> list:
    """
    Get all active bookings that need 24-hour reminders.
    
    Returns bookings where:
    - status = 'active'
    - appointment is roughly 24 hours away
    - reminder_24h_sent = 0

    Returns:
        List of booking dictionaries
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    check_after = now + timedelta(hours=23)
    check_before = now + timedelta(hours=25)

    cursor.execute("""
    SELECT id, clinic_id, chat_id, service, full_name, phone, appointment_at, status,
           created_at, updated_at, reminder_24h_sent, reminder_2h_sent, source_channel
    FROM bookings
    WHERE status = 'active'
    AND reminder_24h_sent = 0
    """)

    bookings = []
    for row in cursor.fetchall():
        try:
            appointment = datetime.fromisoformat(row[6])
            if check_after <= appointment <= check_before:
                booking = {
                    "id": row[0],
                    "clinic_id": row[1],
                    "chat_id": row[2],
                    "service": row[3],
                    "full_name": row[4],
                    "phone": row[5],
                    "appointment_at": row[6],
                    "status": row[7],
                    "created_at": row[8],
                    "updated_at": row[9],
                    "reminder_24h_sent": row[10],
                    "reminder_2h_sent": row[11],
                    "source_channel": row[12] or "",
                }
                bookings.append(booking)
        except (ValueError, TypeError):
            pass

    conn.close()
    return bookings


def get_bookings_needing_2h_reminder() -> list:
    """
    Get all active bookings that need 2-hour reminders.
    
    Returns bookings where:
    - status = 'active'
    - appointment is roughly 2 hours away
    - reminder_2h_sent = 0

    Returns:
        List of booking dictionaries
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    check_after = now + timedelta(minutes=90)
    check_before = now + timedelta(minutes=150)

    cursor.execute("""
    SELECT id, clinic_id, chat_id, service, full_name, phone, appointment_at, status,
           created_at, updated_at, reminder_24h_sent, reminder_2h_sent, source_channel
    FROM bookings
    WHERE status = 'active'
    AND reminder_2h_sent = 0
    """)

    bookings = []
    for row in cursor.fetchall():
        try:
            appointment = datetime.fromisoformat(row[6])
            if check_after <= appointment <= check_before:
                booking = {
                    "id": row[0],
                    "clinic_id": row[1],
                    "chat_id": row[2],
                    "service": row[3],
                    "full_name": row[4],
                    "phone": row[5],
                    "appointment_at": row[6],
                    "status": row[7],
                    "created_at": row[8],
                    "updated_at": row[9],
                    "reminder_24h_sent": row[10],
                    "reminder_2h_sent": row[11],
                    "source_channel": row[12] or "",
                }
                bookings.append(booking)
        except (ValueError, TypeError):
            pass

    conn.close()
    return bookings


def get_bookings_by_status(clinic_id: int, status: str) -> list:
    """
    Get all bookings with a specific status for a clinic.

    Args:
        clinic_id: Clinic ID
        status: Status to filter by (e.g., 'completed', 'cancelled', 'no_show', 'active')

    Returns:
        List of booking dictionaries
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, clinic_id, chat_id, service, full_name, phone, appointment_at, 
           duration_minutes, status, created_at, updated_at, reminder_24h_sent, reminder_2h_sent
    FROM bookings
    WHERE clinic_id = ? AND status = ?
    ORDER BY appointment_at DESC
    """, (clinic_id, status))

    bookings = []
    for row in cursor.fetchall():
        booking = {
            "id": row[0],
            "clinic_id": row[1],
            "chat_id": row[2],
            "service": row[3],
            "full_name": row[4],
            "phone": row[5],
            "appointment_at": row[6],
            "duration_minutes": row[7],
            "status": row[8],
            "created_at": row[9],
            "updated_at": row[10],
            "reminder_24h_sent": row[11],
            "reminder_2h_sent": row[12],
        }
        bookings.append(booking)

    conn.close()
    return bookings


def get_conversations_needing_followup(clinic_id: int) -> list:
    """
    Get conversations that need follow-up messages.
    
    Criteria:
    - has_booking = 0 (no booking yet)
    - is_lost = 0 (not a lost lead)
    - follow_up_sent = 0 (follow-up not sent)
    - status = 'active' (active conversation)
    - last_user_message exists and was more than 30 minutes ago

    Args:
        clinic_id: Clinic ID

    Returns:
        List of conversation dictionaries
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.now()
    thirty_min_ago = now - timedelta(minutes=30)

    cursor.execute("""
    SELECT id, clinic_id, chat_id, full_name, phone, last_user_message, last_bot_reply,
           status, needs_operator, has_booking, is_lost, follow_up_sent, created_at, updated_at
    FROM conversations
    WHERE clinic_id = ?
      AND has_booking = 0
      AND is_lost = 0
      AND follow_up_sent = 0
      AND status = 'active'
      AND needs_operator = 0
      AND COALESCE(TRIM(chat_id), '') <> ''
      AND COALESCE(TRIM(last_user_message), '') <> ''
    """, (clinic_id,))

    conversations = []
    for row in cursor.fetchall():
        try:
            if not _is_valid_crm_chat_id(row[2]):
                continue
            updated_at = datetime.fromisoformat(row[13])
            if updated_at <= thirty_min_ago:
                conversation = {
                    "id": row[0],
                    "clinic_id": row[1],
                    "chat_id": row[2],
                    "full_name": row[3],
                    "phone": row[4],
                    "last_user_message": row[5],
                    "last_bot_reply": row[6],
                    "status": row[7],
                    "needs_operator": row[8],
                    "has_booking": row[9],
                    "is_lost": row[10],
                    "follow_up_sent": row[11],
                    "created_at": row[12],
                    "updated_at": row[13],
                }
                conversations.append(conversation)
        except (ValueError, TypeError):
            pass

    conn.close()
    return conversations


def mark_followup_sent(conversation_id: int) -> bool:
    """
    Mark a conversation as having follow-up sent.

    Args:
        conversation_id: ID of the conversation

    Returns:
        True if successful, False if conversation not found
    """
    now = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE conversations
    SET follow_up_sent = 1, updated_at = ?
    WHERE id = ?
    """, (now, conversation_id))

    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()

    return rows_affected > 0


# ========================
# Clinic Settings Functions
# ========================

def get_clinic_settings(clinic_id: int = 1) -> dict:
    try:
        clinic_id = int(clinic_id or 1)
    except (TypeError, ValueError):
        clinic_id = 1

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT work_start, work_end, slot_step_minutes, clinic_name, working_days, bot_pause_hours, address,
           admin_notify_whatsapp, notify_new_leads, notify_new_bookings,
           notify_operator_requests, whatsapp_reminders_enabled
    FROM clinic_settings
    WHERE clinic_id = ?
    ORDER BY id DESC
    LIMIT 1
    """, (clinic_id,))

    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "SELECT name, work_start, work_end, slot_step_minutes, working_days, address FROM clinics WHERE id = ?",
            (clinic_id,)
        )
        clinic_row = cursor.fetchone()

        clinic_name = clinic_row[0] if clinic_row and clinic_row[0] else "Клиника"
        work_start = clinic_row[1] if clinic_row and clinic_row[1] else "10:00"
        work_end = clinic_row[2] if clinic_row and clinic_row[2] else "19:00"
        slot_step = clinic_row[3] if clinic_row and clinic_row[3] else 30
        working_days = _normalize_working_days(clinic_row[4] if clinic_row and len(clinic_row) > 4 else "0,1,2,3,4,5")
        address = clinic_row[5] if clinic_row and len(clinic_row) > 5 and clinic_row[5] else ""
        bot_pause_hours = 12

        cursor.execute("PRAGMA table_info(clinic_settings)")
        settings_columns = {column[1] for column in cursor.fetchall()}
        if "admin_notify_whatsapp" not in settings_columns:
            cursor.execute("ALTER TABLE clinic_settings ADD COLUMN admin_notify_whatsapp TEXT DEFAULT ''")
        if "notify_new_leads" not in settings_columns:
            cursor.execute("ALTER TABLE clinic_settings ADD COLUMN notify_new_leads INTEGER NOT NULL DEFAULT 1")
        if "notify_new_bookings" not in settings_columns:
            cursor.execute("ALTER TABLE clinic_settings ADD COLUMN notify_new_bookings INTEGER NOT NULL DEFAULT 1")
        if "notify_operator_requests" not in settings_columns:
            cursor.execute("ALTER TABLE clinic_settings ADD COLUMN notify_operator_requests INTEGER NOT NULL DEFAULT 1")
        if "whatsapp_reminders_enabled" not in settings_columns:
            cursor.execute("ALTER TABLE clinic_settings ADD COLUMN whatsapp_reminders_enabled INTEGER NOT NULL DEFAULT 1")

        cursor.execute("""
        INSERT INTO clinic_settings (
            clinic_id, work_start, work_end, slot_step_minutes, working_days,
            bot_pause_hours, clinic_name, address, admin_notify_whatsapp,
            notify_new_leads, notify_new_bookings, notify_operator_requests,
            whatsapp_reminders_enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 1, 1, 1, 1)
        """, (clinic_id, work_start, work_end, slot_step, working_days, bot_pause_hours, clinic_name, address))

        conn.commit()
        conn.close()

        return {
            "clinic_id": clinic_id,
            "work_start": work_start,
            "work_end": work_end,
            "slot_step_minutes": slot_step,
            "working_days": working_days,
            "bot_pause_hours": bot_pause_hours,
            "clinic_name": clinic_name,
            "address": address,
            "admin_notify_whatsapp": "",
            "notify_new_leads": True,
            "notify_new_bookings": True,
            "notify_operator_requests": True,
            "whatsapp_reminders_enabled": True,
        }

    conn.close()

    return {
        "clinic_id": clinic_id,
        "work_start": row[0],
        "work_end": row[1],
        "slot_step_minutes": row[2],
        "clinic_name": row[3],
        "working_days": _normalize_working_days(row[4]),
        "bot_pause_hours": row[5] or 12,
        "address": row[6] or "",
        "admin_notify_whatsapp": row[7] or "",
        "notify_new_leads": bool(row[8]),
        "notify_new_bookings": bool(row[9]),
        "notify_operator_requests": bool(row[10]),
        "whatsapp_reminders_enabled": bool(row[11]),
    }


def update_clinic_profile(clinic_name: str, address: str = "", clinic_id: int = 1) -> bool:
    try:
        clinic_id = int(clinic_id or 1)
        clinic_name = (clinic_name or "").strip() or "Клиника"
        address = (address or "").strip()
        get_clinic_settings(clinic_id)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE clinic_settings
        SET clinic_name = ?, address = ?
        WHERE clinic_id = ?
        """, (clinic_name, address, clinic_id))

        cursor.execute("""
        UPDATE clinics
        SET name = ?, address = ?
        WHERE id = ?
        """, (clinic_name, address, clinic_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR updating clinic profile: {e}")
        return False


def update_clinic_notification_settings(
    clinic_id: int = 1,
    admin_notify_whatsapp: str = "",
    notify_new_leads: bool = True,
    notify_new_bookings: bool = True,
    notify_operator_requests: bool = True,
    whatsapp_reminders_enabled: bool = True,
) -> bool:
    try:
        clinic_id = int(clinic_id or 1)
        admin_notify_whatsapp = (admin_notify_whatsapp or "").strip()
        get_clinic_settings(clinic_id)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE clinic_settings
        SET admin_notify_whatsapp = ?,
            notify_new_leads = ?,
            notify_new_bookings = ?,
            notify_operator_requests = ?,
            whatsapp_reminders_enabled = ?
        WHERE clinic_id = ?
        """, (
            admin_notify_whatsapp,
            1 if notify_new_leads else 0,
            1 if notify_new_bookings else 0,
            1 if notify_operator_requests else 0,
            1 if whatsapp_reminders_enabled else 0,
            clinic_id,
        ))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR updating notification settings: {e}")
        return False



def update_work_hours(work_start: str, work_end: str, clinic_id: int = 1) -> bool:
    try:
        clinic_id = int(clinic_id or 1)
        get_clinic_settings(clinic_id)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE clinic_settings
        SET work_start = ?, work_end = ?
        WHERE clinic_id = ?
        """, (work_start, work_end, clinic_id))

        cursor.execute("""
        UPDATE clinics
        SET work_start = ?, work_end = ?
        WHERE id = ?
        """, (work_start, work_end, clinic_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR updating work hours: {e}")
        return False


def update_slot_step(slot_step_minutes: int, clinic_id: int = 1) -> bool:
    try:
        clinic_id = int(clinic_id or 1)
        slot_step_minutes = int(slot_step_minutes)
        get_clinic_settings(clinic_id)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE clinic_settings
        SET slot_step_minutes = ?
        WHERE clinic_id = ?
        """, (slot_step_minutes, clinic_id))

        cursor.execute("""
        UPDATE clinics
        SET slot_step_minutes = ?
        WHERE id = ?
        """, (slot_step_minutes, clinic_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR updating slot step: {e}")
        return False


def update_working_days(working_days, clinic_id: int = 1) -> bool:
    try:
        clinic_id = int(clinic_id or 1)
        working_days_value = _normalize_working_days(working_days)
        get_clinic_settings(clinic_id)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE clinic_settings
        SET working_days = ?
        WHERE clinic_id = ?
        """, (working_days_value, clinic_id))

        cursor.execute("""
        UPDATE clinics
        SET working_days = ?
        WHERE id = ?
        """, (working_days_value, clinic_id))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR updating working days: {e}")
        return False


def update_bot_pause_hours(bot_pause_hours: int, clinic_id: int = 1) -> bool:
    try:
        clinic_id = int(clinic_id or 1)
        bot_pause_hours = int(bot_pause_hours)
        if bot_pause_hours not in {2, 6, 12, 24}:
            bot_pause_hours = 12
        get_clinic_settings(clinic_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE clinic_settings
        SET bot_pause_hours = ?
        WHERE clinic_id = ?
        """, (bot_pause_hours, clinic_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR updating bot pause hours: {e}")
        return False


# ========================
# Services Functions
# ========================

def get_active_services(clinic_id: int = 1) -> list:
    """
    Get all active service names for a clinic.

    Args:
        clinic_id: Clinic ID (default 1)

    Returns:
        List of service names
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT name FROM services
    WHERE clinic_id = ? AND is_active = 1
    ORDER BY sort_order ASC, name ASC
    """, (clinic_id,))

    services = [row[0] for row in cursor.fetchall()]
    conn.close()
    return services


def get_all_services(clinic_id: int = 1) -> list:
    """
    Get all services including metadata.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, name, price, duration_minutes, category, description, sort_order, is_active
    FROM services
    WHERE clinic_id = ?
    ORDER BY sort_order ASC, name ASC
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            'id': row[0],
            'name': row[1],
            'price': row[2],
            'duration_minutes': row[3] or 60,
            'category': row[4],
            'description': row[5],
            'sort_order': row[6] or 0,
            'is_active': row[7],
        }
        for row in rows
    ]


def get_service_by_name(name: str, clinic_id: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, name, price, duration_minutes, category, description, sort_order, is_active
    FROM services
    WHERE clinic_id = ? AND LOWER(name) = LOWER(?) AND is_active = 1
    LIMIT 1
    """, (clinic_id, name))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        'id': row[0],
        'name': row[1],
        'price': row[2],
        'duration_minutes': row[3] or 60,
        'category': row[4],
        'description': row[5],
        'sort_order': row[6] or 0,
        'is_active': row[7],
    }


def get_service_by_id(service_id: int, clinic_id: int = 1):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, clinic_id, name, price, duration_minutes, is_active
        FROM services
        WHERE id = ? AND clinic_id = ?
        LIMIT 1
    """, (service_id, clinic_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "clinic_id": row[1],
        "name": row[2],
        "price": row[3],
        "duration_minutes": row[4],
        "is_active": row[5],
    }
    
    


def update_service(service_id: int, name: str = None, price: int = None, duration_minutes: int = None, category: str = None, description: str = None, sort_order: int = None, is_active: int = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        updates, params = [], []

        if name is not None:
            updates.append('name = ?')
            params.append(name)
        if price is not None:
            updates.append('price = ?')
            params.append(price)
        if duration_minutes is not None:
            updates.append('duration_minutes = ?')
            params.append(duration_minutes)
        if category is not None:
            updates.append('category = ?')
            params.append(category)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        if sort_order is not None:
            updates.append('sort_order = ?')
            params.append(sort_order)
        if is_active is not None:
            updates.append('is_active = ?')
            params.append(is_active)

        if not updates:
            conn.close()
            return False

        query = f"UPDATE services SET {', '.join(updates)} WHERE id = ?"
        params.append(service_id)
        cursor.execute(query, tuple(params))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"ERROR updating service: {e}")
        return False


def add_service(name: str, price: int = None, duration_minutes: int = 60, clinic_id: int = 1, category: str = None, description: str = None, sort_order: int = 0) -> bool:
    """
    Add a new service to a clinic.

    Args:
        name: Service name
        price: Service price in tг
        duration_minutes: duration of service in minutes
        clinic_id: Clinic ID (default 1)
        category: Service category
        description: Service description
        sort_order: Sort order for display

    Returns:
        True if successful, False if service already exists
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO services (clinic_id, name, price, duration_minutes, category, description, sort_order, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (clinic_id, name, price, duration_minutes, category, description, sort_order))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR adding service: {e}")
        return False


def deactivate_service(name: str, clinic_id: int = 1) -> bool:
    """
    Deactivate a service in a clinic (soft delete).

    Args:
        name: Service name
        clinic_id: Clinic ID (default 1)

    Returns:
        True if successful, False if service not found
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE services
        SET is_active = 0
        WHERE clinic_id = ? AND name = ?
        """, (clinic_id, name))

        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"ERROR deactivating service: {e}")
        return False


# ========================
# Booking History Functions
# ========================

def get_booking_history_by_chat_id(chat_id: str) -> list:
    """
    Get all bookings for a user (active, cancelled, completed).

    Args:
        chat_id: Telegram chat ID

    Returns:
        List of booking dictionaries ordered by creation date (newest first)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at
    FROM bookings
    WHERE chat_id = ?
    ORDER BY created_at DESC
    """, (chat_id,))

    bookings = []
    for row in cursor.fetchall():
        booking = {
            "id": row[0],
            "chat_id": row[1],
            "service": row[2],
            "full_name": row[3],
            "phone": row[4],
            "appointment_at": row[5],
            "status": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }
        bookings.append(booking)

    conn.close()
    return bookings


def get_last_booking_by_chat_id(chat_id: str):
    """
    Get the most recent booking for a user (any status).

    Args:
        chat_id: Telegram chat ID

    Returns:
        Dictionary with booking data, or None if no bookings exist
    """
    bookings = get_booking_history_by_chat_id(chat_id)
    
    if bookings:
        return bookings[0]  # First one is newest (ordered DESC)
    
    return None


def count_bookings_by_chat_id(chat_id: str) -> int:
    """
    Count total bookings for a user.

    Args:
        chat_id: Telegram chat ID

    Returns:
        Number of bookings (any status)
    """
    bookings = get_booking_history_by_chat_id(chat_id)
    return len(bookings)


def is_returning_client(chat_id: str) -> bool:
    """
    Check if a user is a returning client (has at least 1 previous booking).

    Args:
        chat_id: Telegram chat ID

    Returns:
        True if user has at least 1 booking, False otherwise
    """
    count = count_bookings_by_chat_id(chat_id)
    return count > 0


# ========================
# FAQ Functions
# ========================

def add_faq_item(question: str, answer: str, clinic_id: int = 1) -> bool:
    """
    Add a new FAQ item to a clinic.

    Args:
        question: FAQ question
        answer: FAQ answer
        clinic_id: Clinic ID (default 1)

    Returns:
        True if successful, False if question already exists
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO faq_items (clinic_id, question, answer, is_active)
        VALUES (?, ?, ?, 1)
        """, (clinic_id, question, answer))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR adding FAQ item: {e}")
        return False


def remove_faq_item(question: str, clinic_id: int = 1) -> bool:
    """
    Deactivate an FAQ item in a clinic (soft delete).

    Args:
        question: FAQ question to deactivate
        clinic_id: Clinic ID (default 1)

    Returns:
        True if successful, False if question not found
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        question_value = str(question).strip()
        if question_value.isdigit():
            cursor.execute("""
            UPDATE faq_items
            SET is_active = 0
            WHERE clinic_id = ? AND id = ?
            """, (clinic_id, int(question_value)))
        else:
            cursor.execute("""
            UPDATE faq_items
            SET is_active = 0
            WHERE clinic_id = ? AND question = ?
            """, (clinic_id, question_value))

        conn.commit()
        conn.close()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"ERROR removing FAQ item: {e}")
        return False


def get_all_active_faq_items(clinic_id: int = 1) -> list:
    """
    Get all active FAQ items for a clinic.

    Args:
        clinic_id: Clinic ID (default 1)

    Returns:
        List of dictionaries with 'question' and 'answer' keys
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT question, answer FROM faq_items
    WHERE clinic_id = ? AND is_active = 1
    ORDER BY question
    """, (clinic_id,))

    faq_items = []
    for row in cursor.fetchall():
        faq_items.append({
            "question": row[0],
            "answer": row[1],
        })

    conn.close()
    return faq_items


def find_faq_answer(user_question: str, clinic_id: int = 1) -> str:
    """
    Find an FAQ answer by matching a user question to stored FAQ items.

    Uses substring matching first and then a light token-overlap heuristic so
    natural variations like "где вы находитесь" can still match "адрес клиники".
    """
    faq_items = get_all_active_faq_items(clinic_id)
    if not faq_items or not user_question:
        return None

    def normalize_text(value: str) -> str:
        value = (value or "").lower().replace("ё", "е")
        value = re.sub(r"[^a-zа-я0-9\s]", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def normalize_token(token: str) -> str:
        alias_groups = {
            "doctor": ("врач", "доктор", "стоматолог", "дантист", "dentist", "doctor"),
            "name": ("имя", "фамилия", "зовут", "surname", "name"),
            "location": ("адрес", "где", "находит", "добрат", "location", "where"),
            "schedule": ("график", "расписание", "часы", "время", "работ", "schedule", "hours"),
            "price": ("цена", "стоимость", "сколько", "стоит", "прайс", "price", "cost"),
            "service": ("услуг", "процедур", "service", "services"),
        }
        for normalized, variants in alias_groups.items():
            if any(token.startswith(variant) for variant in variants):
                return normalized
        return token

    user_normalized = normalize_text(user_question)
    user_tokens = {normalize_token(token) for token in user_normalized.split() if len(token) > 1}
    best_answer = None
    best_score = 0

    for faq in faq_items:
        faq_question = normalize_text(faq.get("question", ""))
        if not faq_question:
            continue

        if faq_question in user_normalized or user_normalized in faq_question:
            return faq.get("answer")

        faq_tokens = {normalize_token(token) for token in faq_question.split() if len(token) > 1}
        overlap = user_tokens & faq_tokens
        score = len(overlap)

        if score > best_score:
            best_score = score
            best_answer = faq.get("answer")

    return best_answer if best_score >= 2 or (best_score >= 1 and len(user_tokens) <= 3) else None


# ========================
# Admin Panel Data Functions (for future web dashboard)
# ========================

def get_today_bookings(clinic_id: int = 1) -> list:
    """
    Get all active bookings for today in a clinic.
    
    For future admin panel use.

    Args:
        clinic_id: Clinic ID (default 1)

    Returns:
        List of booking dictionaries ordered by time
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.now().date().isoformat()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at, clinic_id
    FROM bookings
    WHERE clinic_id = ? AND status = 'active' AND appointment_at LIKE ?
    ORDER BY appointment_at ASC
    """, (clinic_id, today + "%"))

    bookings = []
    for row in cursor.fetchall():
        booking = {
            "id": row[0],
            "chat_id": row[1],
            "service": row[2],
            "full_name": row[3],
            "phone": row[4],
            "appointment_at": row[5],
            "status": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "clinic_id": row[9],
        }
        bookings.append(booking)

    conn.close()
    return bookings


def get_upcoming_bookings(clinic_id: int = 1, days_ahead: int = 30) -> list:
    """
    Get all active bookings for next N days in a clinic.
    
    For future admin panel use.

    Args:
        clinic_id: Clinic ID (default 1)
        days_ahead: Number of days ahead to look (default 30)

    Returns:
        List of booking dictionaries ordered by date and time
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    today = datetime.now().date()
    future_date = (today + timedelta(days=days_ahead)).isoformat()
    today_str = today.isoformat()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at, clinic_id
    FROM bookings
    WHERE clinic_id = ? AND status = 'active' 
    AND appointment_at >= ? AND appointment_at < ?
    ORDER BY appointment_at ASC
    """, (clinic_id, today_str, future_date))

    bookings = []
    for row in cursor.fetchall():
        booking = {
            "id": row[0],
            "chat_id": row[1],
            "service": row[2],
            "full_name": row[3],
            "phone": row[4],
            "appointment_at": row[5],
            "status": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "clinic_id": row[9],
        }
        bookings.append(booking)

    conn.close()
    return bookings


def get_clinic_active_bookings(clinic_id: int = 1) -> list:
    """
    Get all active bookings in a clinic (no date filter).
    
    For future admin panel use.

    Args:
        clinic_id: Clinic ID (default 1)

    Returns:
        List of active booking dictionaries ordered by appointment time
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, chat_id, service, full_name, phone, appointment_at, status, created_at, updated_at, clinic_id
    FROM bookings
    WHERE clinic_id = ? AND status = 'active'
    ORDER BY appointment_at ASC
    """, (clinic_id,))

    bookings = []
    for row in cursor.fetchall():
        booking = {
            "id": row[0],
            "chat_id": row[1],
            "service": row[2],
            "full_name": row[3],
            "phone": row[4],
            "appointment_at": row[5],
            "status": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "clinic_id": row[9],
        }
        bookings.append(booking)

    conn.close()
    return bookings


def get_all_active_services(clinic_id: int = 1) -> list:
    """Return active services with IDs for admin table view."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, name, price, duration_minutes FROM services
        WHERE clinic_id = ? AND is_active = 1
        ORDER BY name
        """,
        (clinic_id,),
    )

    services = []
    for row in cursor.fetchall():
        services.append({
            "id": row[0],
            "name": row[1],
            "price": row[2],
            "duration_minutes": row[3] or 60,
        })

    conn.close()
    return services


def deactivate_service_by_id(service_id: int) -> bool:
    """Deactivate a service by its ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE services
            SET is_active = 0
            WHERE id = ?
            """,
            (service_id,),
        )
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success
    except Exception as e:
        print(f"ERROR deactivate_service_by_id: {e}")
        return False


def get_all_active_faq_items(clinic_id: int = 1) -> list:
    """
    Get all active FAQ items for a clinic.

    Args:
        clinic_id: Clinic ID (default 1)

    Returns:
        List of dictionaries with 'id', 'question' and 'answer' keys
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, question, answer FROM faq_items
    WHERE clinic_id = ? AND is_active = 1
    ORDER BY question
    """, (clinic_id,))

    faq_items = []
    for row in cursor.fetchall():
        faq_items.append({
            "id": row[0],
            "question": row[1],
            "answer": row[2],
        })

    conn.close()
    return faq_items



    conn.close()


def get_conversations_needing_operator(clinic_id: int = 1) -> list:
    return get_operator_inbox(clinic_id)


def close_conversation(conversation_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        "UPDATE conversations SET status = 'closed', needs_operator = 0, follow_up_sent = 1, updated_at = ? WHERE id = ?",
        (now, conversation_id),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed


# ========================
# Message History Functions
# ========================

def get_conversation_by_id(conversation_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, clinic_id, chat_id, full_name, phone, last_user_message, last_bot_reply,
           status, needs_operator, has_booking, is_lost, created_at, updated_at,
           bot_paused_until,
           (
               SELECT sender_type FROM messages m
               WHERE m.conversation_id = conversations.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_sender_type,
           (
               SELECT text FROM messages m
               WHERE m.conversation_id = conversations.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message,
           (
               SELECT created_at FROM messages m
               WHERE m.conversation_id = conversations.id AND COALESCE(TRIM(m.text), '') <> ''
               ORDER BY datetime(m.created_at) DESC, m.id DESC
               LIMIT 1
           ) AS latest_message_at
    FROM conversations WHERE id = ?
    """, (conversation_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "clinic_id": row[1], "chat_id": row[2],
        "full_name": row[3], "phone": row[4],
        "last_user_message": row[5], "last_bot_reply": row[6],
        "status": row[7], "needs_operator": row[8],
        "has_booking": row[9], "is_lost": row[10],
        "created_at": row[11], "updated_at": row[12],
        "bot_paused_until": row[13],
        "latest_sender_type": row[14] or ("user" if row[5] else "bot" if row[6] else ""),
        "latest_message": row[15] or row[5] or row[6] or "",
        "latest_message_at": row[16] or row[12],
        "last_activity_at": row[16] or row[12],
    }


def store_message(conversation_id: int, chat_id: str, sender_type: str, text: str):
    """Store a message in the messages table. sender_type: user | bot | operator"""
    try:
        message_text = _normalize_crm_text(text)
        if not conversation_id or not message_text:
            return

        normalized_sender = _normalize_crm_text(sender_type).lower()
        if normalized_sender not in _VALID_MESSAGE_SENDER_TYPES:
            normalized_sender = "user"

        normalized_chat_id = _normalize_crm_text(chat_id)
        now = datetime.now().isoformat()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO messages (conversation_id, chat_id, sender_type, text, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (conversation_id, normalized_chat_id, normalized_sender, message_text, now))

        if normalized_sender == "user":
            cursor.execute(
                "UPDATE conversations SET last_user_message = ?, updated_at = ? WHERE id = ?",
                (message_text, now, conversation_id),
            )
        else:
            bot_preview = f"[Оператор] {message_text}" if normalized_sender == "operator" else message_text
            cursor.execute(
                "UPDATE conversations SET last_bot_reply = ?, updated_at = ? WHERE id = ?",
                (bot_preview, now, conversation_id),
            )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"ERROR store_message: {e}")


def get_messages_by_conversation(conversation_id: int, limit: int = 100) -> list:
    """Return messages for a conversation ordered by time ascending."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT id, conversation_id, chat_id, sender_type, text, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
        LIMIT ?
        """, (conversation_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "conversation_id": r[1], "chat_id": r[2],
                "sender_type": r[3], "text": r[4], "created_at": r[5],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"ERROR get_messages_by_conversation: {e}")
        return []
    
    
    
def add_doctor(full_name: str, profession: str, clinic_id: int = 1) -> bool:
    full_name = (full_name or "").strip()
    profession = (profession or "").strip().lower()

    if not full_name or not profession:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    cursor.execute("""
    INSERT INTO doctors (clinic_id, full_name, profession, is_active, created_at, updated_at)
    VALUES (?, ?, ?, 1, ?, ?)
    """, (clinic_id, full_name, profession, now, now))

    conn.commit()
    conn.close()
    return True


def get_active_doctors(clinic_id: int = 1) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, clinic_id, full_name, profession, is_active
    FROM doctors
    WHERE clinic_id = ? AND is_active = 1
    ORDER BY full_name
    """, (clinic_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "clinic_id": row[1],
            "full_name": row[2],
            "profession": row[3],
            "is_active": row[4],
        }
        for row in rows
    ]


def get_doctors_by_profession(profession: str, clinic_id: int = 1) -> list:
    profession = (profession or "").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, clinic_id, full_name, profession, is_active
    FROM doctors
    WHERE clinic_id = ? AND is_active = 1 AND LOWER(profession) LIKE ?
    ORDER BY full_name
    """, (clinic_id, f"%{profession}%"))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "clinic_id": row[1],
            "full_name": row[2],
            "profession": row[3],
            "is_active": row[4],
        }
        for row in rows
    ]


def check_doctor_available(doctor_id: int, clinic_id: int, appointment_at: str, duration_minutes: int = 60) -> bool:
    try:
        start = datetime.fromisoformat(appointment_at)
        end = start + timedelta(minutes=duration_minutes)
    except Exception:
        return False

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT appointment_at, duration_minutes
    FROM bookings
    WHERE clinic_id = ?
      AND doctor_id = ?
      AND status = 'active'
    """, (clinic_id, doctor_id))

    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        existing_start = datetime.fromisoformat(row[0])
        existing_end = existing_start + timedelta(minutes=row[1] or 60)

        if start < existing_end and end > existing_start:
            return False

    return True


def find_available_doctor(clinic_id: int, profession: str, appointment_at: str, duration_minutes: int = 60):
    doctors = get_doctors_by_profession(profession, clinic_id)

    for doctor in doctors:
        if check_doctor_available(doctor["id"], clinic_id, appointment_at, duration_minutes):
            return doctor

    return None

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


def _get_slot_issue_message(appointment_at: str, clinic_id: int, duration: int, exclude_booking_id: int | None = None) -> tuple[str, str, list[str]]:
    """Build a human-friendly message for unavailable or invalid slots."""
    if not is_within_working_hours(appointment_at, clinic_id, duration):
        settings = get_clinic_settings()
        return (
            get_outside_working_hours_response(
                settings.get("work_start", "10:00"),
                settings.get("work_end", "19:00"),
            ),
            "outside_hours",
            [],
        )

    alternatives = find_alternative_slots(
        appointment_at,
        clinic_id,
        duration_minutes=duration,
        exclude_booking_id=exclude_booking_id,
    )
    if alternatives:
        alt_lines = "\n".join(
            [f"{i + 1}. {format_slot_for_display(slot)}" for i, slot in enumerate(alternatives)]
        )
        return get_slot_unavailable_message(alt_lines), "slot_taken", alternatives

    return get_no_alternatives_message(), "slot_taken", []

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

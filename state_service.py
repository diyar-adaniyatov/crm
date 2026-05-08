from database import get_db_connection
import traceback


def _normalize_chat_id(chat_id) -> str:
    return str(chat_id).strip() if chat_id is not None else ""


def _coerce_state(state: dict | None) -> dict:
    defaults = get_empty_state()
    safe_state = defaults.copy()
    if isinstance(state, dict):
        for key, default_value in defaults.items():
            value = state.get(key, default_value)
            safe_state[key] = default_value if value is None else value
    return safe_state


def get_empty_state():
    return {
        "service": "",
        "full_name": "",
        "phone": "",
        "preferred_datetime": "",
        "status": "collecting",
        "next_field": "service",
        "booking_status": "in_progress",
        "intent": "booking",
    }


def validate_state_consistency(state: dict) -> bool:
    """
    Validate that the state dictionary has all required keys and valid values.
    Returns True if state is valid, False otherwise.
    """
    required_keys = ["service", "full_name", "phone", "preferred_datetime", "status", "next_field", "booking_status", "intent"]

    # Check all required keys exist
    for key in required_keys:
        if key not in state:
            print(f"ERROR: State missing required key: {key}")
            return False

    # Validate status values
    valid_statuses = ["collecting", "ready_to_book", "booked", "cancelled"]
    if state.get("status", "") not in valid_statuses:
        print(f"ERROR: Invalid status value: {state.get('status')}")
        return False

    # Validate intent values
    valid_intents = ["booking", "question", "operator", "greeting", "cancel", "reschedule", "unknown"]
    if state.get("intent", "") not in valid_intents:
        print(f"ERROR: Invalid intent value: {state.get('intent')}")
        return False

    # Validate booking_status values
    valid_booking_statuses = ["in_progress", "confirmed", "cancelled", "completed"]
    if state.get("booking_status", "") not in valid_booking_statuses:
        print(f"ERROR: Invalid booking_status value: {state.get('booking_status')}")
        return False

    return True


def get_user_state(chat_id: str):
    try:
        normalized_chat_id = _normalize_chat_id(chat_id)
        if not normalized_chat_id:
            return get_empty_state()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT service, full_name, phone, preferred_datetime, status, next_field, booking_status, intent
        FROM user_state
        WHERE chat_id = ?
        """, (normalized_chat_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            print(f"DEBUG: No state found for chat_id {normalized_chat_id}, returning empty state")
            return get_empty_state()

        state = _coerce_state({
            "service": row[0] or "",
            "full_name": row[1] or "",
            "phone": row[2] or "",
            "preferred_datetime": row[3] or "",
            "status": row[4] or "collecting",
            "next_field": row[5] or "service",
            "booking_status": row[6] or "in_progress",
            "intent": row[7] or "booking",
        })

        # Validate state consistency
        if not validate_state_consistency(state):
            print(f"ERROR: Invalid state retrieved for chat_id {chat_id}, resetting to empty state")
            return get_empty_state()

        print(f"DEBUG: Retrieved valid state for chat_id {chat_id}")
        return state

    except Exception as e:
        print(f"ERROR: Failed to get user state for chat_id {chat_id}: {repr(e)}")
        traceback.print_exc()
        return get_empty_state()


def save_user_state(chat_id: str, state: dict):
    try:
        normalized_chat_id = _normalize_chat_id(chat_id)
        safe_state = _coerce_state(state)
        if not normalized_chat_id:
            return False

        # Validate state before saving
        if not validate_state_consistency(safe_state):
            print(f"ERROR: Attempted to save invalid state for chat_id {normalized_chat_id}: {safe_state}")
            return False

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO user_state (
            chat_id, service, full_name, phone, preferred_datetime,
            status, next_field, booking_status, intent
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            service = excluded.service,
            full_name = excluded.full_name,
            phone = excluded.phone,
            preferred_datetime = excluded.preferred_datetime,
            status = excluded.status,
            next_field = excluded.next_field,
            booking_status = excluded.booking_status,
            intent = excluded.intent
        """, (
            normalized_chat_id,
            safe_state.get("service", ""),
            safe_state.get("full_name", ""),
            safe_state.get("phone", ""),
            safe_state.get("preferred_datetime", ""),
            safe_state.get("status", "collecting"),
            safe_state.get("next_field", "service"),
            safe_state.get("booking_status", "in_progress"),
            safe_state.get("intent", "booking"),
        ))

        conn.commit()
        conn.close()
        print(f"DEBUG: Successfully saved state for chat_id {normalized_chat_id}")
        return True

    except Exception as e:
        print(f"ERROR: Failed to save user state for chat_id {chat_id}: {repr(e)}")
        traceback.print_exc()
        return False


def reset_user_state(chat_id: str):
    try:
        result = save_user_state(chat_id, get_empty_state())
        if result:
            print(f"DEBUG: Successfully reset state for chat_id {chat_id}")
        else:
            print(f"ERROR: Failed to reset state for chat_id {chat_id}")
        return result
    except Exception as e:
        print(f"ERROR: Exception during state reset for chat_id {chat_id}: {repr(e)}")
        traceback.print_exc()
        return False

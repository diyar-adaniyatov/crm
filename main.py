import code
import email
from email import message
import html
import os
import re
import ssl
import json
import hmac
import secrets
import hashlib
import logging
import token
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import asyncio
import traceback
import uvicorn
import os
import smtplib
import uuid
import sqlite3
from datetime import datetime, timedelta
import urllib.request
import random
import requests
from urllib.parse import quote as urlquote
from email.mime.text import MIMEText
from email.header import Header
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from database import add_clinic_channel


from database import get_clinic_id_by_channel, add_clinic_channel, get_channel_by_key

from database import init_auth_db, get_db_connection

init_auth_db()


try:
    import certifi
except Exception:
    certifi = None
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from database import init_db
init_db()
from state_service import get_user_state, save_user_state, reset_user_state
from ai_parser import parse_user_message, is_greeting_message
from human_responses import (
    get_greeting, get_personalized_greeting, get_returning_client_greeting,
    get_service_question, get_name_question, get_phone_question,
    get_datetime_question, get_booking_confirmation, get_reschedule_offer,
    get_slot_unavailable_message, get_no_alternatives_message, get_missing_info_message,
    get_price_response, get_price_not_available_response, get_services_list_response,
    get_price_overview_response, get_info_missing_response,
    get_faq_response, get_forward_to_admin_response, get_operator_request_response,
    get_error_response, get_clarifying_question, get_reset_success_response, get_reset_error_response,
    get_no_active_booking_response, get_no_services_response, get_no_bookings_response,
    get_reschedule_confirmation, get_thanks_response, get_booking_already_exists_response,
)
from booking_service import (
    get_doctor_by_id, update_doctor, deactivate_doctor, add_doctor, get_active_doctors,get_service_by_id, create_or_update_booking, get_active_booking_by_chat_id, get_booking_by_id, confirm_booking_by_id, update_booking, get_clinic_active_bookings,
    format_booking_for_display, format_slot_for_display, format_phone_for_display, cancel_active_booking_by_chat_id,
    reschedule_booking_by_chat_id,
    get_service_duration, check_slot_available, find_alternative_slots, get_slot_issue_message,
    cancel_booking_by_id, mark_booking_completed, mark_booking_no_show, mark_reminder_24h_sent, mark_reminder_2h_sent, get_bookings_needing_24h_reminder,
    get_bookings_needing_2h_reminder, get_bookings_by_status, get_clinic_settings, update_work_hours, update_slot_step, update_working_days, update_bot_pause_hours, update_clinic_profile, update_clinic_notification_settings, update_clinic_ui_settings,
    get_active_services, get_all_active_services, get_all_services, get_service_by_name, add_service, update_service, deactivate_service, deactivate_service_by_id, add_faq_item, remove_faq_item,
    get_all_active_faq_items, find_faq_answer, get_booking_history_by_chat_id, is_returning_client,
    get_default_clinic, assign_user_to_clinic, get_clinic_by_chat_id,
    get_today_bookings, get_upcoming_bookings,
    get_conversation_by_chat_id, get_or_create_conversation, upsert_conversation,
    update_conversation_from_user_message, update_conversation_bot_reply, mark_conversation_waiting_operator, mark_conversation_booked, mark_conversation_lost,
    get_operator_inbox, get_leads_without_booking, get_all_conversations, get_lost_conversations, clear_conversation_operator_flag,
    close_conversation, get_conversations_needing_followup, mark_followup_sent,
    get_conversation_by_id, store_message, get_messages_by_conversation,
)

RESET_LIMIT = {}
EMAIL_VERIFY_CODES = {}
ADMIN_CHAT_WARNING_SHOWN = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
    file_handler = RotatingFileHandler("bot_actions.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)
load_dotenv()

# =========================
# API KEYS / ADMIN AUTH CONFIG
# =========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENV") or "development").strip().lower()
ADMIN_USERNAME = (os.getenv("ADMIN_USERNAME") or "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") or ""
ADMIN_PASSWORD_HASH = (os.getenv("ADMIN_PASSWORD_HASH") or "").strip()
ADMIN_SESSION_SECRET = (os.getenv("ADMIN_SESSION_SECRET") or os.getenv("SESSION_SECRET") or "").strip()
PLATFORM_ROOT_EMAIL = "adaniyatov.diyar@gmail.com"

if not ADMIN_SESSION_SECRET:
    ADMIN_SESSION_SECRET = secrets.token_urlsafe(32)
    logger.warning("ADMIN_SESSION_SECRET is missing; using an ephemeral local-only session secret. Set it in .env for persistent admin sessions.")


from passlib.hash import pbkdf2_sha256


def admin_auth_configured() -> bool:
    if ADMIN_USERNAME and (ADMIN_PASSWORD or ADMIN_PASSWORD_HASH):
        return True
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def hash_admin_password(password):
    return pbkdf2_sha256.hash(password)

def verify_admin_password(password, stored_hash=None):
    if stored_hash:
        try:
            return pbkdf2_sha256.verify(password, stored_hash)
        except ValueError:
            return False

    if ADMIN_PASSWORD_HASH:
        try:
            return pbkdf2_sha256.verify(password, ADMIN_PASSWORD_HASH)
        except ValueError:
            return False

    if ADMIN_PASSWORD:
        return hmac.compare_digest(password or "", ADMIN_PASSWORD)

    return False


def ensure_env_admin_user() -> None:
    if not ADMIN_USERNAME or not (ADMIN_PASSWORD or ADMIN_PASSWORD_HASH):
        return

    password_hash = ADMIN_PASSWORD_HASH or hash_admin_password(ADMIN_PASSWORD)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (ADMIN_USERNAME,))
        if cursor.fetchone():
            conn.close()
            return

        cursor.execute("SELECT id FROM clinics WHERE id = 1")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO clinics (id, name) VALUES (1, ?)", ("Клиника",))

        cursor.execute(
            "INSERT INTO users (email, password_hash, clinic_id) VALUES (?, ?, 1)",
            (ADMIN_USERNAME, password_hash),
        )
        conn.commit()
        conn.close()
        logger.info("Created admin user from ADMIN_USERNAME in .env")
    except Exception as e:
        logger.warning("Could not create admin user from .env: %s", e)


ensure_env_admin_user()



def get_safe_next_path(next_path: str | None) -> str:
    candidate = (next_path or "/admin/react").strip()
    if not candidate.startswith("/admin") or candidate.startswith("//"):
        return "/admin/react"
    if candidate == "/admin":
        return "/admin/react"
    return candidate


def is_admin_authenticated(request: Request) -> bool:
    return bool(request.session.get("is_admin") is True)


def get_react_admin_redirect_path(path: str, method: str = "GET") -> str | None:
    if method.upper() != "GET":
        return None

    if not path.startswith("/admin"):
        return None

    if path.startswith("/admin/react") or path.startswith("/admin/assets") or path.startswith("/admin/api"):
        return None

    section_map = {
        "/admin/today": "bookings",
        "/admin/upcoming": "bookings",
        "/admin/bookings": "bookings",
        "/admin/inbox": "conversations",
        "/admin/leads": "conversations",
        "/admin/conversations": "conversations",
        "/admin/settings": "settings",
        "/admin/channels": "settings",
        "/admin/metrics": "dashboard",
        "/admin": "dashboard",
    }

    for legacy_path, section in section_map.items():
        if path == legacy_path or path.startswith(legacy_path + "/"):
            return f"/admin/react#{section}"

    return "/admin/react"


async def send_telegram_text(chat_id: int | str, text: str) -> bool:
    """Send a Telegram message directly via Telegram HTTP API.

    FastAPI stays independent from the bot polling process.
    """
    token = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        logger.warning("TELEGRAM_TOKEN is missing; Telegram message was not sent.")
        return False

    chat_id_value = str(chat_id).strip()
    safe_text = (text or "").strip()
    if not chat_id_value or not chat_id_value.lstrip("-").isdigit():
        logger.warning("Telegram message skipped for invalid chat_id=%r", chat_id)
        return False
    if not safe_text:
        logger.warning("Telegram message skipped because text is empty for chat_id=%s", chat_id_value)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id_value, "text": safe_text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    def _build_ssl_context(allow_insecure: bool = False):
        if allow_insecure:
            return ssl._create_unverified_context()
        if certifi is not None:
            return ssl.create_default_context(cafile=certifi.where())
        return ssl.create_default_context()

    def _send_request(allow_insecure: bool = False):
        ssl_context = _build_ssl_context(allow_insecure=allow_insecure)
        with urllib.request.urlopen(req, timeout=15, context=ssl_context) as response:
            return response.read()

    try:
        await asyncio.to_thread(_send_request, False)
        logger.info("[TG] Delivered message to chat_id=%s", chat_id_value)
        return True
    except ssl.SSLError as e:
        if APP_ENV != "production":
            logger.warning("Telegram SSL verification failed for chat_id=%s, retrying with local fallback: %s", chat_id_value, e)
            try:
                await asyncio.to_thread(_send_request, True)
                logger.info("[TG] Delivered message to chat_id=%s via fallback SSL context", chat_id_value)
                return True
            except Exception as retry_error:
                logger.exception("Telegram send failed after SSL fallback chat_id=%s: %s", chat_id_value, retry_error)
                traceback.print_exc()
                return False
        logger.exception("Telegram send failed chat_id=%s: %s", chat_id_value, e)
        traceback.print_exc()
        return False
    except Exception as e:
        logger.exception("Telegram send failed chat_id=%s: %s", chat_id_value, e)
        traceback.print_exc()
        return False


def get_admin_telegram_chat_ids() -> set[str]:
    raw_values = [
        os.getenv("ADMIN_TELEGRAM_CHAT_ID", ""),
        os.getenv("ADMIN_TELEGRAM_CHAT_IDS", ""),
        os.getenv("ADMIN_CHAT_ID", ""),
        os.getenv("ADMIN_CHAT_IDS", ""),
    ]
    result = set()
    for raw in raw_values:
        for item in re.split(r"[,;\s]+", raw or ""):
            item = item.strip()
            if item and item.lstrip("-").isdigit():
                result.add(item)
    return result


def is_admin_chat_id(chat_id: str) -> bool:
    global ADMIN_CHAT_WARNING_SHOWN
    allowed_ids = get_admin_telegram_chat_ids()
    if not allowed_ids:
        if not ADMIN_CHAT_WARNING_SHOWN:
            logger.warning("ADMIN_TELEGRAM_CHAT_ID is not set; Telegram admin commands are open for backward compatibility.")
            ADMIN_CHAT_WARNING_SHOWN = True
        return True
    return str(chat_id).strip() in allowed_ids


async def require_admin_chat(update: Update) -> bool:
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    if is_admin_chat_id(chat_id):
        return True
    await update.message.reply_text("Эта команда доступна только администратору.")
    logger.warning("Blocked Telegram admin command from chat_id=%s", chat_id)
    return False


async def notify_admins(text: str) -> None:
    admin_chat_ids = get_admin_telegram_chat_ids()
    if not admin_chat_ids:
        logger.info("Admin notification skipped: ADMIN_TELEGRAM_CHAT_ID is not configured.")
        return

    for admin_chat_id in admin_chat_ids:
        try:
            await send_telegram_text(admin_chat_id, text)
        except Exception as e:
            logger.warning("Admin notification failed for chat_id=%s: %s", admin_chat_id, e)


def get_main_menu_markup(flow_state: str = "idle"):
    rows = [
        ["Записаться", "Моя запись"],
        ["Отменить запись", "Услуги"],
        ["История", "Помощь"],
    ]

    if flow_state in {"booking_confirmation", "reschedule_confirmation"}:
        rows = [
            ["Да, подтверждаю", "Изменить время"],
            ["Отменить запись", "Моя запись"],
        ]
    elif flow_state == "cancel_flow":
        rows = [
            ["Да, отменить", "Нет, оставить"],
            ["Моя запись", "Помощь"],
        ]

    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


def get_public_help_text() -> str:
    return (
        "Я могу помочь с записью, переносом и отменой визита.\n\n"
        "Доступно:\n"
        "/start - главное меню\n"
        "/mybooking - текущая запись\n"
        "/history - история записей\n"
        "/cancelbooking - отменить запись\n"
        "/services - список услуг\n\n"
        "Можно писать обычным текстом: например, «хочу записаться на чистку завтра в 15:00»."
    )


def get_admin_help_text() -> str:
    return (
        "Админ-команды:\n"
        "/bookings - все активные записи\n"
        "/today - записи на сегодня\n"
        "/upcoming - ближайшие записи\n"
        "/confirmbooking <id> - подтвердить запись\n"
        "/rejectbooking <id> [причина] - отклонить запись\n"
        "/editbooking <id> <YYYY-MM-DD HH:MM> [услуга] - изменить время и при необходимости услугу\n"
        "/deletebooking <id> - удалить запись через отмену\n"
        "/addservice <название> - добавить услугу\n"
        "/removeservice <название> - отключить услугу\n"
        "/sethours <HH:MM> <HH:MM> - часы работы\n"
        "/setslotstep <минуты> - шаг записи\n"
        "/addfaq <вопрос> | <ответ> - добавить FAQ\n"
        "/removefaq <вопрос> - удалить FAQ"
    )


def is_menu_request(text: str, aliases: set[str]) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").lower().replace("ё", "е")).strip()
    return normalized in aliases


def build_user_booking_text(booking: dict) -> str:
    if not booking:
        return get_no_bookings_response()

    service = booking.get("service") or "визит"
    full_name = booking.get("full_name") or "Клиент"
    phone = format_phone_for_display(booking.get("phone", ""))
    appointment_at = booking.get("appointment_at") or ""
    appointment_display = format_slot_for_display(appointment_at) if appointment_at else "время не указано"

    return (
        "Ваша актуальная запись:\n\n"
        f"Услуга: {service}\n"
        f"Дата и время: {appointment_display}\n"
        f"Имя: {full_name}\n"
        f"Телефон: {phone}\n\n"
        "Если нужно изменить время, напишите новое время или нажмите «Отменить запись»."
    )


def build_booking_history_text(chat_id: str) -> str:
    bookings = get_booking_history_by_chat_id(chat_id)
    if not bookings:
        return "У вас пока нет истории записей. Когда запись появится, я покажу ее здесь."

    status_map = {
        "active": "активна",
        "cancelled": "отменена",
        "completed": "завершена",
        "no_show": "не пришел",
        "pending": "ожидает подтверждения",
        "pending_admin": "ожидает подтверждения",
    }

    lines = []
    for booking in bookings[:10]:
        appointment_at = booking.get("appointment_at") or ""
        appointment_display = format_slot_for_display(appointment_at) if appointment_at else "время не указано"
        lines.append(
            f"ID {booking.get('id', '?')}: {booking.get('service') or 'визит'}\n"
            f"Время: {appointment_display}\n"
            f"Статус: {status_map.get(booking.get('status'), booking.get('status', ''))}"
        )

    return "История ваших записей:\n\n" + "\n\n".join(lines)


def build_admin_booking_notification(event: str, booking: dict | None = None, payload: dict | None = None) -> str:
    data = dict(booking or {})
    if payload:
        data.update({k: v for k, v in payload.items() if v})

    appointment_at = data.get("appointment_at") or data.get("preferred_datetime") or ""
    appointment_display = format_slot_for_display(appointment_at) if appointment_at else "не указано"
    booking_id = data.get("id") or data.get("booking_id") or "новая"

    return (
        f"{event}\n"
        f"ID: {booking_id}\n"
        f"Клиент: {data.get('full_name') or 'Клиент'}\n"
        f"Телефон: {format_phone_for_display(data.get('phone', ''))}\n"
        f"Услуга: {data.get('service') or 'не указана'}\n"
        f"Время: {appointment_display}\n"
        f"Chat ID: {data.get('chat_id') or ''}"
    )

class AdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        protected_paths = path.startswith("/admin") or path in {"/logout", "/change-password"}
        if protected_paths and not is_admin_authenticated(request):

            next_path = get_safe_next_path(path)
            if request.url.query:
                next_path = f"{next_path}?{request.url.query}"
            return RedirectResponse(url=f"/login?next={urlquote(next_path, safe='/?=&')}", status_code=303)

        react_redirect = get_react_admin_redirect_path(path, request.method)
        if react_redirect:
            return RedirectResponse(url=react_redirect, status_code=303)

        response = await call_next(request)
        if path.startswith("/admin") or path in {"/login", "/logout"}:
            response.headers["Cache-Control"] = "no-store"
        return response


# =========================
# FastAPI App
# =========================
app = FastAPI()
app.add_middleware(AdminAuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=ADMIN_SESSION_SECRET,
    session_cookie="ai_booking_admin_session",
    same_site="lax",
    https_only=APP_ENV in {"prod", "production"},
    max_age=60 * 60 * 12,
)

def get_admin_frontend_candidates() -> list[str]:
    module_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.path.abspath(os.getcwd())
    roots = [module_dir, cwd, os.path.dirname(module_dir)]
    candidates = []

    for root in roots:
        candidate = os.path.abspath(os.path.join(root, "admin_frontend"))
        if candidate not in candidates:
            candidates.append(candidate)

    return candidates


def resolve_admin_frontend_dir() -> str:
    candidates = get_admin_frontend_candidates()

    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "index.html")):
            return candidate

    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate

    return candidates[0]


def get_admin_frontend_file(asset_path: str) -> str | None:
    frontend_dir = os.path.abspath(resolve_admin_frontend_dir())
    file_path = os.path.abspath(os.path.join(frontend_dir, asset_path))

    if file_path != frontend_dir and not file_path.startswith(frontend_dir + os.sep):
        return None

    if not os.path.isfile(file_path):
        return None

    return file_path


def render_admin_frontend_missing() -> str:
    searched = "".join(
        f"<li><code>{html.escape(os.path.join(path, 'index.html'))}</code></li>"
        for path in get_admin_frontend_candidates()
    )
    return f"""
    <div class='empty' style='text-align:left;'>
        <p><b>React-интерфейс не найден на сервере.</b></p>
        <p style='margin-top:10px;'>Backend работает, но папка <code>admin_frontend</code> не попала на VDS или лежит не рядом с <code>main.py</code>.</p>
        <p style='margin-top:10px;'>Сервер искал файл здесь:</p>
        <ul style='margin:10px 0 0 18px; line-height:1.8;'>{searched}</ul>
        <p style='margin-top:14px;'>Скопируйте на VDS всю папку <code>admin_frontend</code> с файлами <code>index.html</code>, <code>app.js</code>, <code>styles.css</code> и перезапустите сервер.</p>
    </div>
    """


ADMIN_FRONTEND_DIR = resolve_admin_frontend_dir()


@app.get("/admin/assets/{asset_path:path}")
async def admin_frontend_asset(asset_path: str):
    asset_file = get_admin_frontend_file(asset_path)
    if not asset_file:
        return HTMLResponse("Admin frontend asset not found", status_code=404)
    return FileResponse(asset_file)

# =========================
# Web Admin Routes
# =========================

@app.post("/change-password")
async def change_password(request: Request):
    global ADMIN_PASSWORD_HASH, ADMIN_PASSWORD

    data = await request.json()

    old_password = (data.get("old_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not old_password or not new_password:
        return {"error": "Введите старый и новый пароль"}

    if len(new_password) < 6:
        return {"error": "Новый пароль должен быть минимум 6 символов"}

    stored_hash = ADMIN_PASSWORD_HASH
    session_user_id = request.session.get("user_id")
    if session_user_id:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE id = ?", (session_user_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                stored_hash = row[0]
        except Exception as e:
            logger.warning("Could not load current admin password hash: %s", e)

    if not verify_admin_password(old_password, stored_hash):
        return {"error": "Неверный старый пароль"}

    new_hash = hash_admin_password(new_password)

    env_path = ".env"

    try:
        lines = []
        found_hash = False
        found_plain = False

        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        new_lines = []

        for line in lines:
            if line.startswith("ADMIN_PASSWORD_HASH="):
                new_lines.append(f"ADMIN_PASSWORD_HASH={new_hash}\n")
                found_hash = True
            elif line.startswith("ADMIN_PASSWORD="):
                new_lines.append("ADMIN_PASSWORD=\n")
                found_plain = True
            else:
                new_lines.append(line)

        if not found_hash:
            new_lines.append(f"\nADMIN_PASSWORD_HASH={new_hash}\n")

        if not found_plain:
            new_lines.append("ADMIN_PASSWORD=\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        if session_user_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, session_user_id))
            conn.commit()
            conn.close()

        ADMIN_PASSWORD_HASH = new_hash
        ADMIN_PASSWORD = ""

        request.session.clear()

        return {
            "message": "Пароль изменён. Войдите заново с новым паролем."
        }

    except Exception as e:
        return {"error": f"Не удалось сохранить пароль: {str(e)}"}

def format_admin_datetime(dt_value: str) -> str:
    """Format updated_at/created_at for compact Russian-friendly admin display."""
    if not dt_value or dt_value == "—":
        return "—"

    if isinstance(dt_value, datetime):
        dt = dt_value
    else:
        dt_str = str(dt_value).strip()
        if "." in dt_str:
            dt_str = dt_str.split(".")[0]
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1]

        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%d.%m.%Y %H:%M"):
            try:
                parsed = datetime.strptime(dt_str, fmt)
                break
            except Exception:
                pass

        if parsed is None:
            # keep fallback text if parsing fails
            return dt_str

        dt = parsed

    return f"{dt.day:02d}.{dt.month:02d}.{dt.year} {dt.hour:02d}:{dt.minute:02d}"


def get_conversation_message_preview(item: dict, limit: int = 70) -> str:
    text = (item.get("latest_message") or item.get("last_user_message") or item.get("last_bot_reply") or "").strip()
    if not text:
        return "—"

    sender = (item.get("latest_sender_type") or "").strip().lower()
    sender_labels = {
        "user": "Клиент",
        "bot": "Бот",
        "operator": "Оператор",
    }
    label = sender_labels.get(sender)

    if label:
        if sender == "operator" and not text.startswith("[Оператор]"):
            text = f"Оператор: {text}"
        elif sender == "user" and not text.lower().startswith("клиент:"):
            text = f"Клиент: {text}"
        elif sender == "bot" and not text.lower().startswith("бот:"):
            text = f"Бот: {text}"

    if len(text) > limit:
        return text[:limit - 3] + "..."
    return text


def get_conversation_activity_display(item: dict) -> str:
    return format_admin_datetime(
        item.get("last_activity_at")
        or item.get("latest_message_at")
        or item.get("updated_at")
        or item.get("created_at")
        or "—"
    )
    
    


def get_new_conversations_today(clinic_id: int = 1) -> int:
    """
    Count conversations created today for the clinic.
    """
    today = datetime.now().date()
    count = 0
    for c in get_all_conversations(clinic_id):
        created_at = c.get('created_at')
        if not created_at:
            continue
        try:
            created_dt = datetime.fromisoformat(str(created_at))
        except Exception:
            continue
        if created_dt.date() == today:
            count += 1
    return count


def get_owner_metrics(clinic_id: int = 1) -> dict:
    """Return practical clinic-owner metrics based on already filtered CRM/booking data."""
    conversations = get_all_conversations(clinic_id)
    leads_without_booking = get_leads_without_booking(clinic_id)
    operator_inbox = get_operator_inbox(clinic_id)
    today_bookings_list = get_today_bookings(clinic_id)
    upcoming_bookings_list = get_upcoming_bookings(clinic_id)

    booked_leads = len([c for c in conversations if c.get('has_booking')])
    active_conversations = len([
        c for c in conversations
        if c.get('status') in {'active', 'waiting_operator', 'booked'} and not c.get('is_lost')
    ])
    new_leads_today = get_new_conversations_today(clinic_id)
    bookings_today = len(today_bookings_list)
    bookings_upcoming = max(len(upcoming_bookings_list) - bookings_today, 0)
    cancelled_bookings = len(get_bookings_by_status(clinic_id, 'cancelled'))
    no_show_count = len(get_bookings_by_status(clinic_id, 'no_show'))
    completed_bookings = len(get_bookings_by_status(clinic_id, 'completed'))
    open_leads = len(leads_without_booking)
    needs_operator = len(operator_inbox)

    lead_pool = booked_leads + open_leads
    lead_to_booking_conversion = int((booked_leads / lead_pool) * 100) if lead_pool > 0 else 0

    booking_outcomes_pool = bookings_today + bookings_upcoming + cancelled_bookings + no_show_count + completed_bookings
    cancel_rate = int((cancelled_bookings / booking_outcomes_pool) * 100) if booking_outcomes_pool > 0 else 0
    no_show_rate = int((no_show_count / booking_outcomes_pool) * 100) if booking_outcomes_pool > 0 else 0

    return {
        'new_leads_today': new_leads_today,
        'booked_leads': booked_leads,
        'cancelled_bookings': cancelled_bookings,
        'no_show_count': no_show_count,
        'active_conversations': active_conversations,
        'bookings_today': bookings_today,
        'bookings_upcoming': bookings_upcoming,
        'lead_to_booking_conversion': lead_to_booking_conversion,
        'open_leads': open_leads,
        'needs_operator': needs_operator,
        'completed_bookings': completed_bookings,
        'cancel_rate': cancel_rate,
        'no_show_rate': no_show_rate,
    }


def get_admin_css() -> str:
    """Return shared CSS for admin pages with modern SaaS design."""
    return """
    <style>
        :root {
            --bg: #f4f7fb;
            --surface: #ffffff;
            --surface-soft: #f8fafc;
            --border: #e2e8f0;
            --border-strong: #cbd5e1;
            --text: #0f172a;
            --muted: #64748b;
            --brand: #4f46e5;
            --brand-soft: #eef2ff;
            --success: #047857;
            --warning: #b45309;
            --danger: #b91c1c;
            --shadow-sm: 0 2px 10px rgba(15, 23, 42, 0.05);
            --shadow-md: 0 12px 30px rgba(15, 23, 42, 0.08);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(180deg, #f8fafc 0%, #f4f7fb 100%);
            color: var(--text);
            line-height: 1.5;
        }

        /* Header / Top Bar */
        .header {
            background: rgba(255, 255, 255, 0.94);
            border-bottom: 1px solid rgba(226, 232, 240, 0.9);
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            backdrop-filter: blur(10px);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            max-width: 1440px;
            margin: 0 auto;
            padding: 14px 24px 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header-brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .header-brand h1 {
            font-size: 20px;
            font-weight: 800;
            color: var(--text);
            margin: 0;
            letter-spacing: -0.02em;
        }

        .header-brand p {
            font-size: 12px;
            color: var(--muted);
            margin: 2px 0 0;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .header-actions a {
            padding: 8px 12px;
            font-size: 13px;
            font-weight: 600;
            color: #475569;
            text-decoration: none;
            border-radius: 10px;
            border: 1px solid transparent;
            transition: all 0.2s;
        }

        .header-actions a:hover {
            background: var(--surface-soft);
            color: var(--text);
            border-color: var(--border);
        }

        /* Navigation Menu */
        .menu {
            max-width: 1440px;
            margin: 0 auto;
            padding: 0 24px 12px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            background: transparent;
            overflow-x: auto;
            scrollbar-width: thin;
        }

        .menu a {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 14px;
            text-decoration: none;
            color: #475569;
            background: #f8fafc;
            border: 1px solid transparent;
            border-radius: 10px;
            transition: all 0.2s;
            font-size: 13px;
            font-weight: 600;
            white-space: nowrap;
        }

        .menu a:hover {
            color: var(--brand);
            background: var(--brand-soft);
            border-color: #c7d2fe;
        }

        .menu a.active {
            color: #ffffff;
            background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
            border-color: transparent;
            box-shadow: 0 8px 18px rgba(79, 70, 229, 0.22);
        }

        /* Main Container */
        .container {
            max-width: 1440px;
            margin: 0 auto;
            padding: 18px 24px 32px;
        }

        /* Page Title */
        .page-title {
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 18px;
        }

        .page-title h2 {
            font-size: 27px;
            font-weight: 800;
            color: var(--text);
            letter-spacing: -0.03em;
            margin: 0;
        }

        .page-title p {
            font-size: 14px;
            color: var(--muted);
            margin: 0;
            max-width: 920px;
        }

        .page-subtitle {
            font-size: 14px;
            color: var(--muted);
            margin: 0 0 16px;
            line-height: 1.55;
        }

        .auth-shell {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding-top: 32px;
            padding-bottom: 32px;
        }

        .auth-card {
            width: 100%;
            max-width: 460px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: var(--shadow-md);
            padding: 22px;
        }

        .auth-card .btn {
            width: 100%;
        }

        .auth-meta {
            margin-top: 14px;
            font-size: 12px;
            color: var(--muted);
            line-height: 1.6;
        }

        .section-label {
            font-size: 12px;
            font-weight: 700;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 10px;
        }

        /* Cards Grid */
        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 12px;
            margin-bottom: 16px;
        }

        .card-item {
            background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
            border-radius: 14px;
            padding: 16px 18px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            transition: all 0.2s;
            min-height: 128px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .card-item:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-1px);
            border-color: #c7d2fe;
        }

        .card-item .label {
            color: var(--muted);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            margin-bottom: 8px;
            font-weight: 700;
        }

        .card-item .value {
            font-size: 32px;
            font-weight: 800;
            color: var(--text);
            margin: 6px 0 10px;
            letter-spacing: -0.03em;
        }

        .card-item a {
            text-decoration: none;
            font-size: 13px;
            color: var(--brand);
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .card-item a:hover {
            color: #3730a3;
        }

        /* Cards (Sections) */
        .card {
            background: var(--surface);
            border-radius: 14px;
            padding: 18px 20px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
            margin-bottom: 16px;
        }

        .card > h3 {
            font-size: 16px;
            font-weight: 800;
            color: var(--text);
            margin: 0 0 12px 0;
        }

        /* Table Wrapper */
        .table-wrapper {
            overflow: auto;
            width: 100%;
            margin-top: 12px;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: #ffffff;
            box-shadow: var(--shadow-sm);
        }

        /* Tables */
        .card table, table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            table-layout: auto;
            min-width: 760px;
        }

        .card th, th {
            font-size: 11px;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--muted);
            background: #f8fafc;
            position: sticky;
            top: 0;
            z-index: 10;
            font-weight: 800;
            border-bottom: 1px solid var(--border);
            padding: 12px 14px;
            text-align: left;
            white-space: nowrap;
        }

        .card td, td {
            font-size: 14px;
            color: #1e293b;
            padding: 14px;
            border-bottom: 1px solid #edf2f7;
            vertical-align: top;
        }

        tr:last-child td {
            border-bottom: none;
        }

        tbody tr {
            transition: background 0.15s ease, box-shadow 0.15s ease;
        }

        tbody tr:hover {
            background: #f8fbff;
            box-shadow: inset 3px 0 0 #c7d2fe;
        }

        /* Table Cells */
        .row-number { width: 56px; color: #94a3b8; white-space: nowrap; font-size: 12px; font-weight: 700; }
        .cell-time { width: 150px; white-space: nowrap; font-weight: 700; color: var(--text); }
        .cell-service { min-width: 150px; }
        .cell-phone { width: 130px; white-space: nowrap; font-variant-numeric: tabular-nums; font-weight: 700; color: #1e293b; }
        .cell-status { min-width: 120px; }
        .cell-updated { width: 150px; color: var(--muted); font-size: 12px; white-space: nowrap; }
        .cell-actions { width: auto; min-width: 250px; }
        .cell-message { max-width: 360px; }
        .cell-primary { font-weight: 700; color: var(--text); }
        .cell-secondary { margin-top: 4px; font-size: 12px; color: var(--muted); }
        .table-link { color: var(--brand); text-decoration: none; font-weight: 700; }
        .table-link:hover { color: #3730a3; }
        .message-preview {
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            max-width: 100%;
            line-height: 1.45;
            color: #334155;
        }

        /* Action Buttons */
        .action-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
        }

        .action-buttons form {
            display: inline;
            margin: 0;
            padding: 0;
            border: none;
            background: none;
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
            min-height: 36px;
            padding: 8px 12px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 700;
            transition: all 0.18s ease;
            white-space: nowrap;
            text-decoration: none;
            font-family: inherit;
            user-select: none;
            border: 1px solid transparent;
        }

        .btn:active {
            transform: scale(0.98);
        }

        .btn-primary {
            background: var(--brand);
            color: #ffffff;
            border-color: #4338ca;
        }

        .btn-primary:hover {
            background: #4338ca;
            box-shadow: 0 8px 18px rgba(79, 70, 229, 0.2);
        }

        .btn-success {
            background: #ecfdf5;
            color: #065f46;
            border-color: #bbf7d0;
        }

        .btn-success:hover {
            background: #d1fae5;
        }

        .btn-warning {
            background: #fff7ed;
            color: #b45309;
            border-color: #fdba74;
        }

        .btn-warning:hover {
            background: #ffedd5;
        }

        .btn-danger {
            background: #fef2f2;
            color: #b91c1c;
            border-color: #fecaca;
        }

        .btn-danger:hover {
            background: #fee2e2;
        }

        .btn-secondary {
            background: #ffffff;
            color: #334155;
            border-color: var(--border-strong);
        }

        .btn-secondary:hover {
            background: #f8fafc;
            border-color: #94a3b8;
        }

        /* Status Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 5px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            text-align: center;
            white-space: nowrap;
            border: 1px solid transparent;
        }

        .badge-booked { background: #ecfdf5; color: #065f46; border-color: #a7f3d0; }
        .badge-waiting_operator { background: #fff7ed; color: #b45309; border-color: #fdba74; }
        .badge-closed { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }
        .badge-lost { background: #fef2f2; color: #b91c1c; border-color: #fecaca; }
        .badge-active { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
        .badge-completed { background: #ecfdf5; color: #047857; border-color: #bbf7d0; }
        .badge-no-show { background: #faf5ff; color: #7c3aed; border-color: #d8b4fe; }

        /* Forms */
        form:not([style*="margin:0"]) {
            background: #ffffff;
            padding: 18px 20px;
            border-radius: 12px;
            border: 1px solid var(--border);
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
        }

        .form-group {
            margin-bottom: 18px;
        }

        .form-group:last-child {
            margin-bottom: 0;
        }

        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: var(--text);
            font-size: 14px;
        }

        .form-group label span {
            color: #ef4444;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid var(--border-strong);
            border-radius: 8px;
            font-size: 14px;
            font-family: inherit;
            color: var(--text);
            background: #ffffff;
            transition: all 0.2s;
        }

        .form-group input::placeholder,
        .form-group textarea::placeholder {
            color: #94a3b8;
        }

        .form-group input:focus,
        .form-group textarea:focus,
        .form-group select:focus,
        .chat-reply-form textarea:focus {
            outline: none;
            border-color: var(--brand);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12);
            background: #ffffff;
        }

        /* Remove number spinners */
        input[type="number"]::-webkit-outer-spin-button,
        input[type="number"]::-webkit-inner-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }

        input[type="number"] {
            -moz-appearance: textfield;
        }

        .form-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }

        .form-row .form-group {
            margin-bottom: 0;
        }

        /* Notifications */
        .feedback {
            margin-bottom: 16px;
            padding: 14px 16px;
            background: #ecfdf5;
            border: 1px solid #bbf7d0;
            border-left: 4px solid #10b981;
            border-radius: 10px;
            color: #065f46;
            font-weight: 600;
            font-size: 14px;
        }

        /* Empty States */
        .empty {
            text-align: center;
            padding: 42px 20px;
            color: var(--muted);
            background: #f9fafb;
            border-radius: 12px;
            border: 1px dashed var(--border-strong);
            margin: 12px 0;
        }

        .empty-icon {
            font-size: 54px;
            display: block;
            margin-bottom: 12px;
            line-height: 1;
        }

        .empty p {
            font-size: 15px;
            margin: 0;
            color: #475569;
        }

        /* Quick Stats */
        .quick-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 10px;
            margin-bottom: 16px;
        }

        .stat-box {
            background: #ffffff;
            padding: 14px 16px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
        }

        .stat-label {
            font-size: 11px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .stat-value {
            font-size: 28px;
            font-weight: 800;
            color: var(--text);
            margin: 0;
            letter-spacing: -0.03em;
        }

        .stat-subtitle {
            font-size: 12px;
            color: var(--muted);
            margin-top: 6px;
        }

        /* Footer */
        .footer {
            text-align: center;
            margin: 24px auto 0;
            padding: 16px 0 20px;
            border-top: 1px solid var(--border);
            color: #94a3b8;
            font-size: 12px;
            max-width: 1440px;
        }

        /* Status Colors */
        .status-active { color: #22863a; font-weight: 700; }
        .status-inactive { color: #cb2431; font-weight: 700; }
        .status-cancelled { color: #cb2431; font-weight: 700; }
        .status-completed { color: #0366d6; font-weight: 700; }
        .status-no_show { color: #6f42c1; font-weight: 700; }

        /* Utilities */
        .btn-group { display: flex; gap: 6px; flex-wrap: wrap; }
        .badge-wrapper { display: inline-block; }

        /* Responsive Design */
        @media (max-width: 1200px) {
            .container { padding: 18px 16px 28px; }
            .card { padding: 16px 16px; }
            .cards-grid { grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
        }

        @media (max-width: 768px) {
            .header-content { flex-direction: column; gap: 8px; align-items: flex-start; }
            .header-actions { align-self: flex-start; }
            .container { padding: 14px 12px 24px; }
            .page-title h2 { font-size: 22px; }
            .menu { padding: 0 12px 10px; gap: 6px; flex-wrap: nowrap; }
            .menu a { padding: 9px 12px; font-size: 12px; }
            .btn { padding: 7px 10px; font-size: 12px; }
            .card th, th { padding: 10px 12px; font-size: 10px; }
            .card td, td { padding: 10px 12px; }
            .cell-message { max-width: 180px; }
            .cell-actions { min-width: 210px; }
            .action-buttons { gap: 6px; }
            .cards-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
            .quick-stats { grid-template-columns: repeat(2, 1fr); }
            .form-row { grid-template-columns: 1fr; gap: 12px; }
            .chat-reply-form { flex-direction: column; align-items: stretch; }
            .chat-bubble { max-width: 88%; }
        }

        @media (max-width: 480px) {
            .container { padding: 12px 8px 16px; }
            .page-title h2 { font-size: 18px; }
            .menu a { padding: 8px 10px; font-size: 11px; }
            .cards-grid, .quick-stats { grid-template-columns: 1fr; }
            .empty { padding: 32px 14px; }
            .empty-icon { font-size: 42px; }
        }

        /* Chat UI */
        .chat-window {
            background: linear-gradient(180deg, #f8fbff 0%, #f1f5f9 100%);
            border-radius: 12px;
            border: 1px solid var(--border);
            padding: 14px;
            max-height: 520px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-bottom: 14px;
        }
        .chat-bubble {
            max-width: 72%;
            padding: 10px 14px;
            border-radius: 14px;
            font-size: 14px;
            line-height: 1.5;
            word-break: break-word;
            box-shadow: var(--shadow-sm);
        }
        .chat-bubble .bubble-meta {
            font-size: 11px;
            margin-top: 4px;
            opacity: 0.7;
        }
        .bubble-user {
            background: #e2e8f0;
            color: var(--text);
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .bubble-bot {
            background: #4f46e5;
            color: #fff;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .bubble-operator {
            background: #059669;
            color: #fff;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .chat-reply-form {
            display: flex;
            gap: 10px;
            align-items: flex-end;
        }
        .chat-reply-form textarea {
            flex: 1;
            padding: 10px 12px;
            border: 1px solid var(--border-strong);
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
            resize: none;
            min-height: 64px;
        }
        .chat-empty {
            text-align: center;
            color: #94a3b8;
            font-size: 13px;
            padding: 34px 0;
        }
    </style>
    """

from fastapi.responses import HTMLResponse
from fastapi import Request


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return HTMLResponse(render_login_page())

@app.post("/login")
async def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin/react")
):
    safe_next = get_safe_next_path(next)
    email = (username or "").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, password_hash, clinic_id FROM users WHERE email = ?",
        (email,)
    )
    user = cursor.fetchone()
    conn.close()

    if not user:
        return HTMLResponse(render_login_page(error="Пользователь не найден", next_path=next))

    user_id, stored_hash, clinic_id = user

    if not verify_admin_password(password, stored_hash):
        return HTMLResponse(render_login_page(error="Неверный логин или пароль", next_path=next))

    request.session.clear()
    request.session["is_admin"] = True
    request.session["user_id"] = user_id
    request.session["user_email"] = email
    request.session["clinic_id"] = clinic_id

    return RedirectResponse(url=safe_next, status_code=303)



def render_login_page(error: str = "", info: str = "", next_path: str = "/admin/react") -> str:
    safe_next = get_safe_next_path(next_path)
    notice_html = ""
    if error:
        notice_html += f"<div class='feedback' style='background:#fef2f2;border-color:#fecaca;border-left-color:#dc2626;color:#991b1b;'>⚠️ {error}</div>"
    if info:
        notice_html += f"<div class='feedback' style='background:#eff6ff;border-color:#bfdbfe;border-left-color:#2563eb;color:#1d4ed8;'>ℹ️ {info}</div>"
    if not admin_auth_configured():
        notice_html += "<div class='feedback' style='background:#fff7ed;border-color:#fed7aa;border-left-color:#ea580c;color:#9a3412;'>🔐 Добавьте <b>ADMIN_USERNAME</b>, <b>ADMIN_PASSWORD</b> и <b>ADMIN_SESSION_SECRET</b> в <code>.env</code>, чтобы включить вход в CRM.</div>"

    return f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>Вход в CRM</title>
        {get_admin_css()}
    </head>
    <body>
        <div class='container auth-shell'>
            <div class='auth-card'>
                <div class='page-title'>
                    <h2>🔐 Вход в CRM</h2>
                    <p>Только для администратора клиники. После входа открывается защищённая CRM-панель.</p>
                </div>
                {notice_html}
                <form method='post' action='/login'>
                    <input type='hidden' name='next' value='{safe_next}'>
                    <div class='form-group'>
                        <label>Логин</label>
                        <input type='text' name='username' placeholder='admin' autocomplete='username' autofocus required>
                    </div>
                    <div class='form-group'>
                        <label>Пароль</label>
                        <input type='password' name='password' placeholder='Введите пароль' autocomplete='current-password' required>
                    </div>

                    <button type='submit' class='btn btn-primary'>Войти в админ-панель</button>
                </form>
                <p style="margin-top:12px; text-align:center;">
    <a href="/forgot-password">Забыли пароль?</a>
</p>

                <div class='auth-meta'>
    <a href='/register'>Создать аккаунт →</a><br><br>
    Для локального запуска используйте переменные окружения
    <code>ADMIN_USERNAME</code>, <code>ADMIN_PASSWORD</code>
    или <code>ADMIN_PASSWORD_HASH</code>.
</div>
            </div>
        </div>
    </body>
    </html>
    """


def render_admin_layout(title: str, content: str, message: str = None) -> str:
    page_hints = {
        '📊 Сводка CRM': 'Ключевые записи, лиды и задачи на сегодня — всё видно за несколько секунд.',
        '📅 Записи на сегодня': 'Быстро отмечайте завершение, отмену и неявки без лишних переходов.',
        '🗓️ Ближайшие записи': 'Контролируйте расписание на ближайшие дни и реагируйте заранее.',
        '📋 Все активные записи': 'Рабочий список действующих записей для ресепшена и операторов.',
        '📬 Входящие оператора': 'Диалоги, где нужен ручной ответ, контроль или быстрое решение.',
        '👥 Лиды без записи': 'Тёплые клиенты, которых важно довести до записи.',
        '💬 Все диалоги': 'Полная история общения с пациентами и текущими статусами.',
        '📈 Метрики и аналитика': 'Сводка по загрузке, конверсии, отменам и неявкам.',
    }
    subtitle = page_hints.get(title, 'Ежедневное рабочее пространство администратора клиники.')

    nav = """
    <div class='menu'>
        <a href='/admin/react'>✨ Новый CRM</a>
        <a href='/admin'>📊 Сводка</a>
        <a href='/admin/today'>📅 Сегодня</a>
        <a href='/admin/upcoming'>🗓️ Ближайшие</a>
        <a href='/admin/bookings'>📋 Записи</a>
        <a href='/admin/inbox'>📬 Входящие</a>
        <a href='/admin/leads'>👥 Лиды</a>
        <a href='/admin/conversations'>💬 Диалоги</a>
        <a href='/admin/metrics'>📈 Метрики</a>
        <a href='/admin/services'>🔧 Услуги</a>
        <a href="/admin/doctors">➕ Добавить врачей</a>
        <a href='/admin/channels'>🔌 Каналы</a>
        <a href='/admin/faq'>❓ Вопросы</a>
        <a href='/admin/settings'>⚙️ Настройки</a>

    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            var current = window.location.pathname;
            document.querySelectorAll('.menu a').forEach(function(link) {
                var href = link.getAttribute('href');
                if (!href) return;
                var isRoot = href === '/admin';
                if ((isRoot && current === href) || (!isRoot && current.indexOf(href + '/') === 0) || (!isRoot && current === href)) {
                    link.classList.add('active');
                }
            });

            var isChatPage = current.indexOf('/chat') !== -1;
            var refreshablePaths = ['/admin', '/admin/inbox', '/admin/conversations', '/admin/bookings', '/admin/today', '/admin/upcoming', '/admin/metrics'];
            var shouldAutoRefresh = isChatPage || refreshablePaths.some(function(path) {
                return current === path || current.indexOf(path + '/') === 0;
            });

            if (!shouldAutoRefresh) {
                return;
            }

            var _lastPollTs = '';
            var _lastInboxCount = -1;
            var _pollFailCount = 0;

            function formIsBusy() {
                var el = document.activeElement;
                return !!(el && ['INPUT', 'TEXTAREA', 'SELECT'].indexOf(el.tagName) !== -1 && !el.readOnly && !el.disabled);
            }

            async function refreshAdminData() {
                if (document.hidden || formIsBusy()) return;
                try {
                    var response = await fetch(window.location.href, {
                        headers: { 'X-Requested-With': 'crm-poll', 'Cache-Control': 'no-cache' },
                        cache: 'no-store'
                    });
                    if (!response.ok) return;
                    var html = await response.text();
                    var doc = new DOMParser().parseFromString(html, 'text/html');
                    var nextContainer = doc.querySelector('.container');
                    var currentContainer = document.querySelector('.container');
                    if (!nextContainer || !currentContainer) return;
                    var scrollY = window.scrollY;
                    currentContainer.innerHTML = nextContainer.innerHTML;
                    document.title = doc.title;
                    window.scrollTo({ top: scrollY, behavior: 'auto' });
                    var chatWindow = document.getElementById('chatWindow');
                    if (chatWindow) { chatWindow.scrollTop = chatWindow.scrollHeight; }
                    _pollFailCount = 0;
                } catch (error) {
                    console.debug('CRM refresh skipped:', error);
                }
            }

            async function lightweightPoll() {
                if (document.hidden) return;
                try {
                    var r = await fetch('/admin/api/poll', {
                        cache: 'no-store',
                        headers: { 'Cache-Control': 'no-cache' }
                    });
                    if (!r.ok) { _pollFailCount++; return; }
                    var data = await r.json();
                    var ts = data.latest_ts || '';
                    var inbox = Number(data.inbox) || 0;
                    var changed = (
                        (_lastPollTs !== '' && ts !== _lastPollTs) ||
                        (_lastInboxCount >= 0 && inbox !== _lastInboxCount)
                    );
                    _lastPollTs = ts;
                    _lastInboxCount = inbox;
                    if (changed) {
                        await refreshAdminData();
                    }
                    _pollFailCount = 0;
                } catch (e) {
                    _pollFailCount++;
                    console.debug('CRM poll error:', e);
                }
            }

            if (isChatPage) {
                // Chat pages: fast full refresh every 5s
                window.setInterval(refreshAdminData, 5000);
            } else {
                // List/dashboard pages: lightweight poll every 3s, full refresh only on change
                window.setInterval(lightweightPoll, 3000);
                // Also do a full refresh every 60s regardless, as a safety net
                window.setInterval(refreshAdminData, 60000);
            }
        });
    </script>
    """
    notify = f"<div class='feedback'>✅ {message}</div>" if message else ""
    return f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>{title}</title>
        {get_admin_css()}
    </head>
    <body>
        <div class='header'>
            <div class='header-content'>
                <div class='header-brand'>
                    <div>
                        <h1>🏥 CRM Клиника</h1>
                        <p>Операционный центр администратора</p>
                    </div>
                </div>
<div class='header-actions'>
    <a href='/logout' style='color:#dc2626;'>↪️ Выход</a>
</div>
            </div>
            {nav}
        </div>
        <div class='container'>
            <div class='page-title'>
                <h2>{title}</h2>
                <p>{subtitle}</p>
            </div>
            {notify}
            {content}
        </div>
        <div class='footer'>💼 Управление клиникой | CRM система</div>
        
        
      

<script>
function togglePasswordBlock() {{
    const block = document.getElementById("passwordBlock");
    if (!block) {{
        alert("нет блока");
        return;
    }}
    block.style.display = block.style.display === "block" ? "none" : "block";
}}

function togglePasswordVisibility(id) {{
    const input = document.getElementById(id);
    if (!input) return;
    input.type = input.type === "password" ? "text" : "password";
}}

async function changePassword() {{
    const old_password = document.getElementById("oldPassword").value;
    const new_password = document.getElementById("newPassword").value;
    const result = document.getElementById("changeResult");

    const res = await fetch("/change-password", {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify({{old_password, new_password}})
    }});

    const data = await res.json();
    result.innerText = data.message || data.error;
}}
</script>
        
    </body>
    </html>
    """


def render_status_badge(status: str) -> str:
    classes = {
        'booked': 'badge-booked',
        'waiting_operator': 'badge-waiting_operator',
        'closed': 'badge-closed',
        'lost': 'badge-no-show',
        'active': 'badge-active',
        'completed': 'badge-completed',
        'cancelled': 'badge-lost',
        'no_show': 'badge-no-show',
    }
    labels = {
        'booked': 'Записан',
        'waiting_operator': 'Нужен оператор',
        'closed': 'Закрыт',
        'lost': 'Не пришёл',
        'active': 'Активен',
        'completed': 'Завершён',
        'cancelled': 'Отменён',
        'no_show': 'Не пришёл',
    }
    class_name = classes.get(status, 'badge-active')
    label = labels.get(status, status.replace('_', ' ').capitalize())
    return f"<span class='badge {class_name}'>{label}</span>"


@app.get("/register", response_class=HTMLResponse)
def register_page():
    return HTMLResponse(f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>Регистрация</title>
        {get_admin_css()}
    </head>
    <body>
        <div class='container auth-shell'>
            <div class='auth-card'>
                <div class='page-title'>
                    <h2>🏥 Регистрация клиники</h2>
                    <p>Создайте аккаунт и подтвердите email кодом из письма.</p>
                </div>

                <div class='form-group'>
                    <label>Название клиники</label>
                    <input id='clinic' placeholder='Dental Clinic'>
                </div>

                <div class='form-group'>
                    <label>Email</label>
                    <input id='email' placeholder='admin@gmail.com'>
                </div>

                <div class='form-group'>
                    <label>Пароль</label>
                    <input id='password' type='password'>
                </div>
                <div class='form-group'>
                    <label>Код доступа</label>
                    <input id='invite_code' placeholder='Введите код'>
                </div>  

                <button class='btn btn-primary' onclick='sendCode()'>Отправить код проверки</button>

                <div id='codeBlock' style='display:none; margin-top:16px;'>
                    <div class='form-group'>
                        <label>Код из письма</label>
                        <input id='code' placeholder='123456'>
                    </div>
                    <button class='btn btn-primary' onclick='verifyCode()'>Подтвердить email</button>
                </div>

                <p id='result' style='margin-top:12px; font-weight:700;'></p>

                <div class='auth-meta'>
                    <a href='/login'>← Уже есть аккаунт</a>
                </div>
            </div>
        </div>

<script>
async function sendCode() {{
    const clinic = document.getElementById("clinic").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const invite_code = document.getElementById("invite_code").value;
    const result = document.getElementById("result");
    const codeBlock = document.getElementById("codeBlock");

    result.innerText = "Отправляем код...";
    result.style.color = "#64748b";

    try {{
        const res = await fetch("/register", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{clinic, email, password, invite_code}})
        }});

        const data = await res.json();

        if (data.error) {{
            result.innerText = data.error;
            result.style.color = "#b91c1c";
        }} else {{
            result.innerText = data.message;
            result.style.color = "#047857";
            codeBlock.style.display = "block";
        }}
    }} catch (e) {{
        console.log(e);
        result.innerText = "Ошибка JS. Открой F12 → Console.";
        result.style.color = "#b91c1c";
    }}
}}

async function verifyCode() {{
    const email = document.getElementById("email").value;
    const code = document.getElementById("code").value;
    const result = document.getElementById("result");

    result.innerText = "Проверяем код...";
    result.style.color = "#64748b";

    try {{
        const res = await fetch("/register/verify", {{
            method: "POST",
            headers: {{"Content-Type": "application/json"}},
            body: JSON.stringify({{email, code}})
        }});

        const data = await res.json();

        if (data.error) {{
            result.innerText = data.error;
            result.style.color = "#b91c1c";
        }} else {{
            result.innerText = data.message + ". Сейчас перекину на вход...";
            result.style.color = "#047857";

            setTimeout(() => {{
                window.location.href = "/login";
            }}, 1200);
        }}
    }} catch (e) {{
        console.log(e);
        result.innerText = "Ошибка JS. Открой F12 → Console.";
        result.style.color = "#b91c1c";
    }}
}}
</script>
    </body>
    </html>
    """)
    import sqlite3
@app.post("/register")
async def register_user(request: Request):
    data = await request.json()

    clinic = (data.get("clinic") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    invite_code = (data.get("invite_code") or "").strip()

    # 🔐 проверка инвайта
    real_invite = os.getenv("REGISTER_INVITE_CODE")

    if not real_invite:
        return {"error": "REGISTER_INVITE_CODE не задан в .env"}

    if not invite_code:
        return {"error": "Введите код доступа"}

    if invite_code != real_invite:
        return {"error": "Неверный код доступа"}

    if not clinic or not email or not password:
        return {"error": "Заполните все поля"}
    # проверки...

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    existing_user = cursor.fetchone()
    conn.close()

    if existing_user:
        return {"error": "Пользователь уже существует"}

    # 👇 ВОТ ЭТО ДОЛЖНО БЫТЬ С ОТСТУПОМ
    code = str(random.randint(100000, 999999))
    password_hash = hash_admin_password(password)

    EMAIL_VERIFY_CODES[email] = {
        "code": code,
        "clinic": clinic,
        "password_hash": password_hash,
        "created_at": datetime.utcnow()
    }

    print("REGISTER START")

    try:
        send_register_code_email(email, code)
        print("EMAIL SENT")
    except Exception as e:
        print("EMAIL ERROR:", e)
        return {"error": "Ошибка отправки email"}

    return {"message": "Код отправлен на почту. Он действует 5 минут."}


@app.post("/register/verify")
async def verify_register_code(request: Request):
    data = await request.json()

    email = (data.get("email") or "").strip().lower()
    code = (data.get("code") or "").strip()

    record = EMAIL_VERIFY_CODES.get(email)

    if not record:
        return {"error": "Код не найден. Отправьте код заново."}

    if datetime.utcnow() - record["created_at"] > timedelta(minutes=5):
        EMAIL_VERIFY_CODES.pop(email, None)
        return {"error": "Код истёк. Отправьте новый код."}

    if record["code"] != code:
        return {"error": "Неверный код"}

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO clinics (name) VALUES (?)", (record["clinic"],))
        clinic_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO users (email, password_hash, clinic_id) VALUES (?, ?, ?)",
            (email, record["password_hash"], clinic_id)
        )

        conn.commit()
    except Exception as e:
        print("VERIFY REGISTER ERROR:", e)
        return {"error": "Пользователь уже существует или ошибка базы"}
    finally:
        conn.close()

    EMAIL_VERIFY_CODES.pop(email, None)

    return {"message": "Аккаунт создан"}


@app.get("/forgot-password", response_class=HTMLResponse)

def forgot_password_page():
    return HTMLResponse(f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1.0'>
        <title>Сброс пароля</title>
        {get_admin_css()}
    </head>
    <body>
        <div class='container auth-shell'>
            <div class='auth-card'>
                <div class='page-title'>
                    <h2>🔑 Сброс пароля</h2>
                    <p>Введите email администратора. Мы отправим ссылку для восстановления доступа.</p>
                </div>

                <div class='form-group'>
                    <label>Email</label>
                    <input id='email' placeholder='admin@example.com' autocomplete='email'>
                </div>

                <button class='btn btn-primary' onclick='sendReset()'>Отправить ссылку</button>

                <p id='result' style='margin-top:14px; font-weight:700;'></p>

                <div class='auth-meta'>
                    <a href='/login'>← Вернуться ко входу</a>
                </div>
            </div>
        </div>

        <script>
        async function sendReset() {{
            const email = document.getElementById("email").value;
            const result = document.getElementById("result");

            result.innerText = "Отправляем письмо...";
            result.style.color = "#64748b";

            try {{
                const res = await fetch("/forgot-password", {{
                    method: "POST",
                    headers: {{"Content-Type": "application/json"}},
                    body: JSON.stringify({{email}})
                }});

                const data = await res.json();

                if (data.error) {{
                    result.innerText = data.error;
                    result.style.color = "#b91c1c";
                }} else {{
                    result.innerText = data.message || "Проверьте почту";
                    result.style.color = "#047857";
                }}
                        }} catch (e) {{
                console.log(e);
                result.innerText = "Ошибка JS. Открой F12 → Console.";
                result.style.color = "#b91c1c";
            }}
        }}
        </script>
    </body>
    </html>
    """)

@app.get("/admin/doctors")
async def admin_doctors(request: Request):
    clinic_id = request.session.get("clinic_id", 1)
    doctors = get_active_doctors(clinic_id)

    doctors_rows = ""

    for d in doctors:
        doctors_rows += f"""
        <tr>
            <td>{d['id']}</td>
            <td><b>{d['full_name']}</b></td>
            <td>{d['profession']}</td>
            <td><span class="badge badge-active">✅ Активен</span></td>
            <td>
                <div class="action-buttons">
                    <a class="btn btn-secondary" href="/admin/doctors/{d['id']}/edit">✏️ Редактировать</a>

                    <form method="post" action="/admin/doctors/{d['id']}/delete"
                        style="display:inline; border:none; background:none; padding:0; margin:0;"
                        onsubmit="return confirm('Удалить врача?');">
                        <button class="btn btn-danger" type="submit">🗑️ Удалить</button>
                    </form>
                </div>
            </td>
        </tr>
        """

    if not doctors_rows:
        doctors_rows = """
        <tr>
            <td colspan="5" class="empty-state">Врачей пока нет. Добавьте первого врача выше.</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Врачи</title>
        {get_admin_css()}
    </head>
    <body>
        {get_admin_header("doctors") if "get_admin_header" in globals() else ""}

        <main class="admin-main">
            <div class="page-header">
                <div>
                    <h1>👨‍⚕️ Врачи</h1>
                    <p>Управление врачами клиники и их специализациями.</p>
                </div>
            </div>

            <section class="card">
                <h2>➕ Добавить врача</h2>

                <form method="post" action="/admin/doctors/add" class="form-grid">
                    <div class="form-group">
                        <label>Имя врача <span>*</span></label>
                        <input name="full_name" placeholder="Например: Алина Петрова" required>
                    </div>

                    <div class="form-group">
                        <label>Профессия <span>*</span></label>
                        <input name="profession" placeholder="Например: стоматолог" required>
                    </div>

                    <div class="form-actions">
                        <button class="btn btn-primary" type="submit">✓ Добавить врача</button>
                    </div>
                </form>
            </section>

            <section class="card">
                <h2>📋 Список врачей ({len(doctors)})</h2>

                <div class="table-wrap">
                    <table>
                        <thead>
                            <tr>
                              <th>№</th>
                                <th>Имя</th>
                                <th>Профессия</th>
                                <th>Статус</th>
                                <th>Действия</th>
                                <td colspan="5" class="empty-state">
                                
                            </tr>
                        </thead>
                        <tbody>
                            {doctors_rows}
                        </tbody>
                    </table>
                </div>
            </section>
        </main>
    </body>
    </html>
    """

    return HTMLResponse(html)

@app.get("/admin/doctors/{doctor_id}/edit")
async def admin_edit_doctor(request: Request, doctor_id: int):
    clinic_id = request.session.get("clinic_id", 1)
    doctor = get_doctor_by_id(doctor_id, clinic_id)

    if not doctor:
        return RedirectResponse("/admin/doctors", status_code=303)

    html = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Редактировать врача</title>
        {get_admin_css()}
    </head>
    <body>
        {get_admin_header("doctors") if "get_admin_header" in globals() else ""}

        <main class="admin-main">
            <div class="page-header">
                <div>
                    <h1>✏️ Редактировать врача</h1>
                    <p>Изменение имени и профессии врача.</p>
                </div>
            </div>

            <section class="card">
                <form method="post" action="/admin/doctors/{doctor_id}/edit" class="form-grid">
                    <div class="form-group">
                        <label>Имя врача</label>
                        <input name="full_name" value="{doctor['full_name']}" required>
                    </div>

                    <div class="form-group">
                        <label>Профессия</label>
                        <input name="profession" value="{doctor['profession']}" required>
                    </div>

                    <div class="form-actions">
                        <button class="btn btn-primary" type="submit">✓ Сохранить</button>
                        <a class="btn btn-secondary" href="/admin/doctors">Назад</a>
                    </div>
                </form>
            </section>
        </main>
    </body>
    </html>
    """

    return HTMLResponse(html)


@app.post("/admin/doctors/{doctor_id}/edit")
async def admin_update_doctor(
    request: Request,
    doctor_id: int,
    full_name: str = Form(...),
    profession: str = Form(...)
):
    clinic_id = request.session.get("clinic_id", 1)
    update_doctor(doctor_id, full_name, profession, clinic_id)
    return RedirectResponse("/admin/doctors", status_code=303)

@app.post("/admin/doctors/add")
async def admin_add_doctor(
    request: Request,
    full_name: str = Form(...),
    profession: str = Form(...)
):
    clinic_id = request.session.get("clinic_id", 1)
    add_doctor(full_name, profession, clinic_id)
    return RedirectResponse("/admin/doctors", status_code=303)

@app.post("/admin/doctors/{doctor_id}/delete")
async def admin_delete_doctor(request: Request, doctor_id: int):
    clinic_id = request.session.get("clinic_id", 1)
    deactivate_doctor(doctor_id, clinic_id)
    return RedirectResponse("/admin/doctors", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    clinic_id = request.session.get("clinic_id", 1)
    owner_metrics = get_owner_metrics(clinic_id)

    next_bookings = get_upcoming_bookings(clinic_id)[:5]
    operator_conversations = get_operator_inbox(clinic_id)[:5]
    hot_leads = get_leads_without_booking(clinic_id)[:5]

    upcoming_rows = ""
    for b in next_bookings:
        appointment = format_slot_for_display(b.get('appointment_at', '—'))
        upcoming_rows += f"<tr><td class='cell-time'>{appointment}</td><td class='cell-service'><div class='cell-primary'>{b.get('service','—')}</div></td><td><div class='cell-primary'>{b.get('full_name','—')}</div></td><td class='cell-phone'>{format_phone_for_display(b.get('phone',''))}</td><td class='cell-status'>{render_status_badge('booked' if b.get('status','active') == 'active' else b.get('status','active'))}</td></tr>"

    operator_rows = ""
    for c in operator_conversations:
        last_msg = get_conversation_message_preview(c, limit=72)
        status_html = render_status_badge(c.get('status', 'active'))
        if c.get("needs_operator") and c.get("latest_sender_type") == "user":
            status_html += " <span class='badge badge-warning' style='background:#fff7ed;color:#b45309;border-color:#fdba74;'>Новое</span>"
        operator_rows += f"<tr><td><a href='/admin/conversations/{c.get('id')}/chat' class='table-link'>{c.get('full_name','—')}</a></td><td class='cell-phone'>{c.get('phone','—')}</td><td class='cell-message'><div class='message-preview'>{last_msg}</div></td><td class='cell-status'>{status_html}</td></tr>"

    leads_rows = ""
    for l in hot_leads:
        last_msg = get_conversation_message_preview(l, limit=72)
        leads_rows += f"<tr><td><a href='/admin/conversations/{l.get('id')}/chat' class='table-link'>{l.get('full_name','—')}</a></td><td class='cell-phone'>{l.get('phone','—')}</td><td class='cell-message'><div class='message-preview'>{last_msg}</div></td><td class='cell-status'>{render_status_badge(l.get('status','active'))}</td></tr>"

    card_html =f"""
    

    
    
    <p class='page-subtitle'>Короткая управленческая сводка: новые лиды, записи, отмены и диалоги, где требуется внимание.</p>

    <div class='card'>
        <h3>⚡ Ключевые показатели клиники</h3>
        <div class='cards-grid'>
            <div class='card-item'><div class='label'>🆕 Новые лиды</div><div class='value'>{owner_metrics['new_leads_today']}</div><a href='/admin/leads'>Открыть лиды →</a></div>
            <div class='card-item'><div class='label'>✅ Записанные лиды</div><div class='value'>{owner_metrics['booked_leads']}</div><a href='/admin/bookings'>Смотреть записи →</a></div>
            <div class='card-item'><div class='label'>📅 Записи сегодня</div><div class='value'>{owner_metrics['bookings_today']}</div><a href='/admin/today'>План на сегодня →</a></div>
            <div class='card-item'><div class='label'>🗓️ Впереди</div><div class='value'>{owner_metrics['bookings_upcoming']}</div><a href='/admin/upcoming'>Смотреть график →</a></div>
            <div class='card-item'><div class='label'>💬 Активные диалоги</div><div class='value'>{owner_metrics['active_conversations']}</div><a href='/admin/conversations'>Открыть CRM →</a></div>
            <div class='card-item'><div class='label'>📬 Ждут ответа</div><div class='value'>{owner_metrics['needs_operator']}</div><a href='/admin/inbox'>Разобрать →</a></div>
            <div class='card-item'><div class='label'>❌ Отмены</div><div class='value'>{owner_metrics['cancelled_bookings']}</div><a href='/admin/metrics'>Посмотреть →</a></div>
            <div class='card-item'><div class='label'>⊘ Неявки</div><div class='value'>{owner_metrics['no_show_count']}</div><a href='/admin/metrics'>Посмотреть →</a></div>
        </div>
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Конверсия лид → запись</div><div class='stat-value'>{owner_metrics['lead_to_booking_conversion']}%</div><div class='stat-subtitle'>Из текущих лидов в воронке</div></div>
            <div class='stat-box'><div class='stat-label'>Лиды без записи</div><div class='stat-value'>{owner_metrics['open_leads']}</div><div class='stat-subtitle'>Требуют доведения до визита</div></div>
            <div class='stat-box'><div class='stat-label'>Доля отмен</div><div class='stat-value'>{owner_metrics['cancel_rate']}%</div><div class='stat-subtitle'>От всей загрузки и исходов</div></div>
            <div class='stat-box'><div class='stat-label'>Доля неявок</div><div class='stat-value'>{owner_metrics['no_show_rate']}%</div><div class='stat-subtitle'>Важно для контроля качества</div></div>
        </div>
    </div>

    <div class='card'>
        <h3>📍 Ближайшие записи</h3>
        {"<div class='empty'><div class='empty-icon'>📭</div><p>Нет ближайших записей</p></div>" if not next_bookings else "<div class='table-wrapper'><table><tr><th>Время</th><th>Услуга</th><th>Имя</th><th>Телефон</th><th>Статус</th></tr>" + upcoming_rows + "</table></div>"}
    </div>

    <div class='card'>
        <h3>🚨 Диалоги, требующие внимания</h3>
        {"<div class='empty'><div class='empty-icon'>📭</div><p>Нет диалогов для оператора</p></div>" if not operator_conversations else "<div class='table-wrapper'><table><tr><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th></tr>" + operator_rows + "</table></div>"}
    </div>

    <div class='card'>
        <h3>🔥 Горячие лиды без записи</h3>
        {"<div class='empty'><div class='empty-icon'>👥</div><p>Лидов пока нет</p></div>" if not hot_leads else "<div class='table-wrapper'><table><tr><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th></tr>" + leads_rows + "</table></div>"}
    </div>
    """

    return HTMLResponse(render_admin_layout('📊 Сводка CRM', card_html))

def normalize_admin_time(value: str) -> str:
    value = (value or "").strip()
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except ValueError:
        return ""
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def admin_time_to_minutes(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def get_bot_pause_until(clinic_id: int = 1) -> str:
    settings = get_clinic_settings(clinic_id)
    try:
        pause_hours = int(settings.get("bot_pause_hours") or 12)
    except (TypeError, ValueError):
        pause_hours = 12
    if pause_hours not in {2, 6, 12, 24}:
        pause_hours = 12
    return (datetime.now() + timedelta(hours=pause_hours)).isoformat()


def is_bot_pause_expired(conversation: dict) -> bool:
    paused_until = (conversation or {}).get("bot_paused_until")
    if not paused_until:
        return False
    try:
        return datetime.now() >= datetime.fromisoformat(str(paused_until))
    except Exception:
        return False


@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request, message: str = None, error: str = None):
    clinic_id = get_current_clinic_id(request)
    settings = get_clinic_settings(clinic_id)
    selected_days = set(str(settings.get("working_days", "0,1,2,3,4,5")).split(","))
    day_labels = [
        ("0", "Пн"),
        ("1", "Вт"),
        ("2", "Ср"),
        ("3", "Чт"),
        ("4", "Пт"),
        ("5", "Сб"),
        ("6", "Вс"),
    ]
    working_days_html = "".join(
        f"""
        <label style='display:inline-flex;align-items:center;gap:6px;margin-right:12px;font-weight:700;'>
            <input type='checkbox' name='working_days' value='{day}' {"checked" if day in selected_days else ""}>
            {label}
        </label>
        """
        for day, label in day_labels
    )
    current_pause_hours = int(settings.get("bot_pause_hours") or 12)
    pause_options_html = "".join(
        f"<option value='{hours}' {'selected' if current_pause_hours == hours else ''}>{hours} ч</option>"
        for hours in (2, 6, 12, 24)
    )

    content = f"""
    {"<div class='feedback'>✅ " + message + "</div>" if message else ""}
    {"<div class='feedback' style='background:#fef2f2;border-color:#fecaca;border-left-color:#dc2626;color:#991b1b;'>⚠️ " + error + "</div>" if error else ""}

    <div class='card'>
        <h3>⚙️ График работы</h3>

        <form method='post' action='/admin/settings'>
            <div class='form-row'>
                <div class='form-group'>
                    <label>Начало рабочего дня</label>
                    <input type='time' name='work_start' value='{settings.get("work_start", "10:00")}' required>
                </div>

                <div class='form-group'>
                    <label>Конец рабочего дня</label>
                    <input type='time' name='work_end' value='{settings.get("work_end", "19:00")}' required>
                </div>

                <div class='form-group'>
                    <label>Шаг записи, минут</label>
                    <input type='number' name='slot_step_minutes' value='{settings.get("slot_step_minutes", 30)}' min='5' max='240' step='5' required>
                </div>
            </div>

            <div class='form-group'>
                <label>Рабочие дни</label>
                <div style='padding:10px 0;'>{working_days_html}</div>
            </div>

            <div class='form-group'>
                <label>Автоматически включать бота после ответа оператора</label>
                <select name='bot_pause_hours'>
                    {pause_options_html}
                </select>
            </div>

            <button type='submit' class='btn btn-primary'>✓ Сохранить настройки</button>
        </form>
    </div>
    """

    return HTMLResponse(render_admin_layout("⚙️ Настройки клиники", content))


@app.post("/admin/settings")
async def admin_update_settings(
    request: Request,
    work_start: str = Form(...),
    work_end: str = Form(...),
    slot_step_minutes: int = Form(...),
    working_days: list[str] = Form([]),
    bot_pause_hours: int = Form(12),
):
    clinic_id = get_current_clinic_id(request)

    work_start = normalize_admin_time(work_start)
    work_end = normalize_admin_time(work_end)

    if not work_start or not work_end:
        return RedirectResponse(url="/admin/settings?error=" + urlquote("Введите время в формате ЧЧ:ММ"), status_code=303)

    if admin_time_to_minutes(work_start) >= admin_time_to_minutes(work_end):
        return RedirectResponse(url="/admin/settings?error=" + urlquote("Начало должно быть раньше конца"), status_code=303)

    if slot_step_minutes < 5 or slot_step_minutes > 240:
        return RedirectResponse(url="/admin/settings?error=" + urlquote("Шаг записи должен быть от 5 до 240 минут"), status_code=303)

    if not working_days:
        return RedirectResponse(url="/admin/settings?error=" + urlquote("Выберите хотя бы один рабочий день"), status_code=303)

    if bot_pause_hours not in {2, 6, 12, 24}:
        return RedirectResponse(url="/admin/settings?error=" + urlquote("Выберите корректное время авто-включения бота"), status_code=303)

    update_work_hours(work_start, work_end, clinic_id)
    update_slot_step(slot_step_minutes, clinic_id)
    update_working_days(working_days, clinic_id)
    update_bot_pause_hours(bot_pause_hours, clinic_id)

    return RedirectResponse(url="/admin/settings?message=" + urlquote("Настройки сохранены"), status_code=303)

@app.get("/admin/channels", response_class=HTMLResponse)
async def admin_channels(request: Request, message: str = None):
    clinic_id = get_current_clinic_id(request)

    content = f"""
    <div class='card'>
        <h3>🔌 Подключение каналов</h3>
        <p class='page-subtitle'>
            Здесь можно привязать WhatsApp instance или Telegram bot key к текущей клинике.
        </p>

        {"<div class='feedback'>✅ " + message + "</div>" if message else ""}

        <form method='post' action='/admin/channels/add'>
            <div class='form-group'>
                <label>Тип канала</label>
                <select name='channel_type' required>
                    <option value='whatsapp'>WhatsApp</option>
                </select>
            </div>

            <div class='form-group'>
                <label>Channel key</label>
                <input name='channel_key' placeholder='Например: 7107607169 или clinic1' required>
            </div>
            <div class='form-group'>
                <label>Green API Token</label>
                <input name='channel_token' placeholder='Введите apiTokenInstance'>
            </div>
            <div class='form-group'>
                <label>Название</label>
                <input name='channel_name' placeholder='WhatsApp клиники'>
            </div>

            <button class='btn btn-primary' type='submit'>Подключить канал</button>
        </form>

        <div class='auth-meta'>
            WhatsApp: вставь <b>idInstance</b> из Green API.<br>
            Telegram: вставь свой <b>bot_key</b>, например <code>clinic1</code>.
        </div>
    </div>
    """

    return HTMLResponse(render_admin_layout("🔌 Каналы", content))


@app.post("/admin/channels/add")
async def admin_add_channel(
    request: Request,
    channel_type: str = Form(...),
    channel_key: str = Form(...),
    channel_token: str = Form(""),
    channel_name: str = Form("")
):
    clinic_id = get_current_clinic_id(request)

    channel_type = channel_type.strip().lower()
    channel_key = channel_key.strip()
    channel_token = channel_token.strip() or None
    channel_name = channel_name.strip() or None

    if channel_type not in ["whatsapp", "telegram"]:
        return RedirectResponse(url="/admin/channels?message=Неверный тип канала", status_code=303)

    if not channel_key:
        return RedirectResponse(url="/admin/channels?message=Введите channel key", status_code=303)
    add_clinic_channel(
        clinic_id=clinic_id,
        channel_type=channel_type,
        channel_key=channel_key,
        channel_token=channel_token,
        channel_name=channel_name
    )

    return RedirectResponse(url="/admin/channels?message=Канал подключён", status_code=303)

@app.get("/admin/today", response_class=HTMLResponse)
async def admin_today(request: Request):
    clinic_id = get_current_clinic_id(request)
    bookings = get_today_bookings(clinic_id)
    total = len(bookings)
    active = len([b for b in bookings if b.get("status") == "active"])
    completed = len([b for b in bookings if b.get("status") == "completed"])
    cancelled = len([b for b in bookings if b.get("status") == "cancelled"])

    if not bookings:
        content = '<div class="empty"><div class="empty-icon">📭</div><p>На сегодня записей нет</p></div>'
    else:
        rows = ""
        for booking in bookings:
            status = booking.get("status", "active")
            appointment = booking.get("appointment_at", "—")
            appointment_display = format_slot_for_display(appointment) if appointment != "—" else "—"
            service = booking.get("service", "—")
            full_name = booking.get("full_name", "—")
            phone = format_phone_for_display(booking.get("phone", ""))
            
            status_badge = render_status_badge('booked' if status == 'active' else status)

            actions_html = ""
            if status == "active":
                actions_html = f"""
                <div class='action-buttons'>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/complete' style='margin:0;'>
                        <button class='btn btn-success' type='submit' title='Отметить как завершено'>✓ Завершить</button>
                    </form>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/no-show' style='margin:0;'>
                        <button class='btn btn-warning' type='submit' title='Клиент не пришёл'>⊘ Не пришёл</button>
                    </form>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/cancel' style='margin:0;'>
                        <button class='btn btn-danger' type='submit' onclick='return confirm("Отменить запись?");' title='Отменить запись'>✕ Отменить</button>
                    </form>
                </div>
                """
            else:
                actions_html = "<span style='color:#a0aec0;'>—</span>"

            rows += f"""
            <tr>
                <td class='cell-time'>{appointment_display}</td>
                <td class='cell-service'><div class='cell-primary'>{service}</div></td>
                <td><div class='cell-primary'>{full_name}</div></td>
                <td class='cell-phone'>{phone}</td>
                <td class='cell-status'>{status_badge}</td>
                <td class='cell-actions'>{actions_html}</td>
            </tr>
            """

        stats = f"""
        <div class='quick-stats'>
            <div class='stat-box'>
                <div class='stat-label'>Всего на сегодня</div>
                <div class='stat-value'>{total}</div>
            </div>
            <div class='stat-box'>
                <div class='stat-label'>🔵 В ожидании</div>
                <div class='stat-value' style='color: #22863a;'>{active}</div>
            </div>
            <div class='stat-box'>
                <div class='stat-label'>✅ Завершено</div>
                <div class='stat-value' style='color: #0366d6;'>{completed}</div>
            </div>
            <div class='stat-box'>
                <div class='stat-label'>❌ Отменено</div>
                <div class='stat-value' style='color: #e53e3e;'>{cancelled}</div>
            </div>
        </div>
        """
        content = stats + f"<div class='table-wrapper'><table><tr><th>Время</th><th>Услуга</th><th>Имя</th><th>Телефон</th><th>Статус</th><th>Действия</th></tr>{rows}</table></div>"

    return HTMLResponse(render_admin_layout('📅 Записи на сегодня', content))

from fastapi import Request

@app.get("/admin/upcoming")
async def admin_upcoming(request: Request):
    clinic_id = get_current_clinic_id(request)
    bookings = get_upcoming_bookings(clinic_id)
    total = len(bookings)

    if not bookings:
        content = '<div class="empty"><div class="empty-icon">📭</div><p>Предстоящих записей нет</p></div>'
    else:
        rows = ""
        for booking in bookings:
            status = booking.get("status", "active")
            appointment = booking.get("appointment_at", "—")
            appointment_display = format_slot_for_display(appointment) if appointment != "—" else "—"
            service = booking.get("service", "—")
            full_name = booking.get("full_name", "—")
            phone = format_phone_for_display(booking.get("phone", ""))
            
            status_badge = render_status_badge('booked' if status == 'active' else status)

            actions_html = ""
            if status == "active":
                actions_html = f"""
                <div class='action-buttons'>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/complete' style='margin:0;'>
                        <button class='btn btn-success' type='submit' title='Отметить как завершено'>✓ Завершить</button>
                    </form>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/no-show' style='margin:0;'>
                        <button class='btn btn-warning' type='submit' title='Клиент не пришёл'>⊘ Не пришёл</button>
                    </form>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/cancel' style='margin:0;'>
                        <button class='btn btn-danger' type='submit' onclick='return confirm("Отменить запись?");' title='Отменить запись'>✕ Отменить</button>
                    </form>
                </div>
                """
            else:
                actions_html = "<span style='color:#a0aec0;'>—</span>"

            rows += f"""
            <tr>
                <td class='cell-time'>{appointment_display}</td>
                <td class='cell-service'><div class='cell-primary'>{service}</div></td>
                <td><div class='cell-primary'>{full_name}</div></td>
                <td class='cell-phone'>{phone}</td>
                <td class='cell-status'>{status_badge}</td>
                <td class='cell-actions'>{actions_html}</td>
            </tr>
            """

        stats = f"""
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Ближайшие дни</div><div class='stat-value'>{total}</div></div>
        </div>
        """
        content = stats + f"<div class='table-wrapper'><table><tr><th>Время</th><th>Услуга</th><th>Имя</th><th>Телефон</th><th>Статус</th><th>Действия</th></tr>{rows}</table></div>"

    return HTMLResponse(render_admin_layout('🗓️ Ближайшие записи', content))


@app.get("/admin/bookings", response_class=HTMLResponse)
async def admin_bookings(request: Request):
    clinic_id = get_current_clinic_id(request)
    bookings = get_clinic_active_bookings(clinic_id)
    total = len(bookings)
    active = len([b for b in bookings if b.get("status") == "active"])
    completed = len([b for b in bookings if b.get("status") == "completed"])
    cancelled = len([b for b in bookings if b.get("status") == "cancelled"])

    if not bookings:
        content = '<div class="empty"><div class="empty-icon">📭</div><p>Активных записей нет</p></div>'
    else:
        rows = ""
        for booking in bookings:
            status = booking.get("status", "active")
            appointment = booking.get("appointment_at", "—")
            appointment_display = format_slot_for_display(appointment) if appointment != "—" else "—"
            service = booking.get("service", "—")
            full_name = booking.get("full_name", "—")
            phone = format_phone_for_display(booking.get("phone", ""))

            status_badge = render_status_badge('booked' if status == 'active' else status)

            actions_html = ""
            if status == "active":
                actions_html = f"""
                <div class='action-buttons'>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/complete' style='margin:0;'>
                        <button class='btn btn-success' type='submit' title='Отметить как завершено'>✓ Завершить</button>
                    </form>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/no-show' style='margin:0;'>
                        <button class='btn btn-warning' type='submit' title='Клиент не пришёл'>⊘ Не пришёл</button>
                    </form>
                    <form method='post' action='/admin/bookings/{booking.get('id')}/cancel' style='margin:0;'>
                        <button class='btn btn-danger' type='submit' onclick='return confirm("Отменить запись?");' title='Отменить запись'>✕ Отменить</button>
                    </form>
                </div>
                """
            else:
                actions_html = "<span style='color:#a0aec0;'>—</span>"

            rows += f"""
            <tr>
                <td class='cell-time'>{appointment_display}</td>
                <td class='cell-service'><div class='cell-primary'>{service}</div></td>
                <td><div class='cell-primary'>{full_name}</div></td>
                <td class='cell-phone'>{phone}</td>
                <td class='cell-status'>{status_badge}</td>
                <td class='cell-actions'>{actions_html}</td>
            </tr>
            """

        stats = f"""
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Всего</div><div class='stat-value'>{total}</div></div>
            <div class='stat-box'><div class='stat-label' style='color: #22863a;'>В ожидании</div><div class='stat-value' style='color: #22863a;'>{active}</div></div>
            <div class='stat-box'><div class='stat-label' style='color: #0366d6;'>Завершено</div><div class='stat-value' style='color: #0366d6;'>{completed}</div></div>
            <div class='stat-box'><div class='stat-label' style='color: #cb2431;'>Отменено</div><div class='stat-value' style='color: #cb2431;'>{cancelled}</div></div>
        </div>
        """
        content = stats + f"<div class='table-wrapper'><table><tr><th>Время</th><th>Услуга</th><th>Имя</th><th>Телефон</th><th>Статус</th><th>Действия</th></tr>{rows}</table></div>"

    return HTMLResponse(render_admin_layout('📋 Все активные записи', content))


@app.get("/admin/inbox", response_class=HTMLResponse)
async def admin_inbox(request: Request):
    clinic_id = get_current_clinic_id(request)
    conversations = get_operator_inbox(clinic_id)
    total = len(conversations)

    if not conversations:
        content = '<div class="empty"><div class="empty-icon">📬</div><p>Диалогов, требующих оператора, нет</p></div>'
    else:
        rows = ""
        for idx, c in enumerate(conversations, 1):
            updated = get_conversation_activity_display(c)
            last_msg = get_conversation_message_preview(c, limit=76)
            status_html = render_status_badge(c.get('status', 'active'))
            if c.get("latest_sender_type") == "user":
                status_html += " <span class='badge badge-warning' style='background:#fff7ed;color:#b45309;border-color:#fdba74;'>Новое от клиента</span>"

            rows += f"""
            <tr>
                <td class='row-number'>#{idx}</td>
                <td><a href='/admin/conversations/{c['id']}/chat' class='table-link'>{c.get('full_name', '—')}</a></td>
                <td class='cell-phone'>{c.get('phone', '—')}</td>
                <td class='cell-message'><div class='message-preview'>{last_msg}</div></td>
                <td class='cell-status'>{status_html}</td>
                <td class='cell-updated'>{updated}</td>
                <td class='cell-actions'>
                    <div class='action-buttons'>
                        <a href='/admin/conversations/{c['id']}/chat' class='btn btn-primary' title='Открыть диалог и ответить'>💬 Открыть</a>
                        <form method='post' action='/admin/conversations/{c['id']}/clear-operator' style='margin:0;'>
                            <button class='btn btn-success' type='submit' title='Снова разрешить боту отвечать этому клиенту'>🤖 Включить бота</button>
                        </form>
                        <form method='post' action='/admin/conversations/{c['id']}/lost' style='margin:0;'>
                            <button class='btn btn-danger' type='submit' title='Отметить как «не пришёл»'>⊘ Не пришёл</button>
                        </form>
                    </div>
                </td>
            </tr>
            """
        
        stats = f"""
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Нужен оператор</div><div class='stat-value' style='color: #ff9800;'>{total}</div></div>
        </div>
        """
        content = stats + f"<div class='table-wrapper'><table><tr><th>#</th><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th><th>Обновлено</th><th>Действия</th></tr>{rows}</table></div>"

    return HTMLResponse(render_admin_layout('📬 Входящие оператора', content))


@app.get("/admin/leads", response_class=HTMLResponse)
async def admin_leads(request: Request):
    clinic_id = get_current_clinic_id(request)
    leads = get_leads_without_booking(clinic_id)
    total = len(leads)

    if not leads:
        content = '<div class="empty"><div class="empty-icon">👥</div><p>Нет лидов без записи. Отличный результат!</p></div>'
    else:
        rows = ""
        for idx, c in enumerate(leads, 1):
            updated = get_conversation_activity_display(c)
            last_msg = get_conversation_message_preview(c, limit=72)
            phone = c.get('phone', '—')
            
            rows += f"""
            <tr>
                <td class='row-number'>#{idx}</td>
                <td><a href='/admin/conversations/{c['id']}/chat' class='table-link'>{c.get('full_name', '—')}</a></td>
                <td class='cell-phone'>{phone if phone and phone != '—' else '❌ Нет'}</td>
                <td class='cell-message'><div class='message-preview'>{last_msg}</div></td>
                <td class='cell-status'>{render_status_badge(c.get('status', 'active'))}</td>
                <td class='cell-updated'>{updated}</td>
                <td class='cell-actions'>
                    <div class='action-buttons'>
                        <a href='/admin/conversations/{c['id']}/chat' class='btn btn-primary' title='Открыть переписку'>💬 Диалог</a>
                        <form method='post' action='/admin/conversations/{c['id']}/close' style='margin:0;'>
                            <button class='btn btn-secondary' type='submit' title='Закрыть задачу'>✓ Закрыть</button>
                        </form>
                        <form method='post' action='/admin/conversations/{c['id']}/lost' style='margin:0;'>
                            <button class='btn btn-danger' type='submit' title='Отметить как «не пришёл»'>⊘ Не пришёл</button>
                        </form>
                    </div>
                </td>
            </tr>
            """
        
        stats = f"""
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Активных лидов</div><div class='stat-value' style='color: #dd6b20;'>{total}</div></div>
            <div class='stat-box'><div class='stat-label'>Нужно контактировать</div><div class='stat-value' style='color: #e53e3e;'>{len([l for l in leads if not l.get('phone')])}</div></div>
        </div>
        <p class='page-subtitle'>
            💡 Это потенциальные клиенты, которые интересовались услугами, но ещё не записались. 
            Следите за этими контактами и предлагайте записать их.
        </p>
        """
        content = stats + f"<div class='table-wrapper'><table><tr><th>#</th><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th><th>Последняя активность</th><th>Действия</th></tr>{rows}</table></div>"

    return HTMLResponse(render_admin_layout('👥 Лиды без записи', content))


@app.get("/admin/conversations", response_class=HTMLResponse)
async def admin_conversations(request: Request):
    clinic_id = get_current_clinic_id(request)
    conversations = get_all_conversations(clinic_id)
    total = len(conversations)
    with_booking = len([c for c in conversations if c.get('has_booking')])
    waiting_operator = len([c for c in conversations if c.get('needs_operator')])
    lost = len([c for c in conversations if c.get('is_lost')])

    if not conversations:
        content = '<div class="empty"><div class="empty-icon">💬</div><p>Диалогов нет</p></div>'
    else:
        rows = ""
        for idx, c in enumerate(conversations, 1):
            updated = get_conversation_activity_display(c)
            last_msg = get_conversation_message_preview(c, limit=68)
            
            booking_badge = "<span class='badge badge-booked'>Есть запись</span>" if c.get('has_booking') else "<span class='badge badge-closed'>Нет записи</span>"

            status_indicators = []
            if c.get('needs_operator'):
                status_indicators.append('<span class="badge badge-waiting_operator" style="margin-right: 4px;">Оператор</span>')
            if c.get('needs_operator') and c.get('latest_sender_type') == 'user':
                status_indicators.append('<span class="badge badge-warning" style="margin-right: 4px;background:#fff7ed;color:#b45309;border-color:#fdba74;">Новое от клиента</span>')
            if c.get('is_lost'):
                status_indicators.append('<span class="badge badge-no-show" style="margin-right: 4px;">Не пришёл</span>')
            indicators_html = ''.join(status_indicators) if status_indicators else '<span style="color: #a0aec0;">—</span>'

            rows += f"""
            <tr>
                <td class='row-number'>#{idx}</td>
                <td><a href='/admin/conversations/{c['id']}/chat' class='table-link'>{c.get('full_name', '—')}</a></td>
                <td class='cell-phone'>{c.get('phone', '—')}</td>
                <td class='cell-message'><div class='message-preview'>{last_msg}</div></td>
                <td class='cell-status'>{render_status_badge(c.get('status', 'active'))}</td>
                <td>{booking_badge}</td>
                <td>{indicators_html}</td>
                <td class='cell-updated'>{updated}</td>
                <td class='cell-actions'>
                    <div class='action-buttons'>
                        <a href='/admin/conversations/{c['id']}/chat' class='btn btn-primary'>💬 Открыть</a>
                    </div>
                </td>
            </tr>
            """

        stats = f"""
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Всего диалогов</div><div class='stat-value'>{total}</div></div>
            <div class='stat-box'><div class='stat-label' style='color: #22863a;'>С записью</div><div class='stat-value' style='color: #22863a;'>{with_booking}</div></div>
            <div class='stat-box'><div class='stat-label' style='color: #ff9800;'>Нужен оператор</div><div class='stat-value' style='color: #ff9800;'>{waiting_operator}</div></div>
            <div class='stat-box'><div class='stat-label' style='color: #e53e3e;'>Не пришли</div><div class='stat-value' style='color: #e53e3e;'>{lost}</div></div>
        </div>
        """
        content = stats + f"<div class='table-wrapper'><table><tr><th>#</th><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th><th>Запись</th><th>Флаги</th><th>Обновлено</th><th>Действия</th></tr>{rows}</table></div>"

    return HTMLResponse(render_admin_layout('💬 Все диалоги', content))


@app.get("/admin/metrics", response_class=HTMLResponse)
async def admin_metrics(request: Request):
    clinic_id = get_current_clinic_id(request)
    owner_metrics = get_owner_metrics(clinic_id)
    active_bookings = len(get_clinic_active_bookings(clinic_id))
    total_bookings = (
        active_bookings
        + owner_metrics['completed_bookings']
        + owner_metrics['cancelled_bookings']
        + owner_metrics['no_show_count']
    )

    recent_bookings = get_upcoming_bookings(clinic_id)[:5]
    recent_leads = get_leads_without_booking(clinic_id)[:5]
    recent_actions = get_operator_inbox(clinic_id)[:5]

    recent_bookings_rows = ""
    for b in recent_bookings:
        appointment = format_slot_for_display(b.get("appointment_at", "—"))
        recent_bookings_rows += f"<tr><td>{appointment}</td><td>{b.get('service','—')}</td><td>{b.get('full_name','—')}</td><td class='cell-phone'>{format_phone_for_display(b.get('phone',''))}</td><td>{render_status_badge(b.get('status','active'))}</td></tr>"

    recent_leads_rows = ""
    for l in recent_leads:
        recent_leads_rows += f"<tr><td>{l.get('full_name','—')}</td><td class='cell-phone'>{l.get('phone','—')}</td><td>{get_conversation_message_preview(l, limit=64)}</td><td>{render_status_badge(l.get('status','active'))}</td></tr>"

    recent_actions_rows = ""
    for a in recent_actions:
        recent_actions_rows += f"<tr><td>{a.get('full_name','—')}</td><td class='cell-phone'>{a.get('phone','—')}</td><td>{get_conversation_message_preview(a, limit=64)}</td><td>{render_status_badge(a.get('status','active'))}</td></tr>"

    content = f"""
    <div class='quick-stats'>
        <div class='stat-box'><div class='stat-label'>Новые лиды</div><div class='stat-value'>{owner_metrics['new_leads_today']}</div></div>
        <div class='stat-box'><div class='stat-label'>Записанные лиды</div><div class='stat-value'>{owner_metrics['booked_leads']}</div></div>
        <div class='stat-box'><div class='stat-label'>Лиды без записи</div><div class='stat-value'>{owner_metrics['open_leads']}</div></div>
        <div class='stat-box'><div class='stat-label'>Активные диалоги</div><div class='stat-value'>{owner_metrics['active_conversations']}</div></div>
        <div class='stat-box'><div class='stat-label'>Ждут ответа</div><div class='stat-value'>{owner_metrics['needs_operator']}</div></div>
        <div class='stat-box'><div class='stat-label'>Записи сегодня</div><div class='stat-value'>{owner_metrics['bookings_today']}</div></div>
        <div class='stat-box'><div class='stat-label'>Ближайшие записи</div><div class='stat-value'>{owner_metrics['bookings_upcoming']}</div></div>
        <div class='stat-box'><div class='stat-label'>Активные записи</div><div class='stat-value'>{active_bookings}</div></div>
        <div class='stat-box'><div class='stat-label'>Отменённые</div><div class='stat-value'>{owner_metrics['cancelled_bookings']}</div></div>
        <div class='stat-box'><div class='stat-label'>Неявки</div><div class='stat-value'>{owner_metrics['no_show_count']}</div></div>
        <div class='stat-box'><div class='stat-label'>Завершённые</div><div class='stat-value'>{owner_metrics['completed_bookings']}</div></div>
        <div class='stat-box'><div class='stat-label'>Всего воронка + визиты</div><div class='stat-value'>{total_bookings}</div></div>
    </div>

    <div class='card'>
        <h3>📊 Показатели воронки</h3>
        <div class='quick-stats'>
            <div class='stat-box'><div class='stat-label'>Конверсия лид → запись</div><div class='stat-value'>{owner_metrics['lead_to_booking_conversion']}%</div><div class='stat-subtitle'>Текущая воронка без ghost-записей</div></div>
            <div class='stat-box'><div class='stat-label'>Доля неявок</div><div class='stat-value'>{owner_metrics['no_show_rate']}%</div><div class='stat-subtitle'>От общей загрузки и исходов</div></div>
            <div class='stat-box'><div class='stat-label'>Доля отмен</div><div class='stat-value'>{owner_metrics['cancel_rate']}%</div><div class='stat-subtitle'>Сигнал по качеству записи</div></div>
        </div>
    </div>

    <div class='card'>
        <h3>🕒 Последние записи</h3>
        {"<div class='empty'><div class='empty-icon'>📭</div><p>Нет ближайших записей</p></div>" if not recent_bookings else "<div class='table-wrapper'><table><tr><th>Время</th><th>Услуга</th><th>Имя</th><th>Телефон</th><th>Статус</th></tr>" + recent_bookings_rows + "</table></div>"}
    </div>

    <div class='card'>
        <h3>📋 Последние лиды</h3>
        {"<div class='empty'><div class='empty-icon'>👥</div><p>Лидов пока нет</p></div>" if not recent_leads else "<div class='table-wrapper'><table><tr><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th></tr>" + recent_leads_rows + "</table></div>"}
    </div>

    <div class='card'>
        <h3>⚡ Последние задачи оператору</h3>
        {"<div class='empty'><div class='empty-icon'>📭</div><p>Ни одной задачи нет</p></div>" if not recent_actions else "<div class='table-wrapper'><table><tr><th>Имя</th><th>Телефон</th><th>Последнее сообщение</th><th>Статус</th></tr>" + recent_actions_rows + "</table></div>"}
    </div>
    """

    return HTMLResponse(render_admin_layout('📈 Метрики и аналитика', content)) 


@app.post("/admin/conversations/{conversation_id}/close")
async def admin_conversation_close(conversation_id: int):
    close_conversation(conversation_id)
    return RedirectResponse(url="/admin/inbox", status_code=303)


@app.post("/admin/conversations/{conversation_id}/lost")
async def admin_conversation_lost(conversation_id: int):
    mark_conversation_lost(conversation_id)
    return RedirectResponse(url="/admin/leads", status_code=303)

@app.post("/register/send-code")
async def send_register_code(request: Request):
    data = await request.json()

    clinic = (data.get("clinic") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not clinic or not email or not password:
        return {"error": "Заполните все поля"}

    # генерация кода
    code = str(random.randint(100000, 999999))

    password_hash = hash_admin_password(password)

    EMAIL_VERIFY_CODES[email] = {
        "code": code,
        "clinic": clinic,
        "password_hash": password_hash,
        "created_at": datetime.utcnow()
    }

    # отправка письма
    send_email(email, f"Ваш код подтверждения: {code}")

    return {"message": "Код отправлен на почту"}



@app.post("/admin/conversations/{conversation_id}/clear-operator")
async def admin_conversation_clear_operator(conversation_id: int):
    clear_conversation_operator_flag(conversation_id)
    return RedirectResponse(url="/admin/inbox", status_code=303)


@app.post("/admin/conversations/{conversation_id}/enable-bot")
async def admin_conversation_enable_bot(conversation_id: int):
    clear_conversation_operator_flag(conversation_id)
    return RedirectResponse(url=f"/admin/conversations/{conversation_id}/chat", status_code=303)


@app.get("/admin/conversations/{conversation_id}/chat", response_class=HTMLResponse)
async def admin_conversation_chat(conversation_id: int):
    conv = get_conversation_by_id(conversation_id)
    if not conv:
        return RedirectResponse(url="/admin/inbox", status_code=303)

    messages = get_messages_by_conversation(conversation_id, limit=200)

    bubbles_html = ""
    if not messages:
        bubbles_html = "<div class='chat-empty'>Сообщений пока нет</div>"
    else:
        for msg in messages:
            sender = msg["sender_type"]
            text = msg["text"].replace("<", "&lt;").replace(">", "&gt;")
            ts = format_admin_datetime(msg.get("created_at", ""))

            if sender == "user":
                label = conv.get("full_name") or "Клиент"
                bubble_class = "bubble-user"
            elif sender == "operator":
                label = "Оператор"
                bubble_class = "bubble-operator"
            else:
                label = "Бот"
                bubble_class = "bubble-bot"

            bubbles_html += f"""
            <div class='chat-bubble {bubble_class}'>
                <div>{text}</div>
                <div class='bubble-meta'>{label} · {ts}</div>
            </div>
            """

    bot_available = bool((os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip())
    send_disabled = "" if bot_available else "disabled"
    send_hint = "" if bot_available else "<p style='color:#f56565;font-size:12px;margin-top:6px;'>⚠️ Укажите TELEGRAM_TOKEN в .env, чтобы отвечать клиентам из CRM</p>"
    bot_paused = bool(conv.get("needs_operator"))
    bot_paused_until = format_admin_datetime(conv.get("bot_paused_until", "")) if conv.get("bot_paused_until") else ""
    bot_mode_badge = (
        f"<span class='badge badge-waiting_operator'>Бот выключен{(' до ' + bot_paused_until) if bot_paused_until else ''}</span>"
        if bot_paused
        else "<span class='badge badge-active'>Бот включен</span>"
    )
    new_client_badge = (
        "<span class='badge badge-warning' style='background:#fff7ed;color:#b45309;border-color:#fdba74;'>Новое от клиента</span>"
        if bot_paused and conv.get("latest_sender_type") == "user"
        else ""
    )
    enable_bot_button = f"""
                <form method='post' action='/admin/conversations/{conversation_id}/enable-bot' style='margin:0;'>
                    <button class='btn btn-success' type='submit' title='Снова разрешить боту отвечать этому клиенту'>🤖 Включить бота</button>
                </form>
    """ if bot_paused else ""

    info_html = f"""
    <div class='card' style='margin-bottom: 16px;'>
        <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;'>
            <div>
                <strong>{conv.get('full_name') or '—'}</strong>
                &nbsp;&nbsp;
                <span style='color:#718096;'>{conv.get('phone') or '—'}</span>
                &nbsp;&nbsp;
                {render_status_badge(conv.get('status', 'active'))}
                &nbsp;&nbsp;
                {bot_mode_badge}
                &nbsp;&nbsp;
                {new_client_badge}
            </div>
            <div class='action-buttons'>
                {enable_bot_button}
                <form method='post' action='/admin/conversations/{conversation_id}/close' style='margin:0;'>
                    <button class='btn btn-secondary' type='submit'>✓ Закрыть</button>
                </form>
                <form method='post' action='/admin/conversations/{conversation_id}/lost' style='margin:0;'>
                    <button class='btn btn-danger' type='submit'>⊘ Не пришёл</button>
                </form>
                <a href='/admin/inbox' class='btn btn-secondary'>← Назад</a>
            </div>
        </div>
    </div>
    """

    template_buttons = """
    <div class='action-buttons' style='margin-bottom:10px;'>
        <button type='button' class='btn btn-secondary' data-template='Здравствуйте! Сейчас помогу вам.' onclick='insertReplyTemplate(this)'>Здравствуйте</button>
        <button type='button' class='btn btn-secondary' data-template='Подскажите, пожалуйста, номер телефона для связи.' onclick='insertReplyTemplate(this)'>Нужен номер</button>
        <button type='button' class='btn btn-secondary' data-template='Могу предложить ближайшее удобное время. Какой день вам подходит?' onclick='insertReplyTemplate(this)'>Предложить время</button>
        <button type='button' class='btn btn-secondary' data-template='Передала информацию администратору. Скоро вам ответим.' onclick='insertReplyTemplate(this)'>Передано администратору</button>
    </div>
    """

    reply_form = f"""
    <form method='post' action='/admin/conversations/{conversation_id}/reply' style='border:none;background:none;padding:0;margin:0;'>
        {template_buttons}
        <div class='chat-reply-form'>
            <textarea id='operatorReplyText' name='message' placeholder='Написать ответ клиенту...' required {send_disabled}></textarea>
            <button type='submit' class='btn btn-primary' {send_disabled}>📤 Отправить</button>
        </div>
        {send_hint}
    </form>
    """

    content = info_html + f"""
    <div class='card'>
        <h3 style='margin-bottom:12px;'>💬 История переписки</h3>
        <div class='chat-window' id='chatWindow'>{bubbles_html}</div>
        {reply_form}
    </div>
    <script>
        var cw = document.getElementById('chatWindow');
        if (cw) cw.scrollTop = cw.scrollHeight;
        function insertReplyTemplate(button) {{
            var textarea = document.getElementById('operatorReplyText');
            if (!textarea) return;
            textarea.value = button.getAttribute('data-template') || '';
            textarea.focus();
        }}
    </script>
    """

    name = conv.get("full_name") or f"Диалог #{conversation_id}"
    return HTMLResponse(render_admin_layout(f"💬 {name}", content))


async def deliver_operator_reply(conversation_id: int, message: str) -> dict:
    conv = get_conversation_by_id(conversation_id)
    if not conv:
        return {"ok": False, "error": "Диалог не найден"}

    safe_message = (message or "").strip()
    if not safe_message:
        return {"ok": False, "error": "Введите сообщение"}

    chat_id = (conv.get("chat_id") or "").strip()

    current_status = (conv.get("status") or "active").strip()
    if current_status in {"cancelled", "completed", "closed", "no_show"}:
        status_after_reply = current_status
    elif conv.get("has_booking"):
        status_after_reply = "booked"
    elif conv.get("is_lost"):
        status_after_reply = "no_show"
    else:
        status_after_reply = "waiting_operator"

    store_message(conversation_id, chat_id, "operator", safe_message)
    upsert_conversation(
        clinic_id=conv["clinic_id"],
        chat_id=chat_id,
        last_bot_reply=f"[Оператор] {safe_message}",
        needs_operator=1,
        status=status_after_reply,
        bot_paused_until=get_bot_pause_until(conv["clinic_id"]),
    )

    delivered = False
    if chat_id:
        try:
            logger.info("[ADMIN->TG] Sending message to %s: %s", chat_id, safe_message[:80])
            delivered = await send_telegram_text(chat_id, safe_message)
            if delivered:
                logger.info("[ADMIN->TG] Delivered conv=%s chat_id=%s", conversation_id, chat_id)
            else:
                logger.error("[ADMIN->TG] Delivery failed conv=%s chat_id=%s", conversation_id, chat_id)
        except Exception as e:
            logger.exception("[ADMIN->TG] Failed to send conv=%s chat_id=%s: %s", conversation_id, chat_id, e)
            traceback.print_exc()
    else:
        logger.error("[ADMIN->TG] Missing chat_id for conversation_id=%s", conversation_id)

    return {"ok": True, "delivered": delivered, "conversation": get_conversation_by_id(conversation_id)}


@app.post("/admin/conversations/{conversation_id}/reply")
async def admin_conversation_reply(conversation_id: int, message: str = Form(...)):
    await deliver_operator_reply(conversation_id, message)

    return RedirectResponse(
        url=f"/admin/conversations/{conversation_id}/chat",
        status_code=303,
    )
    
    


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login?logged_out=1", status_code=303)


@app.get("/admin/api/poll", include_in_schema=False)
async def admin_api_poll(request: Request):
    """Lightweight JSON endpoint for admin live-update polling.

    Returns inbox count and latest conversation update timestamp so the
    frontend JavaScript can decide whether a full content refresh is needed,
    avoiding expensive full-page fetches when nothing has changed.
    """
    from fastapi.responses import JSONResponse
    clinic_id = get_current_clinic_id(request)
    try:
        inbox_count = len(get_operator_inbox(clinic_id))
        all_convs = get_all_conversations(clinic_id)
        latest_ts = ""
        if all_convs:
            ts_values = [
                c.get("last_activity_at") or c.get("updated_at") or c.get("created_at") or ""
                for c in all_convs
            ]
            latest_ts = max(ts_values, default="")
        return JSONResponse({"inbox": inbox_count, "latest_ts": latest_ts, "ok": True})
    except Exception as exc:
        logger.debug("admin_api_poll error: %s", exc)
        return JSONResponse({"inbox": 0, "latest_ts": "", "ok": False})


def serialize_admin_booking(booking: dict) -> dict:
    appointment_at = booking.get("appointment_at") or ""
    return {
        "id": booking.get("id"),
        "service": booking.get("service") or "визит",
        "full_name": booking.get("full_name") or "Клиент",
        "phone": format_phone_for_display(booking.get("phone", "")),
        "raw_phone": booking.get("phone", ""),
        "appointment_at": appointment_at,
        "appointment_display": format_slot_for_display(appointment_at) if appointment_at else "—",
        "status": booking.get("status") or "active",
        "duration_minutes": booking.get("duration_minutes") or 60,
    }


def serialize_admin_conversation(conversation: dict) -> dict:
    latest_sender = conversation.get("latest_sender_type") or ""
    bot_paused_until = conversation.get("bot_paused_until") or ""
    return {
        "id": conversation.get("id"),
        "chat_id": conversation.get("chat_id") or "",
        "full_name": conversation.get("full_name") or "Клиент",
        "phone": conversation.get("phone") or "—",
        "status": conversation.get("status") or "active",
        "needs_operator": bool(conversation.get("needs_operator")),
        "has_booking": bool(conversation.get("has_booking")),
        "is_lost": bool(conversation.get("is_lost")),
        "latest_sender_type": latest_sender,
        "latest_message": get_conversation_message_preview(conversation, limit=120),
        "latest_message_raw": conversation.get("latest_message") or conversation.get("last_user_message") or conversation.get("last_bot_reply") or "",
        "last_activity_at": conversation.get("last_activity_at") or conversation.get("updated_at") or conversation.get("created_at") or "",
        "last_activity_display": get_conversation_activity_display(conversation),
        "bot_paused_until": bot_paused_until,
        "bot_paused_until_display": format_admin_datetime(bot_paused_until) if bot_paused_until else "",
        "has_new_client_message": bool(conversation.get("needs_operator") and latest_sender == "user"),
    }


def serialize_admin_message(message: dict) -> dict:
    return {
        "id": message.get("id"),
        "sender_type": message.get("sender_type") or "",
        "text": message.get("text") or "",
        "created_at": message.get("created_at") or "",
        "created_display": format_admin_datetime(message.get("created_at") or ""),
    }


def serialize_admin_doctor(doctor: dict) -> dict:
    return {
        "id": doctor.get("id"),
        "clinic_id": doctor.get("clinic_id"),
        "full_name": doctor.get("full_name") or "",
        "profession": doctor.get("profession") or "",
        "is_active": bool(doctor.get("is_active", 1)),
    }


def serialize_admin_service(service: dict) -> dict:
    price = service.get("price")
    duration = service.get("duration_minutes") or 60
    return {
        "id": service.get("id"),
        "name": service.get("name") or "",
        "price": price,
        "price_display": f"{int(price):,}".replace(",", " ") + " тг" if price is not None else "не указана",
        "duration_minutes": duration,
        "duration_display": f"{int(duration)} мин",
        "category": service.get("category") or "",
        "description": service.get("description") or "",
        "sort_order": service.get("sort_order") or 0,
        "is_active": bool(service.get("is_active", 1)),
    }


def format_admin_money(value) -> str:
    try:
        amount = int(float(value or 0))
    except (TypeError, ValueError):
        amount = 0
    return f"{amount:,}".replace(",", " ") + " тг"


def mask_secret(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}••••{value[-4:]}"


def get_clinic_channels_for_admin(clinic_id: int) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, channel_type, channel_key, channel_token, channel_name, is_active, created_at
    FROM clinic_channels
    WHERE clinic_id = ? AND is_active = 1
    ORDER BY created_at DESC, id DESC
    """, (clinic_id,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "channel_type": row[1],
            "channel_key": row[2],
            "channel_token_masked": mask_secret(row[3]),
            "has_token": bool(row[3]),
            "channel_name": row[4] or "",
            "is_active": bool(row[5]),
            "created_at": row[6] or "",
            "created_display": format_admin_datetime(row[6] or ""),
        }
        for row in rows
    ]


def get_channel_owner(channel_type: str, channel_key: str) -> int | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT clinic_id
    FROM clinic_channels
    WHERE channel_type = ? AND channel_key = ? AND is_active = 1
    LIMIT 1
    """, (channel_type, channel_key))
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else None


def deactivate_clinic_channel(channel_id: int, clinic_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE clinic_channels
    SET is_active = 0
    WHERE id = ? AND clinic_id = ?
    """, (channel_id, clinic_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def normalize_user_email(email: str) -> str:
    return (email or "").strip().lower()


def is_platform_root_email(email: str) -> bool:
    return normalize_user_email(email) == PLATFORM_ROOT_EMAIL


def is_platform_admin_email(email: str) -> bool:
    normalized_email = normalize_user_email(email)
    if not normalized_email:
        return False
    if is_platform_root_email(normalized_email):
        return True

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 1
    FROM platform_admins
    WHERE lower(email) = ? AND is_active = 1
    LIMIT 1
    """, (normalized_email,))
    row = cursor.fetchone()
    conn.close()
    return bool(row)


def get_current_user_email(request: Request) -> str:
    return normalize_user_email(request.session.get("user_email") or "")


def has_platform_access(request: Request) -> bool:
    return is_platform_admin_email(get_current_user_email(request))


def has_platform_root_access(request: Request) -> bool:
    return is_platform_root_email(get_current_user_email(request))


def get_platform_access_payload(request: Request) -> dict:
    user_email = get_current_user_email(request)
    is_root = is_platform_root_email(user_email)
    return {
        "enabled": is_root or is_platform_admin_email(user_email),
        "is_root": is_root,
        "can_manage_all_clinics": is_root or is_platform_admin_email(user_email),
        "can_manage_platform_admins": is_root,
        "root_email": PLATFORM_ROOT_EMAIL,
    }


def get_platform_clinics_for_admin() -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        c.id,
        COALESCE(NULLIF(cs.clinic_name, ''), c.name, 'Клиника') AS clinic_name,
        COALESCE(NULLIF(cs.address, ''), c.address, '') AS address,
        COALESCE(c.is_active, 1) AS is_active,
        GROUP_CONCAT(DISTINCT u.email) AS admin_emails
    FROM clinics c
    LEFT JOIN clinic_settings cs
        ON cs.id = (
            SELECT id
            FROM clinic_settings
            WHERE clinic_id = c.id
            ORDER BY id DESC
            LIMIT 1
        )
    LEFT JOIN users u ON u.clinic_id = c.id
    GROUP BY c.id
    ORDER BY c.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    clinics = []
    for row in rows:
        clinic_id = int(row[0])
        admin_emails = [item for item in (row[4] or "").split(",") if item]
        channels = get_clinic_channels_for_admin(clinic_id)
        clinics.append({
            "id": clinic_id,
            "name": row[1] or "Клиника",
            "address": row[2] or "",
            "is_active": bool(row[3]),
            "admin_emails": admin_emails,
            "admin_emails_display": ", ".join(admin_emails) if admin_emails else "Администратор не найден",
            "channels": channels,
            "channels_count": len(channels),
        })
    return clinics


def get_platform_users_for_root() -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        u.id,
        u.email,
        u.clinic_id,
        COALESCE(NULLIF(cs.clinic_name, ''), c.name, 'Клиника') AS clinic_name,
        COALESCE(pa.is_active, 0) AS platform_access,
        pa.granted_by,
        pa.created_at
    FROM users u
    LEFT JOIN clinics c ON c.id = u.clinic_id
    LEFT JOIN clinic_settings cs
        ON cs.id = (
            SELECT id
            FROM clinic_settings
            WHERE clinic_id = u.clinic_id
            ORDER BY id DESC
            LIMIT 1
        )
    LEFT JOIN platform_admins pa ON lower(pa.email) = lower(u.email)
    ORDER BY lower(u.email)
    """)
    rows = cursor.fetchall()
    conn.close()

    users = []
    for row in rows:
        email = normalize_user_email(row[1])
        is_root = is_platform_root_email(email)
        users.append({
            "id": row[0],
            "email": email,
            "clinic_id": row[2],
            "clinic_name": row[3] or "Клиника",
            "is_root": is_root,
            "has_platform_access": is_root or bool(row[4]),
            "granted_by": row[5] or "",
            "created_at": row[6] or "",
            "created_display": format_admin_datetime(row[6] or "") if row[6] else "",
        })
    return users


def clinic_exists(clinic_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM clinics WHERE id = ? LIMIT 1", (clinic_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row)


def get_user_email_by_id(user_id: int) -> str:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return normalize_user_email(row[0]) if row else ""


def set_platform_admin_access(email: str, granted_by: str, enabled: bool) -> bool:
    normalized_email = normalize_user_email(email)
    granted_by = normalize_user_email(granted_by)
    if not normalized_email or is_platform_root_email(normalized_email):
        return False

    conn = get_db_connection()
    cursor = conn.cursor()
    if enabled:
        cursor.execute("""
        INSERT INTO platform_admins (email, granted_by, is_active, created_at, updated_at)
        VALUES (?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(email) DO UPDATE SET
            granted_by = excluded.granted_by,
            is_active = 1,
            updated_at = CURRENT_TIMESTAMP
        """, (normalized_email, granted_by))
    else:
        cursor.execute("""
        UPDATE platform_admins
        SET is_active = 0, updated_at = CURRENT_TIMESTAMP
        WHERE lower(email) = ?
        """, (normalized_email,))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def ensure_erp_tables() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS erp_inventory_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT DEFAULT '',
        unit TEXT DEFAULT 'шт',
        quantity REAL NOT NULL DEFAULT 0,
        min_quantity REAL NOT NULL DEFAULT 0,
        cost_per_unit INTEGER NOT NULL DEFAULT 0,
        supplier TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS erp_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL,
        expense_date TEXT NOT NULL,
        category TEXT DEFAULT '',
        title TEXT NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0,
        vendor TEXT DEFAULT '',
        payment_method TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(clinic_id) REFERENCES clinics(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS erp_doctor_salaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        salary_month TEXT NOT NULL,
        doctor_name TEXT NOT NULL,
        profession TEXT DEFAULT '',
        amount INTEGER NOT NULL DEFAULT 0,
        is_paid INTEGER NOT NULL DEFAULT 0,
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(clinic_id, doctor_id, salary_month),
        FOREIGN KEY(clinic_id) REFERENCES clinics(id),
        FOREIGN KEY(doctor_id) REFERENCES doctors(id)
    )
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_erp_inventory_clinic_active
    ON erp_inventory_items (clinic_id, is_active, name)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_erp_expenses_clinic_date
    ON erp_expenses (clinic_id, expense_date DESC, id DESC)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_erp_salaries_clinic_month
    ON erp_doctor_salaries (clinic_id, salary_month DESC, doctor_id)
    """)

    conn.commit()
    conn.close()


def parse_admin_decimal(value, default: float = 0.0) -> float:
    value_text = str(value if value is not None else "").strip().replace(",", ".")
    if value_text == "":
        return default
    try:
        parsed = float(value_text)
    except (TypeError, ValueError):
        return default
    return parsed


def serialize_erp_inventory_item(item: dict) -> dict:
    quantity = float(item.get("quantity") or 0)
    min_quantity = float(item.get("min_quantity") or 0)
    cost_per_unit = int(item.get("cost_per_unit") or 0)
    stock_value = int(round(quantity * cost_per_unit))
    return {
        "id": item.get("id"),
        "name": item.get("name") or "",
        "category": item.get("category") or "",
        "unit": item.get("unit") or "шт",
        "quantity": quantity,
        "quantity_display": f"{quantity:g} {item.get('unit') or 'шт'}",
        "min_quantity": min_quantity,
        "min_quantity_display": f"{min_quantity:g} {item.get('unit') or 'шт'}",
        "cost_per_unit": cost_per_unit,
        "cost_per_unit_display": format_admin_money(cost_per_unit),
        "stock_value": stock_value,
        "stock_value_display": format_admin_money(stock_value),
        "supplier": item.get("supplier") or "",
        "notes": item.get("notes") or "",
        "is_low_stock": quantity <= min_quantity if min_quantity > 0 else False,
        "updated_at": item.get("updated_at") or "",
        "updated_display": format_admin_datetime(item.get("updated_at") or ""),
    }


def serialize_erp_expense(expense: dict) -> dict:
    amount = int(expense.get("amount") or 0)
    return {
        "id": expense.get("id"),
        "expense_date": expense.get("expense_date") or "",
        "expense_date_display": format_admin_datetime((expense.get("expense_date") or "") + " 00:00")[:10],
        "category": expense.get("category") or "",
        "title": expense.get("title") or "",
        "amount": amount,
        "amount_display": format_admin_money(amount),
        "vendor": expense.get("vendor") or "",
        "payment_method": expense.get("payment_method") or "",
        "notes": expense.get("notes") or "",
        "created_at": expense.get("created_at") or "",
        "created_display": format_admin_datetime(expense.get("created_at") or ""),
    }


def serialize_erp_doctor_salary(salary: dict) -> dict:
    amount = int(salary.get("amount") or 0)
    return {
        "id": salary.get("id"),
        "doctor_id": salary.get("doctor_id"),
        "doctor_name": salary.get("doctor_name") or salary.get("current_doctor_name") or "",
        "profession": salary.get("profession") or salary.get("current_profession") or "",
        "salary_month": salary.get("salary_month") or "",
        "amount": amount,
        "amount_display": format_admin_money(amount),
        "is_paid": bool(salary.get("is_paid")),
        "status_label": "Выплачено" if salary.get("is_paid") else "Запланировано",
        "notes": salary.get("notes") or "",
        "created_at": salary.get("created_at") or "",
        "updated_at": salary.get("updated_at") or "",
        "updated_display": format_admin_datetime(salary.get("updated_at") or ""),
    }


def get_erp_inventory_items(clinic_id: int) -> list[dict]:
    ensure_erp_tables()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT *
    FROM erp_inventory_items
    WHERE clinic_id = ? AND is_active = 1
    ORDER BY
        CASE WHEN min_quantity > 0 AND quantity <= min_quantity THEN 0 ELSE 1 END,
        lower(name)
    """, (clinic_id,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_erp_expenses(clinic_id: int, limit: int = 80) -> list[dict]:
    ensure_erp_tables()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT *
    FROM erp_expenses
    WHERE clinic_id = ?
    ORDER BY expense_date DESC, id DESC
    LIMIT ?
    """, (clinic_id, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_erp_doctor_salaries(clinic_id: int, limit: int = 120) -> list[dict]:
    ensure_erp_tables()
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT
        s.*,
        COALESCE(d.full_name, s.doctor_name) AS current_doctor_name,
        COALESCE(d.profession, s.profession) AS current_profession
    FROM erp_doctor_salaries s
    LEFT JOIN doctors d
        ON d.id = s.doctor_id
       AND d.clinic_id = s.clinic_id
    WHERE s.clinic_id = ?
    ORDER BY s.salary_month DESC, lower(COALESCE(d.full_name, s.doctor_name)), s.id DESC
    LIMIT ?
    """, (clinic_id, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_erp_finance_metrics(clinic_id: int) -> dict:
    ensure_erp_tables()
    month_prefix = datetime.now().strftime("%Y-%m")
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT COALESCE(SUM(COALESCE(s.price, 0)), 0)
    FROM bookings b
    LEFT JOIN services s
        ON s.clinic_id = b.clinic_id
       AND lower(trim(s.name)) = lower(trim(COALESCE(b.service, '')))
       AND COALESCE(s.is_active, 1) = 1
    WHERE b.clinic_id = ?
      AND b.status = 'completed'
      AND substr(COALESCE(b.appointment_at, ''), 1, 7) = ?
    """, (clinic_id, month_prefix))
    completed_revenue = int(cursor.fetchone()[0] or 0)

    cursor.execute("""
    SELECT COALESCE(SUM(COALESCE(s.price, 0)), 0)
    FROM bookings b
    LEFT JOIN services s
        ON s.clinic_id = b.clinic_id
       AND lower(trim(s.name)) = lower(trim(COALESCE(b.service, '')))
       AND COALESCE(s.is_active, 1) = 1
    WHERE b.clinic_id = ?
      AND b.status = 'active'
      AND substr(COALESCE(b.appointment_at, ''), 1, 7) = ?
    """, (clinic_id, month_prefix))
    pipeline_revenue = int(cursor.fetchone()[0] or 0)

    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0)
    FROM erp_expenses
    WHERE clinic_id = ?
      AND substr(COALESCE(expense_date, ''), 1, 7) = ?
    """, (clinic_id, month_prefix))
    operating_expenses = int(cursor.fetchone()[0] or 0)

    cursor.execute("""
    SELECT
        COALESCE(SUM(CASE WHEN is_paid = 1 THEN amount ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN is_paid = 0 THEN amount ELSE 0 END), 0),
        COALESCE(SUM(amount), 0)
    FROM erp_doctor_salaries
    WHERE clinic_id = ?
      AND salary_month = ?
    """, (clinic_id, month_prefix))
    salary_paid_total, salary_planned_total, salary_total = cursor.fetchone()
    salary_paid_total = int(salary_paid_total or 0)
    salary_planned_total = int(salary_planned_total or 0)
    salary_total = int(salary_total or 0)

    conn.close()
    month_expenses = operating_expenses + salary_paid_total

    return {
        "month": month_prefix,
        "completed_revenue": completed_revenue,
        "completed_revenue_display": format_admin_money(completed_revenue),
        "pipeline_revenue": pipeline_revenue,
        "pipeline_revenue_display": format_admin_money(pipeline_revenue),
        "operating_expenses": operating_expenses,
        "operating_expenses_display": format_admin_money(operating_expenses),
        "salary_total": salary_total,
        "salary_total_display": format_admin_money(salary_total),
        "salary_paid_total": salary_paid_total,
        "salary_paid_total_display": format_admin_money(salary_paid_total),
        "salary_planned_total": salary_planned_total,
        "salary_planned_total_display": format_admin_money(salary_planned_total),
        "month_expenses": month_expenses,
        "month_expenses_display": format_admin_money(month_expenses),
        "estimated_profit": completed_revenue - month_expenses,
        "estimated_profit_display": format_admin_money(completed_revenue - month_expenses),
    }


def get_admin_erp_payload(clinic_id: int) -> dict:
    inventory_raw = get_erp_inventory_items(clinic_id)
    expenses_raw = get_erp_expenses(clinic_id)
    salaries_raw = get_erp_doctor_salaries(clinic_id)
    inventory = [serialize_erp_inventory_item(item) for item in inventory_raw]
    expenses = [serialize_erp_expense(item) for item in expenses_raw]
    salaries = [serialize_erp_doctor_salary(item) for item in salaries_raw]

    inventory_value = sum(item["stock_value"] for item in inventory)
    low_stock_count = len([item for item in inventory if item["is_low_stock"]])
    finance = get_erp_finance_metrics(clinic_id)
    current_month = finance.get("month") or datetime.now().strftime("%Y-%m")
    current_month_salaries = [item for item in salaries if item["salary_month"] == current_month]

    return {
        "metrics": {
            **finance,
            "inventory_count": len(inventory),
            "inventory_value": inventory_value,
            "inventory_value_display": format_admin_money(inventory_value),
            "low_stock_count": low_stock_count,
            "expenses_count": len(expenses),
            "salary_count": len(current_month_salaries),
            "salary_paid_count": len([item for item in current_month_salaries if item["is_paid"]]),
            "salary_planned_count": len([item for item in current_month_salaries if not item["is_paid"]]),
        },
        "inventory": inventory,
        "low_stock": [item for item in inventory if item["is_low_stock"]],
        "expenses": expenses,
        "salaries": salaries,
    }


def get_admin_react_payload(request: Request) -> dict:
    clinic_id = get_current_clinic_id(request)
    platform_access = get_platform_access_payload(request)
    owner_metrics = get_owner_metrics(clinic_id)
    settings = get_clinic_settings(clinic_id)
    active_bookings = get_clinic_active_bookings(clinic_id)
    today_bookings = get_today_bookings(clinic_id)
    upcoming_bookings = get_upcoming_bookings(clinic_id)
    inbox = get_operator_inbox(clinic_id)
    leads = get_leads_without_booking(clinic_id)
    conversations = get_all_conversations(clinic_id)
    working_days = [
        item.strip()
        for item in str(settings.get("working_days") or "0,1,2,3,4,5").split(",")
        if item.strip()
    ]

    return {
        "ok": True,
        "clinic": {
            "id": clinic_id,
            "name": settings.get("clinic_name") or "Клиника",
            "user_email": request.session.get("user_email") or "",
        },
        "settings": {
            "clinic_name": settings.get("clinic_name") or "Клиника",
            "address": settings.get("address") or "",
            "work_start": settings.get("work_start") or "10:00",
            "work_end": settings.get("work_end") or "19:00",
            "slot_step_minutes": settings.get("slot_step_minutes") or 30,
            "working_days": working_days,
            "bot_pause_hours": settings.get("bot_pause_hours") or 12,
            "admin_notify_whatsapp": settings.get("admin_notify_whatsapp") or "",
            "notify_new_leads": bool(settings.get("notify_new_leads")),
            "notify_new_bookings": bool(settings.get("notify_new_bookings")),
            "notify_operator_requests": bool(settings.get("notify_operator_requests")),
            "whatsapp_reminders_enabled": bool(settings.get("whatsapp_reminders_enabled")),
            "panel_language": settings.get("panel_language") or "ru",
            "panel_theme": settings.get("panel_theme") or "blue",
        },
        "channels": get_clinic_channels_for_admin(clinic_id),
        "doctors": [
            serialize_admin_doctor(item)
            for item in get_active_doctors(clinic_id)
        ],
        "services": [
            serialize_admin_service(item)
            for item in get_all_services(clinic_id)
            if item.get("is_active", 1)
        ],
        "erp": get_admin_erp_payload(clinic_id),
        "webhooks": {
            "whatsapp": str(request.base_url).rstrip("/") + "/webhook/whatsapp",
        },
        "platform_admin": platform_access,
        "platform_clinics": get_platform_clinics_for_admin() if platform_access["can_manage_all_clinics"] else [],
        "platform_users": get_platform_users_for_root() if platform_access["can_manage_platform_admins"] else [],
        "metrics": owner_metrics,
        "bookings": {
            "active": [serialize_admin_booking(item) for item in active_bookings],
            "today": [serialize_admin_booking(item) for item in today_bookings],
            "upcoming": [serialize_admin_booking(item) for item in upcoming_bookings],
        },
        "conversations": {
            "inbox": [serialize_admin_conversation(item) for item in inbox],
            "leads": [serialize_admin_conversation(item) for item in leads],
            "all": [serialize_admin_conversation(item) for item in conversations],
        },
        "poll": {
            "inbox": len(inbox),
            "latest_ts": max(
                [
                    item.get("last_activity_at") or item.get("updated_at") or item.get("created_at") or ""
                    for item in conversations
                ],
                default="",
            ),
        },
    }


def get_admin_assistant_action(label: str, view: str) -> dict:
    return {"label": label, "view": view}


def get_admin_assistant_booking_lines(bookings: list[dict], limit: int = 5) -> str:
    if not bookings:
        return ""

    lines = []
    for item in bookings[:limit]:
        lines.append(
            f"• {item.get('appointment_display', '—')} — "
            f"{item.get('full_name', 'Клиент')}, "
            f"{item.get('service', 'визит')}, "
            f"{item.get('phone', '—')}"
        )
    return "\n".join(lines)


def build_admin_assistant_reply(request: Request, message: str) -> dict:
    payload = get_admin_react_payload(request)
    text = re.sub(r"\s+", " ", (message or "").lower().replace("ё", "е")).strip()
    metrics = payload.get("metrics", {})
    bookings = payload.get("bookings", {})
    conversations = payload.get("conversations", {})
    settings = payload.get("settings", {})
    channels = payload.get("channels", [])
    doctors = payload.get("doctors", [])
    services = payload.get("services", [])
    erp = payload.get("erp", {})
    erp_metrics = erp.get("metrics", {})

    suggestions = [
        "Какие записи сегодня?",
        "Что требует внимания?",
        "Что есть в ERP?",
        "Как добавить врача?",
        "Как подключить WhatsApp?",
    ]

    def response(answer: str, actions: list[dict] | None = None, extra_suggestions: list[str] | None = None) -> dict:
        return {
            "answer": answer,
            "actions": actions or [],
            "suggestions": extra_suggestions or suggestions,
        }

    if not text or any(word in text for word in ["помощ", "что умеешь", "ориентир", "подскажи", "с чего начать"]):
        answer = (
            "Я помогу ориентироваться в CRM.\n\n"
            f"Сейчас: записей сегодня — {metrics.get('bookings_today', 0)}, "
            f"ожидают ответа — {metrics.get('needs_operator', 0)}, "
            f"лидов без записи — {metrics.get('open_leads', 0)}, "
            f"услуг — {len(services)}, врачей — {len(doctors)}, "
            f"низких остатков ERP — {erp_metrics.get('low_stock_count', 0)}.\n\n"
            "Можно спросить: «какие записи сегодня», «как добавить врача», "
            "«что есть в ERP», «как подключить WhatsApp», «что требует внимания»."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть входящие", "conversations"),
            get_admin_assistant_action("Открыть записи", "bookings"),
            get_admin_assistant_action("Открыть ERP", "erp"),
            get_admin_assistant_action("Открыть настройки", "settings"),
        ])

    if any(word in text for word in ["запис", "распис", "сегодня", "ближайш", "прием", "приём"]):
        today = bookings.get("today", [])
        upcoming = bookings.get("upcoming", [])
        today_lines = get_admin_assistant_booking_lines(today)
        if today_lines:
            details = f"\n\nБлижайшие записи сегодня:\n{today_lines}"
        else:
            details = "\n\nНа сегодня записей пока нет."
        answer = (
            f"По записям: сегодня — {len(today)}, "
            f"ближайших — {len(upcoming)}, активных всего — {len(bookings.get('active', []))}."
            f"{details}"
        )
        return response(answer, [
            get_admin_assistant_action("Открыть записи", "bookings"),
            get_admin_assistant_action("Открыть сводку", "dashboard"),
        ], ["Что требует внимания?", "Есть ли лиды без записи?", "Как закрыть запись?"])

    if any(word in text for word in ["лид", "входящ", "оператор", "ответ", "вниман", "новые", "диалог"]):
        inbox = conversations.get("inbox", [])
        leads = conversations.get("leads", [])
        first_items = "\n".join([
            f"• {item.get('full_name', 'Клиент')} — {item.get('latest_message', 'сообщение')}"
            for item in inbox[:4]
        ])
        details = f"\n\nПервые диалоги:\n{first_items}" if first_items else "\n\nСейчас нет диалогов, которые требуют оператора."
        answer = (
            f"Внимание сейчас нужно здесь: входящих оператору — {len(inbox)}, "
            f"лидов без записи — {len(leads)}, активных диалогов — {metrics.get('active_conversations', 0)}."
            f"{details}"
        )
        return response(answer, [
            get_admin_assistant_action("Открыть диалоги", "conversations"),
            get_admin_assistant_action("Открыть сводку", "dashboard"),
        ], ["Какие записи сегодня?", "Как включить бота обратно?", "Как ответить клиенту?"])

    if any(word in text for word in ["врач", "доктор", "специалист"]) and "зарплат" not in text:
        answer = (
            "Чтобы добавить врача:\n"
            "1. Откройте раздел «Врачи».\n"
            "2. Введите имя врача и профессию, например «стоматолог».\n"
            "3. Нажмите «Добавить врача».\n\n"
            f"Сейчас в этой клинике активных врачей: {len(doctors)}. "
            "После добавления бот сможет понимать вопросы клиентов про врачей и запись к специалисту."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть врачей", "doctors"),
        ], ["Как добавить услугу?", "Какие записи сегодня?", "Как клиент выберет врача?"])

    if any(word in text for word in ["услуг", "цен", "стоим", "прайс", "процедур"]):
        answer = (
            "Чтобы добавить услугу и цену:\n"
            "1. Откройте раздел «Услуги».\n"
            "2. Заполните название, цену, длительность и при необходимости категорию.\n"
            "3. Нажмите «Добавить услугу».\n\n"
            f"Сейчас в клинике активных услуг: {len(services)}. "
            "Бот будет использовать эти цены, когда клиент спросит стоимость."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть услуги", "services"),
        ], ["Как добавить врача?", "Как бот отвечает на цены?", "Как изменить график?"])

    if any(word in text for word in ["whatsapp", "ватсап", "green", "api", "instance", "инстанс", "канал", "webhook"]):
        answer = (
            "Чтобы подключить WhatsApp через Green API:\n"
            "1. Откройте «Настройки».\n"
            "2. В блоке WhatsApp / Green API вставьте idInstance и apiTokenInstance.\n"
            "3. В Green API укажите webhook: /webhook/whatsapp на вашем домене.\n"
            "4. Сохраните и отправьте тестовое сообщение в личный чат WhatsApp.\n\n"
            f"Сейчас подключено активных WhatsApp-каналов: {len(channels)}."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть настройки", "settings"),
        ], ["Почему бот не отвечает?", "Как проверить webhook?", "Что требует внимания?"])

    if any(word in text for word in ["erp", "склад", "расход", "финанс", "остат", "прибыл", "выруч", "материал", "зарплат"]):
        answer = (
            "В ERP можно вести склад расходников, фиксировать расходы, зарплаты врачей и смотреть финансы месяца.\n\n"
            f"Сейчас: складских позиций — {erp_metrics.get('inventory_count', 0)}, "
            f"низких остатков — {erp_metrics.get('low_stock_count', 0)}, "
            f"стоимость склада — {erp_metrics.get('inventory_value_display', '0 тг')}, "
            f"выплаченные зарплаты врачей — {erp_metrics.get('salary_paid_total_display', '0 тг')}, "
            f"запланированные зарплаты — {erp_metrics.get('salary_planned_total_display', '0 тг')}, "
            f"расходы месяца — {erp_metrics.get('month_expenses_display', '0 тг')}, "
            f"оценка прибыли — {erp_metrics.get('estimated_profit_display', '0 тг')}.\n\n"
            "Откройте ERP, чтобы добавить материалы, указать минимальный остаток, внести расход или назначить зарплату врачу."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть ERP", "erp"),
        ], ["Как добавить расход?", "Что требует внимания?", "Какие записи сегодня?"])

    if any(word in text for word in ["график", "работ", "адрес", "настрой", "часы", "название", "клиник"]):
        days = ", ".join(settings.get("working_days") or [])
        answer = (
            "Настройки клиники находятся в разделе «Настройки».\n\n"
            f"Сейчас указано: {settings.get('clinic_name', 'Клиника')}, "
            f"график {settings.get('work_start', '10:00')}–{settings.get('work_end', '19:00')}, "
            f"рабочие дни: {days or 'не указаны'}, "
            f"адрес: {settings.get('address') or 'не заполнен'}.\n\n"
            "Эти данные бот использует в ответах клиентам про график, адрес и запись."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть настройки", "settings"),
        ], ["Как подключить WhatsApp?", "Как добавить услугу?", "Какие записи сегодня?"])

    if any(word in text for word in ["бот", "человек", "ручн", "включить", "выключить", "пауза"]):
        answer = (
            "Если оператор отвечает клиенту из CRM, бот ставится на паузу только в этом конкретном диалоге. "
            "Чтобы вернуть автоответы, откройте диалог клиента и нажмите «Включить бота».\n\n"
            "Это не отключает бота для всей клиники, остальные клиенты продолжают получать автоответы."
        )
        return response(answer, [
            get_admin_assistant_action("Открыть диалоги", "conversations"),
        ], ["Что требует внимания?", "Как ответить клиенту?", "Какие лиды без записи?"])

    answer = (
        "Я не до конца понял вопрос, но могу помочь по основным разделам CRM: "
        "записи, диалоги, врачи, услуги, настройки и WhatsApp.\n\n"
        "Попробуйте спросить проще: «какие записи сегодня», «как добавить врача», "
        "«как подключить WhatsApp» или «что требует внимания»."
    )
    return response(answer, [
        get_admin_assistant_action("Открыть сводку", "dashboard"),
        get_admin_assistant_action("Открыть настройки", "settings"),
    ])


@app.get("/admin/react", response_class=HTMLResponse)
async def admin_react_page(request: Request):
    index_path = get_admin_frontend_file("index.html")
    if not index_path:
        return HTMLResponse(render_admin_layout(
            "✨ Новый CRM",
            render_admin_frontend_missing(),
        ))
    return FileResponse(index_path)


@app.get("/admin/api/react/bootstrap")
async def admin_api_react_bootstrap(request: Request):
    return get_admin_react_payload(request)


@app.post("/admin/api/react/assistant")
async def admin_api_react_assistant(request: Request):
    data = await request.json()
    message = (data.get("message") or "").strip()
    return {
        "ok": True,
        **build_admin_assistant_reply(request, message),
    }


@app.post("/admin/api/react/bookings/{booking_id}/{action}")
async def admin_api_react_booking_action(request: Request, booking_id: int, action: str):
    clinic_id = get_current_clinic_id(request)
    booking = get_booking_by_id(booking_id)
    if not booking or int(booking.get("clinic_id") or 0) != clinic_id:
        return {"ok": False, "error": "Запись не найдена"}

    if action == "complete":
        ok = mark_booking_completed(booking_id)
    elif action == "no-show":
        ok = mark_booking_no_show(booking_id)
    elif action == "cancel":
        ok = cancel_booking_by_id(booking_id)
    else:
        return {"ok": False, "error": "Неизвестное действие"}

    return {"ok": bool(ok), "data": get_admin_react_payload(request)}


@app.get("/admin/api/react/conversations/{conversation_id}")
async def admin_api_react_conversation(request: Request, conversation_id: int):
    clinic_id = get_current_clinic_id(request)
    conversation = get_conversation_by_id(conversation_id)
    if not conversation or int(conversation.get("clinic_id") or 0) != clinic_id:
        return {"ok": False, "error": "Диалог не найден"}

    return {
        "ok": True,
        "conversation": serialize_admin_conversation(conversation),
        "messages": [
            serialize_admin_message(item)
            for item in get_messages_by_conversation(conversation_id, limit=200)
        ],
    }


@app.post("/admin/api/react/conversations/{conversation_id}/reply")
async def admin_api_react_conversation_reply(request: Request, conversation_id: int):
    clinic_id = get_current_clinic_id(request)
    conversation = get_conversation_by_id(conversation_id)
    if not conversation or int(conversation.get("clinic_id") or 0) != clinic_id:
        return {"ok": False, "error": "Диалог не найден"}

    data = await request.json()
    result = await deliver_operator_reply(conversation_id, data.get("message", ""))
    return {
        **result,
        "thread": await admin_api_react_conversation(request, conversation_id),
        "data": get_admin_react_payload(request),
    }


@app.post("/admin/api/react/conversations/{conversation_id}/{action}")
async def admin_api_react_conversation_action(request: Request, conversation_id: int, action: str):
    clinic_id = get_current_clinic_id(request)
    conversation = get_conversation_by_id(conversation_id)
    if not conversation or int(conversation.get("clinic_id") or 0) != clinic_id:
        return {"ok": False, "error": "Диалог не найден"}

    if action == "enable-bot":
        ok = clear_conversation_operator_flag(conversation_id)
    elif action == "close":
        ok = close_conversation(conversation_id)
    elif action == "lost":
        ok = mark_conversation_lost(conversation_id)
    else:
        return {"ok": False, "error": "Неизвестное действие"}

    return {"ok": bool(ok), "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/settings")
async def admin_api_react_settings(request: Request):
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    clinic_name = (data.get("clinic_name") or "").strip()
    address = (data.get("address") or "").strip()
    admin_notify_whatsapp = (data.get("admin_notify_whatsapp") or "").strip()
    admin_notify_digits = re.sub(r"\D", "", admin_notify_whatsapp)
    notify_new_leads = bool(data.get("notify_new_leads"))
    notify_new_bookings = bool(data.get("notify_new_bookings"))
    notify_operator_requests = bool(data.get("notify_operator_requests"))
    whatsapp_reminders_enabled = bool(data.get("whatsapp_reminders_enabled"))
    panel_language = (data.get("panel_language") or "ru").strip().lower()
    panel_theme = (data.get("panel_theme") or "blue").strip().lower()
    work_start = normalize_admin_time(data.get("work_start", ""))
    work_end = normalize_admin_time(data.get("work_end", ""))
    try:
        slot_step_minutes = int(data.get("slot_step_minutes") or 30)
    except (TypeError, ValueError):
        slot_step_minutes = 30
    try:
        bot_pause_hours = int(data.get("bot_pause_hours") or 12)
    except (TypeError, ValueError):
        bot_pause_hours = 12

    working_days = [str(item) for item in data.get("working_days", []) if str(item).strip() in {"0", "1", "2", "3", "4", "5", "6"}]

    if not clinic_name:
        return {"ok": False, "error": "Введите название клиники"}
    if len(clinic_name) > 120:
        return {"ok": False, "error": "Название клиники слишком длинное"}
    if len(address) > 300:
        return {"ok": False, "error": "Адрес слишком длинный"}
    if admin_notify_whatsapp and len(admin_notify_digits) < 10:
        return {"ok": False, "error": "Введите корректный WhatsApp номер администратора"}
    if not work_start or not work_end:
        return {"ok": False, "error": "Введите время в формате ЧЧ:ММ"}
    if admin_time_to_minutes(work_start) >= admin_time_to_minutes(work_end):
        return {"ok": False, "error": "Начало должно быть раньше конца"}
    if slot_step_minutes < 5 or slot_step_minutes > 240:
        return {"ok": False, "error": "Шаг записи должен быть от 5 до 240 минут"}
    if not working_days:
        return {"ok": False, "error": "Выберите хотя бы один рабочий день"}
    if bot_pause_hours not in {2, 6, 12, 24}:
        return {"ok": False, "error": "Выберите корректное время авто-включения бота"}
    if panel_language not in {"ru", "en"}:
        return {"ok": False, "error": "Выберите корректный язык панели"}
    if panel_theme not in {"blue", "green", "orange", "red", "yellow", "violet", "slate"}:
        return {"ok": False, "error": "Выберите корректную тему панели"}

    update_clinic_profile(clinic_name, address, clinic_id)
    update_work_hours(work_start, work_end, clinic_id)
    update_slot_step(slot_step_minutes, clinic_id)
    update_working_days(working_days, clinic_id)
    update_bot_pause_hours(bot_pause_hours, clinic_id)
    update_clinic_notification_settings(
        clinic_id=clinic_id,
        admin_notify_whatsapp=admin_notify_whatsapp,
        notify_new_leads=notify_new_leads,
        notify_new_bookings=notify_new_bookings,
        notify_operator_requests=notify_operator_requests,
        whatsapp_reminders_enabled=whatsapp_reminders_enabled,
    )
    update_clinic_ui_settings(
        clinic_id=clinic_id,
        panel_language=panel_language,
        panel_theme=panel_theme,
    )

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/settings/appearance")
async def admin_api_react_settings_appearance(request: Request):
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    panel_language = (data.get("panel_language") or "ru").strip().lower()
    panel_theme = (data.get("panel_theme") or "blue").strip().lower()

    if panel_language not in {"ru", "en"}:
        return {"ok": False, "error": "Выберите корректный язык панели"}
    if panel_theme not in {"blue", "green", "orange", "red", "yellow", "violet", "slate"}:
        return {"ok": False, "error": "Выберите корректную тему панели"}

    ok = update_clinic_ui_settings(
        clinic_id=clinic_id,
        panel_language=panel_language,
        panel_theme=panel_theme,
    )
    if not ok:
        return {"ok": False, "error": "Не удалось сохранить внешний вид панели"}

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/channels")
async def admin_api_react_add_channel(request: Request):
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    channel_type = (data.get("channel_type") or "whatsapp").strip().lower()
    channel_key = (data.get("channel_key") or "").strip()
    channel_token = (data.get("channel_token") or "").strip()
    channel_name = (data.get("channel_name") or "").strip()

    if channel_type != "whatsapp":
        return {"ok": False, "error": "Сейчас в интерфейсе доступен только WhatsApp"}
    if not channel_key:
        return {"ok": False, "error": "Введите idInstance из Green API"}
    if not channel_key.isdigit():
        return {"ok": False, "error": "idInstance должен состоять из цифр"}
    if not channel_token:
        return {"ok": False, "error": "Введите apiTokenInstance"}

    owner_clinic_id = get_channel_owner(channel_type, channel_key)
    if owner_clinic_id and owner_clinic_id != clinic_id:
        return {"ok": False, "error": "Этот idInstance уже привязан к другой клинике"}

    add_clinic_channel(
        clinic_id=clinic_id,
        channel_type=channel_type,
        channel_key=channel_key,
        channel_token=channel_token,
        channel_name=channel_name or "WhatsApp клиники",
    )

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/channels/{channel_id}/delete")
async def admin_api_react_delete_channel(request: Request, channel_id: int):
    clinic_id = get_current_clinic_id(request)
    ok = deactivate_clinic_channel(channel_id, clinic_id)
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Канал не найден"}


@app.post("/admin/api/react/platform/channels")
async def admin_api_react_platform_add_channel(request: Request):
    if not has_platform_access(request):
        return {"ok": False, "error": "Нет доступа к управлению платформой"}

    data = await request.json()

    try:
        clinic_id = int(data.get("clinic_id") or 0)
    except (TypeError, ValueError):
        clinic_id = 0

    channel_type = (data.get("channel_type") or "whatsapp").strip().lower()
    channel_key = (data.get("channel_key") or "").strip()
    channel_token = (data.get("channel_token") or "").strip()
    channel_name = (data.get("channel_name") or "").strip()

    if not clinic_id or not clinic_exists(clinic_id):
        return {"ok": False, "error": "Выберите клинику"}
    if channel_type != "whatsapp":
        return {"ok": False, "error": "Сейчас доступно подключение только WhatsApp / Green API"}
    if not channel_key:
        return {"ok": False, "error": "Введите idInstance из Green API"}
    if not channel_key.isdigit():
        return {"ok": False, "error": "idInstance должен состоять из цифр"}
    if not channel_token:
        return {"ok": False, "error": "Введите apiTokenInstance"}

    owner_clinic_id = get_channel_owner(channel_type, channel_key)
    if owner_clinic_id and owner_clinic_id != clinic_id:
        return {"ok": False, "error": "Этот idInstance уже привязан к другой клинике"}

    add_clinic_channel(
        clinic_id=clinic_id,
        channel_type=channel_type,
        channel_key=channel_key,
        channel_token=channel_token,
        channel_name=channel_name or "WhatsApp клиники",
    )

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/platform/switch-clinic/{clinic_id}")
async def admin_api_react_platform_switch_clinic(request: Request, clinic_id: int):
    if not has_platform_access(request):
        return {"ok": False, "error": "Нет доступа к управлению платформой"}
    if not clinic_exists(clinic_id):
        return {"ok": False, "error": "Клиника не найдена"}

    request.session["clinic_id"] = int(clinic_id)
    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/platform/channels/{channel_id}/delete")
async def admin_api_react_platform_delete_channel(request: Request, channel_id: int):
    if not has_platform_access(request):
        return {"ok": False, "error": "Нет доступа к управлению платформой"}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE clinic_channels
    SET is_active = 0
    WHERE id = ?
    """, (channel_id,))
    changed = cursor.rowcount
    conn.commit()
    conn.close()

    return {"ok": bool(changed), "data": get_admin_react_payload(request), "error": "" if changed else "Канал не найден"}


@app.post("/admin/api/react/platform/users/{user_id}/{action}")
async def admin_api_react_platform_user_action(request: Request, user_id: int, action: str):
    if not has_platform_root_access(request):
        return {"ok": False, "error": "Выдавать доступ может только владелец платформы"}

    if action not in {"grant", "revoke"}:
        return {"ok": False, "error": "Неизвестное действие"}

    email = get_user_email_by_id(user_id)
    if not email:
        return {"ok": False, "error": "Пользователь не найден"}
    if is_platform_root_email(email):
        return {"ok": False, "error": "Root-аккаунт нельзя изменить из панели"}

    ok = set_platform_admin_access(
        email=email,
        granted_by=get_current_user_email(request),
        enabled=action == "grant",
    )

    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось обновить доступ"}


@app.post("/admin/api/react/doctors")
async def admin_api_react_add_doctor(request: Request):
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    full_name = (data.get("full_name") or "").strip()
    profession = (data.get("profession") or "").strip()

    if not full_name:
        return {"ok": False, "error": "Введите имя врача"}
    if not profession:
        return {"ok": False, "error": "Введите профессию врача"}

    ok = add_doctor(full_name, profession, clinic_id)
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось добавить врача"}


@app.post("/admin/api/react/doctors/{doctor_id}/update")
async def admin_api_react_update_doctor(request: Request, doctor_id: int):
    clinic_id = get_current_clinic_id(request)
    doctor = get_doctor_by_id(doctor_id, clinic_id)
    if not doctor:
        return {"ok": False, "error": "Врач не найден"}

    data = await request.json()
    full_name = (data.get("full_name") or "").strip()
    profession = (data.get("profession") or "").strip()

    if not full_name:
        return {"ok": False, "error": "Введите имя врача"}
    if not profession:
        return {"ok": False, "error": "Введите профессию врача"}

    ok = update_doctor(doctor_id, full_name, profession, clinic_id)
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось обновить врача"}


@app.post("/admin/api/react/doctors/{doctor_id}/delete")
async def admin_api_react_delete_doctor(request: Request, doctor_id: int):
    clinic_id = get_current_clinic_id(request)
    doctor = get_doctor_by_id(doctor_id, clinic_id)
    if not doctor:
        return {"ok": False, "error": "Врач не найден"}

    ok = deactivate_doctor(doctor_id, clinic_id)
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось отключить врача"}


def parse_admin_money(value) -> int | None:
    value_text = str(value if value is not None else "").strip().replace(" ", "")
    if value_text == "":
        return None
    try:
        parsed = int(value_text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def parse_admin_duration(value, default: int = 60) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed


def normalize_erp_date(value: str) -> str:
    value_text = (value or "").strip()
    if not value_text:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return datetime.strptime(value_text, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def normalize_erp_month(value: str) -> str:
    value_text = (value or "").strip()
    if not value_text:
        return datetime.now().strftime("%Y-%m")
    try:
        return datetime.strptime(value_text, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return ""


@app.post("/admin/api/react/erp/inventory")
async def admin_api_react_erp_add_inventory(request: Request):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    unit = (data.get("unit") or "шт").strip()[:24] or "шт"
    quantity = parse_admin_decimal(data.get("quantity"), 0)
    min_quantity = parse_admin_decimal(data.get("min_quantity"), 0)
    cost_per_unit = parse_admin_money(data.get("cost_per_unit")) or 0
    supplier = (data.get("supplier") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not name:
        return {"ok": False, "error": "Введите название позиции"}
    if quantity < 0 or min_quantity < 0:
        return {"ok": False, "error": "Количество не может быть отрицательным"}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO erp_inventory_items (
        clinic_id, name, category, unit, quantity, min_quantity,
        cost_per_unit, supplier, notes, is_active, created_at, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (clinic_id, name, category, unit, quantity, min_quantity, cost_per_unit, supplier, notes))
    conn.commit()
    conn.close()

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/erp/inventory/{item_id}/update")
async def admin_api_react_erp_update_inventory(request: Request, item_id: int):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    unit = (data.get("unit") or "шт").strip()[:24] or "шт"
    quantity = parse_admin_decimal(data.get("quantity"), 0)
    min_quantity = parse_admin_decimal(data.get("min_quantity"), 0)
    cost_per_unit = parse_admin_money(data.get("cost_per_unit")) or 0
    supplier = (data.get("supplier") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not name:
        return {"ok": False, "error": "Введите название позиции"}
    if quantity < 0 or min_quantity < 0:
        return {"ok": False, "error": "Количество не может быть отрицательным"}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE erp_inventory_items
    SET name = ?,
        category = ?,
        unit = ?,
        quantity = ?,
        min_quantity = ?,
        cost_per_unit = ?,
        supplier = ?,
        notes = ?,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = ? AND clinic_id = ? AND is_active = 1
    """, (name, category, unit, quantity, min_quantity, cost_per_unit, supplier, notes, item_id, clinic_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()

    return {"ok": bool(changed), "data": get_admin_react_payload(request), "error": "" if changed else "Позиция не найдена"}


@app.post("/admin/api/react/erp/inventory/{item_id}/delete")
async def admin_api_react_erp_delete_inventory(request: Request, item_id: int):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE erp_inventory_items
    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
    WHERE id = ? AND clinic_id = ?
    """, (item_id, clinic_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return {"ok": bool(changed), "data": get_admin_react_payload(request), "error": "" if changed else "Позиция не найдена"}


@app.post("/admin/api/react/erp/expenses")
async def admin_api_react_erp_add_expense(request: Request):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    expense_date = normalize_erp_date(data.get("expense_date") or "")
    category = (data.get("category") or "").strip()
    title = (data.get("title") or "").strip()
    amount = parse_admin_money(data.get("amount"))
    vendor = (data.get("vendor") or "").strip()
    payment_method = (data.get("payment_method") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not expense_date:
        return {"ok": False, "error": "Введите дату в формате YYYY-MM-DD"}
    if not title:
        return {"ok": False, "error": "Введите название расхода"}
    if amount is None or amount <= 0:
        return {"ok": False, "error": "Введите сумму расхода числом"}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO erp_expenses (
        clinic_id, expense_date, category, title, amount,
        vendor, payment_method, notes, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (clinic_id, expense_date, category, title, amount, vendor, payment_method, notes))
    conn.commit()
    conn.close()

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/erp/expenses/{expense_id}/delete")
async def admin_api_react_erp_delete_expense(request: Request, expense_id: int):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    DELETE FROM erp_expenses
    WHERE id = ? AND clinic_id = ?
    """, (expense_id, clinic_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return {"ok": bool(changed), "data": get_admin_react_payload(request), "error": "" if changed else "Расход не найден"}


@app.post("/admin/api/react/erp/salaries")
async def admin_api_react_erp_upsert_salary(request: Request):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    try:
        doctor_id = int(data.get("doctor_id") or 0)
    except (TypeError, ValueError):
        doctor_id = 0

    salary_month = normalize_erp_month(data.get("salary_month") or "")
    amount = parse_admin_money(data.get("amount"))
    is_paid = 1 if data.get("is_paid") in {True, "true", "1", 1, "on", "yes"} else 0
    notes = (data.get("notes") or "").strip()

    if doctor_id <= 0:
        return {"ok": False, "error": "Выберите врача"}
    if not salary_month:
        return {"ok": False, "error": "Введите месяц в формате YYYY-MM"}
    if amount is None or amount < 0:
        return {"ok": False, "error": "Введите сумму зарплаты числом"}

    doctor = get_doctor_by_id(doctor_id, clinic_id)
    if not doctor:
        return {"ok": False, "error": "Врач не найден"}

    doctor_name = (doctor.get("full_name") or "").strip()
    profession = (doctor.get("profession") or "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO erp_doctor_salaries (
        clinic_id, doctor_id, salary_month, doctor_name, profession,
        amount, is_paid, notes, created_at, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT(clinic_id, doctor_id, salary_month) DO UPDATE SET
        doctor_name = excluded.doctor_name,
        profession = excluded.profession,
        amount = excluded.amount,
        is_paid = excluded.is_paid,
        notes = excluded.notes,
        updated_at = CURRENT_TIMESTAMP
    """, (clinic_id, doctor_id, salary_month, doctor_name, profession, amount, is_paid, notes))
    conn.commit()
    conn.close()

    return {"ok": True, "data": get_admin_react_payload(request)}


@app.post("/admin/api/react/erp/salaries/{salary_id}/update")
async def admin_api_react_erp_update_salary(request: Request, salary_id: int):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    salary_month = normalize_erp_month(data.get("salary_month") or "")
    amount = parse_admin_money(data.get("amount"))
    is_paid = 1 if data.get("is_paid") in {True, "true", "1", 1, "on", "yes"} else 0
    notes = (data.get("notes") or "").strip()

    if not salary_month:
        return {"ok": False, "error": "Введите месяц в формате YYYY-MM"}
    if amount is None or amount < 0:
        return {"ok": False, "error": "Введите сумму зарплаты числом"}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE erp_doctor_salaries
        SET salary_month = ?,
            amount = ?,
            is_paid = ?,
            notes = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND clinic_id = ?
        """, (salary_month, amount, is_paid, notes, salary_id, clinic_id))
        changed = cursor.rowcount
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return {"ok": False, "error": "Для этого врача за выбранный месяц зарплата уже есть"}
    conn.close()

    return {"ok": bool(changed), "data": get_admin_react_payload(request), "error": "" if changed else "Зарплата не найдена"}


@app.post("/admin/api/react/erp/salaries/{salary_id}/delete")
async def admin_api_react_erp_delete_salary(request: Request, salary_id: int):
    ensure_erp_tables()
    clinic_id = get_current_clinic_id(request)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    DELETE FROM erp_doctor_salaries
    WHERE id = ? AND clinic_id = ?
    """, (salary_id, clinic_id))
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    return {"ok": bool(changed), "data": get_admin_react_payload(request), "error": "" if changed else "Зарплата не найдена"}


@app.post("/admin/api/react/services")
async def admin_api_react_add_service(request: Request):
    clinic_id = get_current_clinic_id(request)
    data = await request.json()

    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    description = (data.get("description") or "").strip()
    price = parse_admin_money(data.get("price"))
    duration_minutes = parse_admin_duration(data.get("duration_minutes") or 60)

    if not name:
        return {"ok": False, "error": "Введите название услуги"}
    if price is None:
        return {"ok": False, "error": "Введите цену услуги числом"}
    if duration_minutes < 5 or duration_minutes > 480:
        return {"ok": False, "error": "Длительность должна быть от 5 до 480 минут"}

    ok = add_service(
        name=name,
        price=price,
        duration_minutes=duration_minutes,
        clinic_id=clinic_id,
        category=category or None,
        description=description or None,
    )
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось добавить услугу"}


@app.post("/admin/api/react/services/{service_id}/update")
async def admin_api_react_update_service(request: Request, service_id: int):
    clinic_id = get_current_clinic_id(request)
    service = get_service_by_id(service_id, clinic_id)
    if not service:
        return {"ok": False, "error": "Услуга не найдена"}

    data = await request.json()
    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()
    description = (data.get("description") or "").strip()
    price = parse_admin_money(data.get("price"))
    duration_minutes = parse_admin_duration(data.get("duration_minutes") or service.get("duration_minutes") or 60)

    if not name:
        return {"ok": False, "error": "Введите название услуги"}
    if price is None:
        return {"ok": False, "error": "Введите цену услуги числом"}
    if duration_minutes < 5 or duration_minutes > 480:
        return {"ok": False, "error": "Длительность должна быть от 5 до 480 минут"}

    ok = update_service(
        service_id=service_id,
        name=name,
        price=price,
        duration_minutes=duration_minutes,
        category=category,
        description=description,
    )
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось обновить услугу"}


@app.post("/admin/api/react/services/{service_id}/delete")
async def admin_api_react_delete_service(request: Request, service_id: int):
    clinic_id = get_current_clinic_id(request)
    service = get_service_by_id(service_id, clinic_id)
    if not service:
        return {"ok": False, "error": "Услуга не найдена"}

    ok = deactivate_service_by_id(service_id)
    return {"ok": bool(ok), "data": get_admin_react_payload(request), "error": "" if ok else "Не удалось отключить услугу"}


@app.post("/admin/bookings/{booking_id}/cancel")
async def admin_cancel_booking(booking_id: int):
    cancel_booking_by_id(booking_id)
    return RedirectResponse(url="/admin/bookings", status_code=303)


@app.post("/admin/bookings/{booking_id}/complete")
async def admin_complete_booking(booking_id: int):
    mark_booking_completed(booking_id)
    return RedirectResponse(url="/admin/bookings", status_code=303)


@app.post("/admin/bookings/{booking_id}/no-show")
async def admin_no_show_booking(booking_id: int):
    mark_booking_no_show(booking_id)
    return RedirectResponse(url="/admin/bookings", status_code=303)


@app.post("/admin/services/add")
async def admin_add_service(
    request: Request,
    name: str = Form(...),
    price: int = Form(None),
    duration_minutes: int = Form(60),
    category: str = Form(""),
    description: str = Form(""),
):
    clinic_id = get_current_clinic_id(request)
    if name:
        add_service(
            name,
            price=price,
            duration_minutes=duration_minutes,
            clinic_id=clinic_id,
            category=category if category else None,
            description=description if description else None,
        )
    return RedirectResponse(url="/admin/services", status_code=303)


@app.post("/admin/services/{service_id}/update")
async def admin_update_service(request: Request, service_id: int, name: str = Form(None), price: int = Form(None), duration_minutes: int = Form(None)):
    clinic_id = get_current_clinic_id(request)
    service = get_service_by_id(service_id, clinic_id)
    if not service:
        return RedirectResponse(url="/admin/services", status_code=303)
    update_service(service_id, name=name, price=price, duration_minutes=duration_minutes)
    return RedirectResponse(url="/admin/services", status_code=303)


@app.post("/admin/services/{service_id}/deactivate")
async def admin_deactivate_service(request: Request, service_id: int):
    clinic_id = get_current_clinic_id(request)
    service = get_service_by_id(service_id, clinic_id)
    if not service:
        return RedirectResponse(url="/admin/services", status_code=303)
    deactivate_service_by_id(service_id)
    return RedirectResponse(url="/admin/services", status_code=303)


@app.get("/admin/services/{service_id}/edit", response_class=HTMLResponse)
async def admin_edit_service(service_id: int, request: Request):
    clinic_id = get_current_clinic_id(request)

    service = get_service_by_id(service_id, clinic_id)

    if not service:
        return RedirectResponse(url="/admin/services", status_code=303)

    form_html = f"""
    <div class='card'>
        <h3 style='margin-bottom: 20px; font-size: 18px; color: #2d3748;'>✏️ Редактировать услугу</h3>
        <form method='post' action='/admin/services/{service_id}/edit' style='border: none; background: #f9fafb; padding: 20px;'>
            <div class='form-row'>
                <div class='form-group'>
                    <label>Название услуги <span style='color: #f56565;'>*</span></label>
                    <input type='text' name='name' value='{service['name']}' placeholder='Например: УЗИ диагностика' required style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Категория</label>
                    <input type='text' name='category' value='{service.get('category', '')}' placeholder='Например: Диагностика' style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Цена (тг)</label>
                    <input type='number' name='price' value='{service.get('price', '')}' min='0' placeholder='0' style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Длительность (мин)</label>
                    <input type='number' name='duration_minutes' value='{service.get('duration_minutes', 60)}' min='15' step='15' style='border: 1px solid #cbd5e0;'>
                </div>
            </div>
            <div class='form-row'>
                <div class='form-group' style='width: 100%;'>
                    <label>Описание</label>
                    <textarea name='description' placeholder='Краткое описание услуги...' rows='2' style='border: 1px solid #cbd5e0; width: 100%; resize: vertical;'>{service.get('description', '')}</textarea>
                </div>
            </div>
            <div class='form-row'>
                <div class='form-group'>
                    <label>Порядок сортировки</label>
                    <input type='number' name='sort_order' value='{service.get('sort_order', 0)}' min='0' style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Статус</label>
                    <select name='is_active' style='border: 1px solid #cbd5e0;'>
                        <option value='1' {'selected' if service.get('is_active', True) else ''}>Активна</option>
                        <option value='0' {'selected' if not service.get('is_active', True) else ''}>Неактивна</option>
                    </select>
                </div>
            </div>
            <div style='margin-top: 20px;'>
                <button type='submit' class='btn btn-primary'>✓ Сохранить изменения</button>
                <a href='/admin/services' class='btn btn-secondary' style='margin-left: 10px;'>← Назад к списку</a>
            </div>
        </form>
    </div>
    """

    return HTMLResponse(render_admin_layout('Редактировать услугу', form_html))


@app.post("/admin/services/{service_id}/edit")
async def admin_update_service(
    request: Request,
    service_id: int,
    name: str = Form(...),
    category: str = Form(""),
    price: int = Form(None),
    duration_minutes: int = Form(60),
    description: str = Form(""),
    sort_order: int = Form(0),
    is_active: int = Form(1)
):
    clinic_id = get_current_clinic_id(request)
    service = get_service_by_id(service_id, clinic_id)
    if not service:
        return RedirectResponse(url="/admin/services", status_code=303)

    update_service(
        service_id=service_id,
        name=name,
        category=category if category else None,
        price=price,
        duration_minutes=duration_minutes,
        description=description if description else None,
        sort_order=sort_order,
        is_active=bool(is_active)
    )
    return RedirectResponse(url="/admin/services", status_code=303)


@app.post("/admin/faq/add")
async def admin_add_faq(request: Request, question: str = Form(...), answer: str = Form(...)):
    clinic_id = get_current_clinic_id(request)
    if question and answer:
        add_faq_item(question, answer, clinic_id)
    return RedirectResponse(url="/admin/faq", status_code=303)


@app.post("/admin/faq/{faq_id}/delete")
async def admin_delete_faq(request: Request, faq_id: int):
    clinic_id = get_current_clinic_id(request)
    remove_faq_item(str(faq_id), clinic_id)
    return RedirectResponse(url="/admin/faq", status_code=303)


@app.get("/admin/services", response_class=HTMLResponse)
async def admin_services(request: Request, message: str = None):
    clinic_id = get_current_clinic_id(request)
    services = get_all_active_services(clinic_id)

    form_html = """
    <div class='card'>
        <h3 style='margin-bottom: 20px; font-size: 18px; color: #2d3748;'>➕ Добавить новую услугу</h3>
        <form method='post' action='/admin/services/add' style='border: none; background: #f9fafb; padding: 20px;'>
            <div class='form-row'>
                <div class='form-group'>
                    <label>Название услуги <span style='color: #f56565;'>*</span></label>
                    <input type='text' name='name' placeholder='Например: УЗИ диагностика' required style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Категория</label>
                    <input type='text' name='category' placeholder='Например: Диагностика' style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Цена (тг)</label>
                    <input type='number' name='price' value='' min='0' placeholder='0' style='border: 1px solid #cbd5e0;'>
                </div>
                <div class='form-group'>
                    <label>Длительность (мин)</label>
                    <input type='number' name='duration_minutes' value='60' min='15' step='15' style='border: 1px solid #cbd5e0;'>
                </div>
            </div>
            <div class='form-row'>
                <div class='form-group' style='width: 100%;'>
                    <label>Описание</label>
                    <textarea name='description' placeholder='Краткое описание услуги...' rows='2' style='border: 1px solid #cbd5e0; width: 100%; resize: vertical;'></textarea>
                </div>
            </div>
            <button type='submit' class='btn btn-primary'>✓ Добавить услугу</button>
        </form>
    </div>
    """

    if not services:
        content = form_html + '<div class="empty" style="margin-top: 20px;"><div class="empty-icon">📋</div><p>Услуги пока не добавлены</p></div>'
    else:
        rows = ""
        for service in services:
            price_display = f"{service.get('price')} тг" if service.get('price') else "—"
            duration = service.get('duration_minutes', 60)
            category = service.get('category', '—')
            description = service.get('description', '—')
            status = "✅ Активна" if service.get('is_active', True) else "❌ Неактивна"
            status_class = "status-active" if service.get('is_active', True) else "status-inactive"
            rows += f"""
            <tr>
                <td style='font-weight: 600;'>{service['id']}</td>
                <td>{service['name']}</td>
                <td>{category}</td>
                <td>{price_display}</td>
                <td>{duration} мин</td>
                <td style='max-width: 260px; white-space: normal; word-break: break-word;'>{description}</td>
                <td><span class='{status_class}'>{status}</span></td>
                <td style='min-width: 250px;'>
                    <div class='action-buttons'>
                        <a href='/admin/services/{service['id']}/edit' class='btn btn-secondary' title='Редактировать'>✏️ Редактировать</a>
                        <form method='post' action='/admin/services/{service['id']}/deactivate' style='display:inline; border: none; background: none; padding: 0; margin: 0;' onsubmit='return confirm("Удалить услугу?");'>
                            <button class='btn btn-danger' type='submit' title='Удалить'>🗑️ Удалить</button>
                        </form>
                    </div>
                </td>
            </tr>
            """
        table_html = f"""
        <div class='card'>
            <h3 style='margin-bottom: 16px; font-size: 18px; color: #2d3748;'>📊 Список услуг ({len(services)})</h3>
            <div class='table-wrapper'>
                <table>
                    <thead>
                        <tr style='background: #f7fafc;'>
                            <th style='width: 60px;'>№</th>
                            <th style='min-width: 180px;'>Название</th>
                            <th style='width: 140px;'>Категория</th>
                            <th style='width: 120px;'>Цена</th>
                            <th style='width: 120px;'>Длительность</th>
                            <th style='min-width: 240px;'>Описание</th>
                            <th style='width: 120px;'>Статус</th>
                            <th style='width: 260px;'>Действия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows}
                    </tbody>
                </table>
            </div>
        </div>
        """
        content = form_html + table_html

    return HTMLResponse(render_admin_layout('🔧 Управление услугами', content, message))

from fastapi import Request

@app.get("/admin/faq", response_class=HTMLResponse)
async def admin_faq(request: Request, message: str = None):
    clinic_id = get_current_clinic_id(request)
    faq_items = get_all_active_faq_items(clinic_id)

    form_html = """
    <div class='card'>
        <h3 style='margin-bottom: 20px; font-size: 18px; color: #2d3748;'>➕ Добавить новый вопрос</h3>
        <form method='post' action='/admin/faq/add' style='border: none; background: #f9fafb; padding: 20px;'>
            <div class='form-group'>
                <label>Вопрос <span style='color: #f56565;'>*</span></label>
                <input type='text' name='question' placeholder='Например: Какие способы оплаты вы принимаете?' required style='border: 1px solid #cbd5e0;'>
            </div>
            <div class='form-group'>
                <label>Ответ <span style='color: #f56565;'>*</span></label>
                <textarea name='answer' placeholder='Введите подробный ответ...' rows='6' required style='border: 1px solid #cbd5e0;'></textarea>
            </div>
            <button type='submit' class='btn btn-primary'>✓ Добавить вопрос</button>
        </form>
    </div>
    """

    if not faq_items:
        content = form_html + '<div class="empty" style="margin-top: 20px;"><div class="empty-icon">❓</div><p>Вопросы пока не добавлены</p></div>'
    else:
        rows = ""
        for item in faq_items:
            answer_preview = item['answer'][:100] + "..." if len(item['answer']) > 100 else item['answer']
            rows += f"""
            <tr>
                <td style='font-weight: 600; width: 30%;'>{item['question']}</td>
                <td style='width: 60%; color: #4a5568;'>{answer_preview}</td>
                <td style='width: 10%;'>
                    <form method='post' action='/admin/faq/{item['id']}/delete' style='display:inline; border: none; background: none; padding: 0; margin: 0;' onsubmit='return confirm("Удалить вопрос?");'>
                        <button class='btn btn-danger' style='font-size: 12px; padding: 6px 12px;' type='submit' title='Удалить'>🗑️ Удал.</button>
                    </form>
                </td>
            </tr>
            """
        table_html = f"""
        <div class='card'>
            <h3 style='margin-bottom: 16px; font-size: 18px; color: #2d3748;'>📚 Список вопросов ({len(faq_items)})</h3>
            <table>
                <thead>
                    <tr style='background: #f7fafc;'>
                        <th>Вопрос</th>
                        <th>Ответ</th>
                        <th style='text-align: center;'>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
        """
        content = form_html + table_html

    return HTMLResponse(render_admin_layout('❓ Часто задаваемые вопросы', content, message))


# =========================
# Telegram Bot Routes
# =========================

QUESTION_TOPIC_KEYWORDS = {
    "services": [
        "какие услуги", "что вы делаете", "что вы предлагаете", "список услуг",
        "услуги", "услуга", "какие процедуры", "что у вас есть", "что можете",
        "какие направления", "что делаете", "что лечите", "перечень", "прейскурант",
        "services", "what services", "which services", "what do you offer",
    ],
    "price": [
        "сколько", "сколько стоит", "стоимость", "стоимости", "цена", "цену",
        "стоит", "прайс", "почём", "price", "cost", "pricing",
    ],
    "location": [
        "адрес", "где вы", "где находитесь", "как добраться", "как вас найти",
        "где клиника", "где приём", "location", "where are you", "where located",
        "ориентир", "как проехать", "как пройти",
        "локация", "местоположение", "куда подъехать", "куда приехать",
        "где находится", "где вас найти", "карта", "2гис", "2gis",
    ],
    "schedule": [
        "график", "время работы", "режим работы", "расписание", "во сколько открываетесь",
        "до скольки работаете", "когда работаете", "schedule", "hours", "working hours",
        "принимаете до", "принимаете с", "со скольки", "до скольки",
        "с какого времени", "до какого времени", "во сколько закрываетесь",
        "когда открываетесь", "когда закрываетесь", "часы работы",
        "во сколько работаете", "со скольки работаете", "до какого часа",
        "в какие дни работаете", "какие дни работаете", "по каким дням",
        "по каким дням работаете", "рабочие дни", "дни работы",
    ],
    "doctor": [
        "врач", "доктор", "стоматолог", "дантист", "кто принимает",
        "как зовут", "имя врача", "фамилия", "фамилия врача", "surname", "dentist", "doctor",
        "специалист", "кто ведёт", "кто ведет",
    ],
}
def get_working_hours_reply(clinic_id: int = 1) -> str:
    settings = get_clinic_settings(clinic_id)
    work_start = settings.get("work_start") or "10:00"
    work_end = settings.get("work_end") or "19:00"
    day_map = {
        "0": "пн",
        "1": "вт",
        "2": "ср",
        "3": "чт",
        "4": "пт",
        "5": "сб",
        "6": "вс",
    }
    working_days = [
        day_map.get(item.strip())
        for item in str(settings.get("working_days") or "0,1,2,3,4,5").split(",")
        if day_map.get(item.strip())
    ]
    days_text = ", ".join(working_days) if working_days else "по рабочим дням"
    return f"⏰ Мы работаем с {work_start} до {work_end} ({days_text}). Могу помочь подобрать удобное время для записи."


def get_clinic_location_reply(clinic_id: int = 1) -> str:
    settings = get_clinic_settings(clinic_id)
    clinic_name = (settings.get("clinic_name") or "клиника").strip()
    address = (settings.get("address") or "").strip()

    if address:
        return f"📍 Клиника «{clinic_name}» находится по адресу: {address}."

    return "📍 Адрес пока не добавлен в настройках клиники. Я могу передать вопрос администратору."


def get_clinic_greeting_reply(clinic_id: int = 1, user_name: str = "") -> str:
    settings = get_clinic_settings(clinic_id)
    clinic_name = (settings.get("clinic_name") or "наша клиника").strip()
    first_name = (user_name or "").strip().split()[0] if user_name else ""
    name_part = f", {first_name}" if first_name else ""
    return (
        f"Здравствуйте{name_part}! 👋 Рады видеть вас в клинике «{clinic_name}».\n\n"
        "Помогу записаться, перенести визит, отменить запись или ответить на вопрос."
    )


def detect_question_topic(message: str) -> str:
    text = (message or "").lower().replace("ё", "е").strip()
    if any(keyword in text for keyword in QUESTION_TOPIC_KEYWORDS.get("schedule", [])):
        return "schedule"

    for topic, keywords in QUESTION_TOPIC_KEYWORDS.items():
        if topic == "schedule":
            continue
        if any(keyword in text for keyword in keywords):
            return topic
    # Broad "question" detection: starts with wh-word OR ends with ?
    if "?" in text or any(text.startswith(word) for word in (
        "кто", "что", "где", "когда", "как", "сколько", "какой", "какая", "какие",
        "есть ли", "можно ли", "работаете", "принимаете",
    )):
        return "general"
    return ""


def format_service_summary(service: dict) -> str:
    name = (service.get("name") or "Услуга").strip()
    extras = []
    price = service.get("price")
    duration = service.get("duration_minutes")
    if price is not None:
        extras.append(f"{int(price):,}".replace(",", " ") + " тг")
    if duration:
        extras.append(f"~{duration} мин")
    return f"{name} — {', '.join(extras)}" if extras else name


def is_service_question(message: str) -> bool:
    return detect_question_topic(message) == "services"


def get_services_reply(clinic_id: int = 1) -> str:
    """Format active services as a concise, user-friendly reply."""
    services = get_all_active_services(clinic_id)

    if not services:
        return get_no_services_response()

    services_list = "\n".join([f"• {format_service_summary(service)}" for service in services[:8]])
    if len(services) > 8:
        services_list += "\n• И другие позиции по запросу."
    return get_services_list_response(services_list)

def is_doctors_question(text: str) -> bool:
    text_low = (text or "").lower().replace("ё", "е")

    phrases = [
        "какие врачи",
        "какие доктора",
        "какие специалисты",
        "кто работает",
        "какие у вас врачи",
        "какие есть врачи",
        "врачи есть",
        "список врачей",
        "список специалистов",
        "есть ли врач",
        "есть ли стоматолог",
        "есть ли дантист",
        "есть ли ортодонт",
    ]



    return any(p in text_low for p in phrases)



def is_doctor_list_request(text: str) -> bool:
    text_low = (text or "").lower().replace("ё", "е")
    patterns = [
        "какие есть",
        "кто есть",
        "какие доступны",
        "кто доступен",
        "какие свободны",
        "кто свободен",
        "свободные врачи",
        "свободные специалисты",
        "доступные врачи",
        "доступные специалисты",
    ]
    return any(pattern in text_low for pattern in patterns)



def get_doctors_reply(clinic_id: int = 1) -> str:
    doctors = get_active_doctors(clinic_id)

    if not doctors:
        return "Сейчас список врачей пуст. Администратор скоро добавит специалистов."

    text = "👩‍⚕️ У нас работают:\n\n"

    for d in doctors:
        text += f"• {d['full_name']} — {d['profession']}\n"

    text += "\nЕсли хотите, я могу помочь записаться к нужному специалисту."
    return text

def find_service_for_price_query(text: str, clinic_id: int = 1):
    text_low = (text or "").lower().replace("ё", "е")
    best_match = None
    best_score = 0

    for service in get_all_active_services(clinic_id):
        name = (service.get("name") or "").strip()
        name_low = name.lower()
        if not name_low:
            continue
        if name_low in text_low:
            return service

        tokens = [token for token in re.findall(r"[a-zа-яё0-9]+", name_low) if len(token) > 2]
        score = sum(1 for token in tokens if token in text_low)
        if score > best_score:
            best_score = score
            best_match = service

    return best_match if best_score > 0 else None


def get_price_overview_reply(clinic_id: int = 1) -> str:
    priced_services = [service for service in get_all_active_services(clinic_id) if service.get("price") is not None]
    if not priced_services:
        return ""

    items = "\n".join([f"• {format_service_summary(service)}" for service in priced_services[:6]])
    return get_price_overview_response(items)


def answer_direct_question(user_text: str, clinic_id: int = 1) -> str:
    topic = detect_question_topic(user_text)
    text_low = (user_text or "").lower().replace("ё", "е").strip()

    if topic == "schedule":
        return get_working_hours_reply(clinic_id)

    if topic == "services":
        return get_services_reply(clinic_id)

    if topic == "price":
        service = find_service_for_price_query(user_text, clinic_id)
        if service:
            if service.get("price") is not None:
                return get_price_response(service["name"], service["price"], service.get("duration_minutes", 60))
            return get_price_not_available_response(service["name"])
        # Try FAQ first
        faq_answer = find_faq_answer(user_text, clinic_id)
        if faq_answer:
            return get_faq_response(faq_answer)
        overview = get_price_overview_reply(clinic_id)
        if overview:
            return overview
        return get_info_missing_response("стоимости")


    # Always try FAQ for known topics and for general questions
    faq_answer = find_faq_answer(user_text, clinic_id)
    if faq_answer:
        return get_faq_response(faq_answer)

    if topic == "doctor":
        return get_info_missing_response("врачу")
    if topic == "location":
        return get_clinic_location_reply(clinic_id)

    if topic == "general":
        # Fuzzy FAQ search: find the FAQ item with most keyword overlap
        try:
            faq_items = get_all_active_faq_items(clinic_id)
            if faq_items:
                best_item = None
                best_score = 0
                user_words = set(re.findall(r"[а-яa-z]{3,}", text_low))
                for item in faq_items:
                    q_low = (item.get("question") or "").lower().replace("ё", "е")
                    q_words = set(re.findall(r"[а-яa-z]{3,}", q_low))
                    score = len(user_words & q_words)
                    if score > best_score:
                        best_score = score
                        best_item = item
                if best_item and best_score >= 2:
                    return get_faq_response(best_item["answer"])
        except Exception:
            pass
        return get_info_missing_response("данному вопросу")

    return get_info_missing_response("данному вопросу")



# ── Детектор запроса на изменение конкретного поля ───────────────────────────
_EDIT_NAME_KW    = [
    "изменить имя", "измени имя", "поменять имя", "поменяй имя",
    "другое имя", "исправить имя", "исправь имя", "исправьте имя",
    "другое фио", "имя неверно", "имя неправильно", "зовут не так",
    "не то имя", "имя не то", "смените имя", "смени имя",
    "меня зовут",  # клиент сразу даёт новое имя
    "имя неправ", "неверное имя", "неправильное имя",
    "имя ошибка", "ошибка в имени", "имя не верно",
]
_EDIT_PHONE_KW   = [
    "изменить телефон", "измени телефон", "поменять телефон", "поменяй телефон",
    "другой номер", "другой телефон", "исправить номер", "исправь номер",
    "номер неверный", "номер не тот", "не тот номер", "смените номер",
    "смени номер", "номер неправильный", "неверный номер", "номер ошибка",
    "ошибка в номере", "телефон не тот", "не тот телефон", "телефон не верный", "изменить номер", "поменять номер", "поменяй номер", "другой номер", "другой телефон", "исправить номер", "исправь номер",
]
_EDIT_SERVICE_KW = [
    "изменить услугу", "измени услугу", "поменять услугу", "поменяй услугу",
    "другая услуга", "другую услугу", "не та услуга", "услуга не та",
    "сменить услугу", "смени услугу", "хочу другую услугу",
    "неправильная услуга", "услуга не верна", "неверная услуга",
]
_EDIT_TIME_KW    = [
    "изменить время", "измени время", "поменять время", "поменяй время",
    "другое время", "другую дату", "перенести", "перенос",
    "другой день", "другое окно",
]

def detect_field_edit_request(text: str) -> str:
    """Возвращает имя поля которое клиент хочет исправить, или ''."""
    t = text.lower().replace("ё", "е").strip()
    if any(kw in t for kw in _EDIT_NAME_KW):
        return "full_name"
    if any(kw in t for kw in _EDIT_PHONE_KW):
        return "phone"
    if any(kw in t for kw in _EDIT_SERVICE_KW):
        return "service"
    if any(kw in t for kw in _EDIT_TIME_KW):
        return "preferred_datetime"
    return ""

RUNTIME_SESSIONS = {}
BOOKING_KEYWORDS = [
    "запис", "хочу запис", "нужна запись", "консультац", "на процедуру",
    "забронировать", "подобрать время", "хочу к врачу", "хочу прийти",
    "хочу попасть", "нужен врач", "нужен специалист", "хочу получить",
    "запишите", "запиши ", "можете записать", "хочу к вам",
    "хочу записаться", "как записаться", "можно записаться",
    "когда можно прийти", "нужна консультация", "хочу на приём",
    "записаться на", "нужно записаться", "хочу попасть",
]
CANCEL_KEYWORDS = [
    "отмен", "отмени", "отмена", "хочу отменить", "удали запись", "удали",
    "не приду", "не смогу прийти", "отменяй", "сними запись", "убери запись",
    "не смогу", "придти не смогу", "не получится прийти",
]
RESCHEDULE_KEYWORDS = [
    "перенес", "перенест", "перенести", "перенос", "другое время",
    "изменить время", "перепис", "поменять время", "переставить",
    "другое окно", "надо перенести",
]
OPERATOR_KEYWORDS = [
    "оператор", "администратор", "человек", "живой человек", "сотрудник", "позвоните",
    "свяжите", "связаться с человеком", "свяжите с человеком", "соедините", "соедините с человеком",
    "позовите человека", "позовите администратора", "нужен человек", "нужен оператор",
    "нужен администратор", "хочу с человеком", "хочу поговорить с человеком",
    "менеджер", "консультант", "живой оператор", "реальный человек",
]
WEEKDAY_MAP = {
    "понедельник": 0,
    "вторник": 1,
    "среду": 2,
    "среда": 2,
    "четверг": 3,
    "пятницу": 4,
    "пятница": 4,
    "субботу": 5,
    "суббота": 5,
    "воскресенье": 6,
}
MONTH_MAP = {
    "январь": 1, "января": 1,
    "февраль": 2, "февраля": 2,
    "март": 3, "марта": 3,
    "апрель": 4, "апреля": 4,
    "май": 5, "мая": 5,
    "июнь": 6, "июня": 6,
    "июль": 7, "июля": 7,
    "август": 8, "августа": 8,
    "сентябрь": 9, "сентября": 9,
    "октябрь": 10, "октября": 10,
    "ноябрь": 11, "ноября": 11,
    "декабрь": 12, "декабря": 12,
}


def get_default_session() -> dict:
    return {
        "flow_state": "idle",
        "doctor_profession": "",
        "service": "",
        "phone": "",
        "full_name": "",
        "preferred_datetime": "",
        "pending_datetime": "",
        "pending_action": "",
        "suggested_slots": [],
        "last_user_message": "",
        "last_bot_message": "",
        "repeat_count": 0,
        "last_requested_action": "",
        "last_intent": "",
    }


def get_runtime_session(chat_id: str, current_state: dict = None, telegram_name: str = "") -> dict:
    session = RUNTIME_SESSIONS.get(chat_id, get_default_session())
    current_state = current_state or {}

    for field in ["service", "doctor_profession", "phone", "full_name", "preferred_datetime"]:
        if current_state.get(field) and not session.get(field):
            session[field] = current_state.get(field, "")

    if telegram_name and not session.get("full_name"):
        session["full_name"] = telegram_name

    RUNTIME_SESSIONS[chat_id] = session
    return session


def save_runtime_session(chat_id: str, **updates) -> dict:
    session = RUNTIME_SESSIONS.get(chat_id, get_default_session())
    for key, value in updates.items():
        if value is not None:
            session[key] = value
    RUNTIME_SESSIONS[chat_id] = session
    return session


def reset_runtime_session(chat_id: str, preserve_contact: bool = False):
    previous = RUNTIME_SESSIONS.get(chat_id, {})
    fresh_session = get_default_session()
    if preserve_contact:
        for field in ["full_name", "phone"]:
            if previous.get(field):
                fresh_session[field] = previous.get(field, "")
    RUNTIME_SESSIONS[chat_id] = fresh_session
    return RUNTIME_SESSIONS[chat_id]


def sync_user_state(chat_id: str, session: dict, intent: str = "booking", booking_status: str = "in_progress"):
    next_field = "completed"
    effective_datetime = session.get("pending_datetime") or session.get("preferred_datetime", "")
    if not session.get("service"):
        next_field = "service"
    elif not session.get("full_name"):
        next_field = "full_name"
    elif not session.get("phone"):
        next_field = "phone"
    elif not effective_datetime:
        next_field = "preferred_datetime"

    status = "ready_to_book" if next_field == "completed" else "collecting"
    save_user_state(chat_id, {
        "service": session.get("service", ""),
        "full_name": session.get("full_name", ""),
        "phone": session.get("phone", ""),
        "preferred_datetime": effective_datetime,
        "status": status,
        "next_field": next_field,
        "booking_status": booking_status,
        "intent": intent,
    })


def detect_intent(text: str) -> str:
    text_low = text.lower().replace("ё", "е").strip()
    if text_low in {"записаться", "новая запись", "хочу записаться"}:
        return "booking"
    if text_low in {"отменить запись", "да, отменить"}:
        return "cancel"
    if text_low in {"изменить время", "перенести запись", "перенос записи"}:
        return "reschedule"
    # High priority: actionable intents
    dental_words = ["зуб", "зуба", "зубы", "зубов", "моляр", "корень"]
    dental_remove_words = ["удалить", "удаление", "вырвать", "выдернуть"]

    if any(w in text_low for w in dental_words) and any(w in text_low for w in dental_remove_words):
        return "booking"
    dental_words = ["зуб", "зуба", "зубы", "зубов", "моляр", "корень"]
    dental_remove_words = ["удалить", "удаление", "вырвать", "выдернуть"]

    if any(w in text_low for w in dental_words) and any(w in text_low for w in dental_remove_words):
        return "booking"

    if any(word in text_low for word in CANCEL_KEYWORDS):
        return "cancel"
    if any(word in text_low for word in RESCHEDULE_KEYWORDS):
        return "reschedule"
    if any(word in text_low for word in OPERATOR_KEYWORDS):
        return "operator"
    # Booking intent checked BEFORE question detection so that
    # "как к вам записаться?" / "можно ли записаться?" are treated as booking, not question
    if any(word in text_low for word in BOOKING_KEYWORDS):
        return "booking"
    # Question detection — topic match (price/location/schedule/doctor/services/general)
    topic = detect_question_topic(text_low)
    if topic:
        return "question"
    return "unknown"

def is_vague_doctor_request(text: str) -> bool:
    text_low = (text or "").lower().replace("ё", "е").strip()

    vague_phrases = [
        "хочу записаться к врачу",
        "запишите к врачу",
        "нужно к врачу",
        "к врачу",
        "на прием к врачу",
        "на приём к врачу",
        "хочу к вам",
        "хочу попасть",
        "записаться на прием",
        "попасть на прием"  
    ]

    known_specialists = [
        "стоматолог", "дантист", "ортодонт", "терапевт",
        "хирург", "имплантолог", "гигиенист"
    ]

    return any(p in text_low for p in vague_phrases) and not any(s in text_low for s in known_specialists)


def is_yes_message(text: str) -> bool:
    text_low = text.lower().replace("ё", "е").strip()
    return text_low in {
        "да", "ага", "подтверждаю", "да, подтверждаю", "подтвердить", "подтвердите",
        "подходит", "все верно", "все правильно", "ок", "ok", "хорошо", "конечно",
        "давай", "ладно", "согласен", "отменяй", "да, отменить"
    }


def is_no_message(text: str) -> bool:
    text_low = text.lower().replace("ё", "е").strip()
    return text_low in {"нет", "неа", "не подходит", "не хочу", "отмена", "нет, оставить", "оставить"}


def is_flexible_time_message(text: str) -> bool:
    text_low = text.lower().replace("ё", "е").strip()
    phrases = {
        "на любое время", "на любое", "мне все равно", "мне всё равно", "без разницы",
        "когда угодно", "как будет удобно", "как будет свободно", "любое окно", "первое свободное"
    }
    return any(phrase in text_low for phrase in phrases)


def get_best_available_slot(clinic_id: int, service_name: str = "", preferred_datetime: str = "", exclude_booking_id: int | None = None) -> str:
    duration = get_service_duration(clinic_id, service_name or "")
    base_slot = preferred_datetime or (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    slots = find_alternative_slots(
        base_slot,
        clinic_id,
        duration_minutes=duration,
        exclude_booking_id=exclude_booking_id,
        limit=3,
    )
    return slots[0] if slots else ""


def get_services_hint(clinic_id: int = 1) -> str:
    services = get_active_services(clinic_id)
    if not services:
        return ""
    names = services[:4]
    if len(services) > 4:
        return f"Например: {', '.join(names)} и другие."
    return f"Например: {', '.join(names)}."


def detect_service_from_text(text: str, clinic_id: int = 1) -> str:
    text_low = text.lower().strip()
    service_aliases = {
    "Удаление зуба": ["удалить зуб", "удаление зуба", "вырвать зуб", "выдернуть зуб"],
    "Чистка зубов": ["чистка", "почистить зубы", "гигиена", "проф чистка"],
    "Лечение зуба": ["лечить зуб", "лечение зуба", "болит зуб", "кариес"],
    "Консультация": ["консультация", "осмотр", "посмотреть зуб", "к врачу"],
}

    for service_name, aliases in service_aliases.items():
        if any(alias in text_low for alias in aliases):
            return service_name
    best_match = ""
    best_score = 0

    for service in get_all_services(clinic_id):
        if not service.get("is_active", 1):
            continue
        name = (service.get("name") or "").strip()
        name_low = name.lower()
        if not name_low:
            continue
        if name_low in text_low:
            return name

        tokens = [token for token in re.findall(r"[a-zа-яё0-9]+", name_low) if len(token) > 2]
        score = sum(1 for token in tokens if token in text_low)
        if score > best_score:
            best_score = score
            best_match = name

    return best_match if best_score > 0 else ""


def extract_phone_number(text: str) -> str:
    digits = re.sub(r"\D", "", text)
    if len(digits) < 10:
        return ""

    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) >= 11:
        if digits.startswith("8"):
            digits = "7" + digits[1:11]
        else:
            digits = digits[:11]

    if len(digits) != 11:
        return ""

    return f"+{digits[0]} {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"


def parse_human_datetime(text: str, existing_datetime: str = ""):
    text_low = text.lower().replace("ё", "е").strip()
    now = datetime.now()
    target_date = None
    target_time = None

    existing_dt = None
    if existing_datetime:
        try:
            existing_dt = datetime.fromisoformat(existing_datetime)
        except Exception:
            existing_dt = None

    if "послезавтра" in text_low:
        target_date = now.date() + timedelta(days=2)
    elif "завтра" in text_low:
        target_date = now.date() + timedelta(days=1)
    elif "сегодня" in text_low:
        target_date = now.date()

    date_match = re.search(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", text_low)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        year = int(date_match.group(3)) if date_match.group(3) else now.year
        if year < 100:
            year += 2000
        try:
            target_date = datetime(year, month, day).date()
        except ValueError:
            return None, "Похоже, дата получилась некорректной. Напишите, пожалуйста, дату в формате 00.00 или 00/00."

    month_name_match = re.search(
        r"\b(\d{1,2})\s+([а-я]+)(?:\s+(\d{2,4}))?\b",
        text_low,
    )
    if target_date is None and month_name_match:
        day = int(month_name_match.group(1))
        month = MONTH_MAP.get(month_name_match.group(2))
        year = int(month_name_match.group(3)) if month_name_match.group(3) else now.year
        if year < 100:
            year += 2000
        if month:
            try:
                target_date = datetime(year, month, day).date()
                if target_date < now.date() and not month_name_match.group(3):
                    target_date = datetime(year + 1, month, day).date()
            except ValueError:
                return None, "Похоже, дата получилась некорректной. Напишите, пожалуйста, дату в формате 14 мая или 14.05."

    if target_date is None and month_name_match:
        day = int(month_name_match.group(1))
        month = MONTH_MAP.get(month_name_match.group(2))
        year = int(month_name_match.group(3)) if month_name_match.group(3) else now.year
        if year < 100:
            year += 2000
        if month:
            try:
                target_date = datetime(year, month, day).date()
                if target_date < now.date() and not month_name_match.group(3):
                    target_date = datetime(year + 1, month, day).date()
            except ValueError:
                return None, "Похоже, дата получилась некорректной. Напишите, пожалуйста, дату в формате 14 мая или 14.05."

    if target_date is None:
        for weekday_name, weekday_number in WEEKDAY_MAP.items():
            if weekday_name in text_low:
                days_ahead = (weekday_number - now.weekday()) % 7
                target_date = (now + timedelta(days=days_ahead)).date()
                break

    time_match = re.search(r"(\d{1,2})[:.](\d{2})", text_low)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            target_time = (hour, minute)
    else:
        hour_only = re.search(r"\bв\s*(\d{1,2})\b", text_low)
        if hour_only:
            hour = int(hour_only.group(1))
            if 1 <= hour <= 7 and "утр" not in text_low:
                hour += 12
            if 0 <= hour <= 23:
                target_time = (hour, 0)

    if target_time is None:
        if "после обеда" in text_low:
            target_time = (15, 0)
        elif "утром" in text_low:
            target_time = (10, 0)
        elif "вечером" in text_low:
            target_time = (18, 0)
        elif "днем" in text_low or "днём" in text_low:
            target_time = (14, 0)

    if target_date is None and existing_dt is not None:
        target_date = existing_dt.date()

    if target_time is None and existing_dt is not None:
        target_time = (existing_dt.hour, existing_dt.minute)

    if target_date is None and target_time is not None:
        candidate = now.replace(hour=target_time[0], minute=target_time[1], second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        target_date = candidate.date()

    if target_date is None or target_time is None:
        return None, "Подскажите дату и время чуть точнее."

    candidate_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=target_time[0], minute=target_time[1])
    if candidate_dt <= now:
        return None, "Это время уже прошло. Давайте выберем другое окно."

    return candidate_dt.strftime("%Y-%m-%d %H:%M"), None


def extract_person_name(text: str, relaxed: bool = False) -> str:
    text_value = re.sub(r"[^a-zа-яё\s-]", " ", (text or "").lower(), flags=re.IGNORECASE)
    text_value = re.sub(r"\s+", " ", text_value).strip()
    if not text_value:
        return ""

    stopwords = {
        "да", "нет", "ок", "хорошо", "завтра", "сегодня", "послезавтра", "утром", "вечером",
        "отменить", "перенести", "записаться", "запись", "стоит", "цена", "администратор"
    }

    patterns = [
        r"(?:меня зовут|мое имя|моё имя|это)\s+([a-zа-яё-]+(?:\s+[a-zа-яё-]+){0,2})",
        r"^([a-zа-яё-]+(?:\s+[a-zа-яё-]+){0,2})$",
    ]

    for index, pattern in enumerate(patterns):
        if index == 1 and not relaxed:
            continue
        match = re.search(pattern, text_value, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = " ".join(part.capitalize() for part in match.group(1).split())
        tokens = [token.lower() for token in candidate.split() if token]
        if not tokens or any(token in stopwords for token in tokens):
            continue
        return candidate

    return ""


def pick_suggested_slot(text: str, suggested_slots: list[str]) -> str:
    if not suggested_slots:
        return ""

    text_low = (text or "").lower().strip()
    number_match = re.search(r"\b([1-9])\b", text_low)
    if number_match:
        index = int(number_match.group(1)) - 1
        if 0 <= index < len(suggested_slots):
            return suggested_slots[index]

    ordinal_map = {
        "перв": 0,
        "втор": 1,
        "трет": 2,
        "четвер": 3,
        "пят": 4,
    }
    for fragment, index in ordinal_map.items():
        if fragment in text_low and index < len(suggested_slots):
            return suggested_slots[index]

    return ""


def build_confirmation_text(session: dict, appointment_at: str, is_reschedule: bool = False) -> str:
    action_label = "Проверьте, пожалуйста, перенос:" if is_reschedule else "Проверьте, пожалуйста, запись:"
    service = session.get("service") or "—"
    full_name = session.get("full_name") or "Клиент"
    phone = format_phone_for_display(session.get("phone", ""))
    appointment_display = format_slot_for_display(appointment_at) if appointment_at else "—"
    ending = "Если всё верно — ответьте «да». Чтобы поправить время, имя, телефон или услугу — напишите что изменить."
    return (
        f"{action_label}\n\n"
        f"🏥 Услуга: {service}\n"
        f"👤 Имя: {full_name}\n"
        f"📞 Телефон: {phone}\n"
        f"📅 Время: {appointment_display}\n\n"
        f"{ending}"
    )


def get_repeat_guidance(flow_state: str, clinic_id: int = 1) -> str:
    services_hint = get_services_hint(clinic_id)
    prompts = {
        "choosing_service": f"Нужна именно услуга. {services_hint}".strip(),
        "waiting_name": "Напишите, пожалуйста, имя — например: Анна или Анна Иванова.",
        "waiting_phone": "Нужен именно номер телефона. Например: +7 777 123 45 67.",
        "waiting_datetime": "Напишите удобное время.",
        "reschedule_flow": "Для переноса нужно конкретное время. Например: послезавтра в 17:30.",
    }
    return prompts.get(flow_state, get_flow_prompt(flow_state, clinic_id))


def get_flow_prompt(flow_state: str, clinic_id: int = 1) -> str:
    services_hint = get_services_hint(clinic_id)
    prompts = {
        "choosing_doctor": "К какому специалисту вас записать?",
        "choosing_service": f"На какую услугу хотите записаться? {services_hint}".strip(),
        "waiting_name": "Как вас записать? Напишите имя, пожалуйста.",
        "waiting_phone": "Подскажите номер телефона для подтверждения.",
        "waiting_datetime": "Когда вам удобно прийти?",
        "booking_confirmation": "Если всё верно — ответьте «да». Напишите «изменить имя», «изменить телефон» или другое время — исправим.",
        "reschedule_flow": "На какое время перенести? Например: послезавтра в 17:30.",
        "reschedule_confirmation": "Если всё верно — «да». Хотите другое время — просто напишите его.",
        "cancel_flow": "Отменяем? Напишите «да» для отмены или «нет», если оставляем запись.",
    }
    return prompts.get(flow_state, "Чем помочь: запись, перенос или вопрос?")


def get_flow_followup_hint(flow_state: str, clinic_id: int = 1) -> str:
    hints = {
        "choosing_service": "Если захотите продолжить, просто напишите нужную услугу.",
        "waiting_phone": "Когда будете готовы, просто пришлите номер.",
        "waiting_datetime": "Когда решите, напишите удобное время.",
        "reschedule_flow": "Если хотите перенести запись, напишите новое время.",
    }
    return hints.get(flow_state, "")


@app.post("/webhook/telegram/{bot_key}")
async def telegram_webhook(bot_key: str, request: Request):
    data = await request.json()

    clinic_id = get_clinic_id_by_channel("telegram", bot_key)

    if not clinic_id:
        return {"ok": False, "error": "Telegram бот не привязан"}

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    # дальше твоя логика обработки
    print("TG MESSAGE:", chat_id, text, "clinic:", clinic_id)

    return {"ok": True}
@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    data = await request.json()

    print("GREEN API DATA:", data, flush=True)

    if data.get("typeWebhook") != "incomingMessageReceived":
        return {"ok": True}

    instance_id = str(data["instanceData"]["idInstance"])
    channel = get_channel_by_key("whatsapp", instance_id)

    if not channel:
        return {"ok": False, "error": "Канал не привязан к клинике"}

    message_data = data.get("messageData", {})
    message = (
        message_data.get("textMessageData", {}).get("textMessage")
        or message_data.get("extendedTextMessageData", {}).get("text")
        or ""
    )

    sender = data.get("senderData", {}).get("chatId", "")
    sender_name = data.get("senderData", {}).get("senderName", "Клиент")

    if not message or not sender:
        return {"ok": True}
    if not str(sender).endswith("@c.us"):
        logger.info("WhatsApp webhook skipped non-private chat_id=%s", sender)
        return {"ok": True}

    phone = sender.replace("@c.us", "")

    async def wa_send(text):
        print("WA SEND:", text, flush=True)
        return send_whatsapp_green(
            sender,
            text,
            channel["channel_key"],
            channel["channel_token"]
        )

    await process_client_message(phone, message, sender_name, wa_send, channel["clinic_id"])

    return {"ok": True}




def send_whatsapp_green(chat_id, text, id_instance, api_token_instance):
    if not id_instance or not api_token_instance:
        logger.warning("WhatsApp send skipped: missing idInstance or apiTokenInstance")
        return False

    url = f"https://api.green-api.com/waInstance{id_instance}/sendMessage/{api_token_instance}"

    payload = {
        "chatId": chat_id,
        "message": text
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code >= 400:
            logger.warning("WhatsApp send failed: %s %s", response.status_code, response.text)
            return False

        logger.info("WhatsApp message sent to %s", chat_id)
        return True

    except Exception as e:
        logger.exception("WhatsApp send error: %s", e)
        return False


def normalize_whatsapp_chat_id(value: str) -> str:
    raw_value = (value or "").strip()
    if not raw_value:
        return ""
    if raw_value.endswith("@c.us"):
        return raw_value

    digits = re.sub(r"\D", "", raw_value)
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) >= 11:
        if digits.startswith("8"):
            digits = "7" + digits[1:11]
        else:
            digits = digits[:11]

    if len(digits) < 10:
        return ""
    return f"{digits}@c.us"


def normalize_phone_digits(value: str) -> str:
    chat_id = normalize_whatsapp_chat_id(value)
    return chat_id.replace("@c.us", "") if chat_id else ""


def get_whatsapp_channel_for_clinic(clinic_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT channel_key, channel_token, channel_name
    FROM clinic_channels
    WHERE clinic_id = ? AND channel_type = 'whatsapp' AND is_active = 1
      AND COALESCE(channel_key, '') <> '' AND COALESCE(channel_token, '') <> ''
    ORDER BY id DESC
    LIMIT 1
    """, (clinic_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "channel_key": row[0],
        "channel_token": row[1],
        "channel_name": row[2] or "",
    }


def send_clinic_whatsapp_message(clinic_id: int, recipient: str, text: str) -> bool:
    chat_id = normalize_whatsapp_chat_id(recipient)
    if not chat_id:
        logger.warning("Clinic WhatsApp send skipped: invalid recipient=%r clinic_id=%s", recipient, clinic_id)
        return False

    channel = get_whatsapp_channel_for_clinic(clinic_id)
    if not channel:
        logger.warning("Clinic WhatsApp send skipped: no active Green API channel clinic_id=%s", clinic_id)
        return False

    return send_whatsapp_green(
        chat_id,
        text,
        channel["channel_key"],
        channel["channel_token"],
    )


async def notify_clinic_owner(clinic_id: int, event_key: str, text: str) -> bool:
    settings = get_clinic_settings(clinic_id)
    enabled_key = {
        "lead": "notify_new_leads",
        "booking": "notify_new_bookings",
        "operator": "notify_operator_requests",
    }.get(event_key)

    if enabled_key and not settings.get(enabled_key):
        return False

    admin_whatsapp = (settings.get("admin_notify_whatsapp") or "").strip()
    if not admin_whatsapp:
        logger.info("Clinic notification skipped: admin_notify_whatsapp is empty clinic_id=%s", clinic_id)
        return False

    return await asyncio.to_thread(send_clinic_whatsapp_message, clinic_id, admin_whatsapp, text)


async def send_booking_reminder_message(app, booking: dict, label: str) -> bool:
    clinic_id = int(booking.get("clinic_id") or 1)
    chat_id_raw = str(booking.get("chat_id") or "").strip()
    service_text = f" на услугу {booking.get('service')}" if booking.get("service") else ""
    message = (
        f"Напоминаем: у вас запись {label} на "
        f"{format_slot_for_display(booking.get('appointment_at', ''))}{service_text}. "
        "Если что-то изменится, напишите сюда."
    )

    source_channel = (booking.get("source_channel") or "").strip().lower()
    chat_digits = normalize_phone_digits(chat_id_raw)
    phone_digits = normalize_phone_digits(booking.get("phone") or "")
    should_use_whatsapp = source_channel == "whatsapp" or (
        not source_channel and chat_digits and phone_digits and chat_digits == phone_digits
    )

    if should_use_whatsapp:
        settings = get_clinic_settings(clinic_id)
        if not settings.get("whatsapp_reminders_enabled"):
            logger.info("AUTOMATION: WhatsApp reminders disabled clinic_id=%s booking=%s", clinic_id, booking.get("id"))
            return False
        return await asyncio.to_thread(send_clinic_whatsapp_message, clinic_id, chat_id_raw, message)

    if not app:
        logger.info("AUTOMATION: Skip Telegram reminder because Telegram app is not running")
        return False
    if not chat_id_raw or not chat_id_raw.lstrip("-").isdigit():
        logger.info("AUTOMATION: Skip Telegram reminder for non-Telegram chat_id=%s", chat_id_raw)
        return False

    await app.bot.send_message(chat_id=int(chat_id_raw), text=message)
    return True
    
# =========================
# Telegram Bot Commands & Handlers
# =========================


def get_first_missing_field(state: dict) -> str:
    """
    Determine which booking field is missing and needs to be asked.
    
    Checks fields in order: service → full_name → phone → preferred_datetime
    Returns the first field that is empty, or None if all are filled.
    
    Args:
        state: Current user state dictionary
        
    Returns:
        Field name ("service", "full_name", "phone", "preferred_datetime") or None if all filled
    """
    fields_to_check = ["service", "full_name", "phone", "preferred_datetime"]
    
    for field in fields_to_check:
        if not state.get(field, "").strip():
            return field
    
    return None


def get_current_clinic_id(request: Request) -> int:
    clinic_id = request.session.get("clinic_id")
    if not clinic_id:
        return 1
    return int(clinic_id)

@app.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_page(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, expires_at, used
        FROM password_resets
        WHERE token = ?
        """,
        (token,)
    )

    token_data = cursor.fetchone()
    conn.close()

    if not token_data:
        return HTMLResponse("""
        <html>
        <head>
            <meta charset='UTF-8'>
            <title>Ошибка</title>
        </head>
        <body>
            <h2>Ссылка недействительна</h2>
        </body>
        </html>
        """)

    user_id, expires_at, used = token_data

    if used:
        return HTMLResponse("""
        <html>
        <head>
            <meta charset='UTF-8'>
            <title>Ошибка</title>
        </head>
        <body>
            <h2>Ссылка уже использована</h2>
        </body>
        </html>
        """)

    if datetime.utcnow() > datetime.fromisoformat(expires_at):
        return HTMLResponse(f"""
        <html>
        <head>
            <meta charset='UTF-8'>
            <title>Ссылка устарела</title>
            {get_admin_css()}
        </head>
        <body>
            <div class='container auth-shell'>
                <div class='auth-card'>
                    <div class='page-title'>
                        <h2>⚠️ Ссылка устарела</h2>
                        <p>Запросите новое письмо для восстановления пароля.</p>
                    </div>
                    <a class='btn btn-primary' href='/forgot-password'>Запросить заново</a>
                </div>
            </div>
        </body>
        </html>
        """)

    # если всё ок — показываем форму смены пароля
    return HTMLResponse(f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <title>Смена пароля</title>
        {get_admin_css()}
    </head>
    <body>
        <div class='container auth-shell'>
            <div class='auth-card'>
                <div class='page-title'>
                    <h2>🔑 Новый пароль</h2>
                    <p>Введите новый пароль</p>
                </div>

                <div class='form-group'>
                    <input id="password" type="password" placeholder="Новый пароль">
                </div>

                <button class='btn btn-primary' onclick="resetPassword()">Сменить пароль</button>

                <p id="result" style="margin-top:10px;"></p>
            </div>
        </div>

        <script>
        async function resetPassword() {{
            const password = document.getElementById("password").value;
            const result = document.getElementById("result");

            const res = await fetch("/reset-password/{token}", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ password }})
            }});

            const data = await res.json();
            result.innerText = data.message || data.error;
        }}
        </script>
    </body>
    </html>
    """)
 
@app.post("/forgot-password")
async def forgot_password(request: Request):
    conn = None

    try:
        data = await request.json()
        email = (data.get("email") or "").strip().lower()

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user:
            user_id = user[0]

            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(minutes=15)

            cursor.execute(
                """
                INSERT INTO password_resets (user_id, token, expires_at, used)
                VALUES (?, ?, ?, 0)
                """,
                (user_id, token, expires_at.isoformat())
            )

            conn.commit()

            base_url = str(request.base_url).rstrip("/")
            link = f"{base_url}/reset-password/{token}"

            send_email(email, f"Перейдите по ссылке для сброса пароля:\n{link}")

            logger.info("RESET LINK: %s", link)

        return {"message": "Если email существует — письмо отправлено"}

    except RuntimeError as e:
        logger.exception("FORGOT PASSWORD EMAIL CONFIG ERROR")
        return {"error": str(e)}
    except smtplib.SMTPAuthenticationError:
        logger.exception("FORGOT PASSWORD SMTP AUTH ERROR")
        return {"error": "SMTP не авторизовался. Для Gmail нужен пароль приложения, не обычный пароль."}
    except smtplib.SMTPException as e:
        logger.exception("FORGOT PASSWORD SMTP ERROR")
        return {"error": f"Ошибка SMTP при отправке письма: {str(e)}"}
    except Exception as e:
        logger.exception("FORGOT PASSWORD ERROR")
        return {"error": f"Ошибка сервера: {str(e)}"}

    finally:
        if conn:
            conn.close()

def send_email(to_email, text, subject: str = "Сброс пароля"):
    sender = (os.getenv("SMTP_EMAIL") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()

    if not sender or not password:
        raise RuntimeError("SMTP_EMAIL и SMTP_PASSWORD не заполнены в .env")

    smtp_host = (os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()
    smtp_port = int((os.getenv("SMTP_PORT") or "587").strip())

    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = sender
    msg["To"] = to_email

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(sender, password)
        server.send_message(msg)

    logger.info("EMAIL sent to %s via %s", to_email, smtp_host)


def get_reply_for_missing_field(field: str) -> str:
    """
    Get the Russian reply text for a missing field.
    
    Args:
        field: Field name ("service", "full_name", "phone", "preferred_datetime")
        
    Returns:
        Human-friendly Russian question text
    """
    replies = {
        "service": get_service_question(),
        "full_name": get_name_question(),
        "phone": get_phone_question(),
        "preferred_datetime": get_datetime_question(),
    }
    return replies.get(field, "Спасибо за информацию. Продолжайте, пожалуйста.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat.id)
    current_state = get_user_state(chat_id)
    save_user_state(chat_id, current_state)
    reset_runtime_session(chat_id)

    await update.message.reply_text(
        "Здравствуйте! Помогу записаться, перенести визит, отменить запись или посмотреть услуги.\n\n"
        "Можно выбрать действие кнопкой или написать обычным текстом.",
        reply_markup=get_main_menu_markup("idle"),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_public_help_text(), reply_markup=get_main_menu_markup("idle"))


async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    await update.message.reply_text(get_admin_help_text(), reply_markup=get_main_menu_markup("idle"))


def send_register_code_email(to_email, code):
    body = f"Ваш код подтверждения регистрации: {code}\n\nКод действует 5 минут."
    send_email(to_email, body, subject="Код подтверждения регистрации")
    

   
 
@app.post("/reset-password/{token}")
async def reset_password(token: str, request: Request):
    data = await request.json()
    new_password = (data.get("password") or "").strip()

    if len(new_password) < 6:
        return {"error": "Пароль должен быть минимум 6 символов"}

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, expires_at, used
        FROM password_resets
        WHERE token = ?
        """,
        (token,)
    )

    token_data = cursor.fetchone()

    if not token_data:
        conn.close()
        return {"error": "Неверная ссылка"}

    user_id, expires_at, used = token_data

    if used:
        conn.close()
        return {"error": "Ссылка уже использована"}

    if datetime.utcnow() > datetime.fromisoformat(expires_at):
        conn.close()
        return {"error": "Ссылка устарела"}

    password_hash = hash_admin_password(new_password)

    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id)
    )

    cursor.execute(
        "UPDATE password_resets SET used = 1 WHERE token = ?",
        (token,)
    )

    conn.commit()
    conn.close()

    return {"message": "Пароль успешно изменён. Теперь войдите заново."}
    
async def reset_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat.id)

    # Check if user has an active booking
    existing_booking = get_active_booking_by_chat_id(chat_id)

    if existing_booking:
        cancel_result = cancel_active_booking_by_chat_id(chat_id)
        if cancel_result.get("success"):
            print(f"DEBUG: Cancelled active booking for chat_id {chat_id} during reset")
            await notify_admins(build_admin_booking_notification("Клиент сбросил сценарий и отменил запись", cancel_result.get("booking")))
            await update.message.reply_text(cancel_result.get("message", get_error_response()), reply_markup=get_main_menu_markup("idle"))
        else:
            print(f"ERROR: Failed to cancel active booking for chat_id {chat_id} during reset: {cancel_result.get('error')}")

    # Reset user state
    reset_runtime_session(chat_id)
    reset_result = reset_user_state(chat_id)
    if reset_result:
        print(f"DEBUG: Successfully reset state for chat_id {chat_id}")
        await update.message.reply_text(get_reset_success_response(), reply_markup=get_main_menu_markup("idle"))
    else:
        print(f"ERROR: Failed to reset state for chat_id {chat_id}")
        await update.message.reply_text(get_reset_error_response(), reply_markup=get_main_menu_markup("idle"))


async def state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat.id)
    current_data = get_user_state(chat_id)
    await update.message.reply_text(
        "Текущее состояние:\n" + json.dumps(current_data, ensure_ascii=False, indent=2)
    )


async def my_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /mybooking called")
    try:
        chat_id = str(update.message.chat.id)
        booking = get_active_booking_by_chat_id(chat_id)
        await update.message.reply_text(
            build_user_booking_text(booking),
            reply_markup=get_main_menu_markup("confirmation" if booking else "idle"),
        )
    except Exception as e:
        print(f"ERROR in my_booking: {e}")
        await update.message.reply_text(get_error_response(), reply_markup=get_main_menu_markup("idle"))


async def all_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /bookings called")
    try:
        if not await require_admin_chat(update):
            return
        # Get clinic for current user
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        
        bookings = get_clinic_active_bookings(clinic_id)
        
        if not bookings:
            await update.message.reply_text(get_no_bookings_response(), reply_markup=get_main_menu_markup("idle"))
            return
        
        booking_lines = [format_booking_for_display(booking) for booking in bookings]
        message = "Все активные записи:\n\n" + "\n".join(booking_lines)
        await update.message.reply_text(message, reply_markup=get_main_menu_markup("idle"))
    except Exception as e:
        print(f"ERROR in all_bookings: {e}")
        await update.message.reply_text(get_error_response(), reply_markup=get_main_menu_markup("idle"))


async def cancel_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /cancelbooking called")
    try:
        chat_id = str(update.message.chat.id)
        cancel_result = cancel_active_booking_by_chat_id(chat_id)
        reset_runtime_session(chat_id)
        if cancel_result.get("success"):
            await notify_admins(build_admin_booking_notification("Клиент отменил запись", cancel_result.get("booking")))
        await update.message.reply_text(cancel_result.get("message", get_error_response()), reply_markup=get_main_menu_markup("idle"))
    except Exception as e:
        print(f"ERROR in cancel_booking: {e}")
        await update.message.reply_text(get_error_response(), reply_markup=get_main_menu_markup("idle"))


async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /services called")
    try:
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        await update.message.reply_text(get_services_reply(clinic_id), reply_markup=get_main_menu_markup("idle"))
    except Exception as e:
        print(f"ERROR in show_services: {e}")
        await update.message.reply_text(get_error_response(), reply_markup=get_main_menu_markup("idle"))


async def add_new_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /addservice called")
    try:
        if not await require_admin_chat(update):
            return
        # Get service name from command arguments
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Использование: /addservice <название услуги>")
            return
        
        service_name = " ".join(context.args)
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        success = add_service(service_name, clinic_id=clinic_id)
        
        if success:
            await update.message.reply_text("Услуга добавлена ✅")
        else:
            await update.message.reply_text("Похоже, такая услуга уже есть в списке или данные нужно уточнить. Попробуйте ещё раз, пожалуйста.")
    except Exception as e:
        print(f"ERROR in add_new_service: {e}")
        await update.message.reply_text(get_error_response())


async def remove_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /removeservice called")
    try:
        if not await require_admin_chat(update):
            return
        # Get service name from command arguments
        if not context.args or len(context.args) == 0:
            await update.message.reply_text("Использование: /removeservice <название услуги>")
            return
        
        service_name = " ".join(context.args)
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        success = deactivate_service(service_name, clinic_id)
        
        if success:
            await update.message.reply_text("Услуга отключена ✅")
        else:
            await update.message.reply_text("Услуга не найдена.")
    except Exception as e:
        print(f"ERROR in remove_service: {e}")
        await update.message.reply_text(get_error_response())


async def set_work_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /sethours called")
    try:
        if not await require_admin_chat(update):
            return
        # Expect: /sethours HH:MM HH:MM
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Использование: /sethours <начало> <конец>\\nПример: /sethours 10:00 19:00")
            return
        
        work_start = context.args[0]
        work_end = context.args[1]
        
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        success = update_work_hours(work_start, work_end, clinic_id)

        
        if success:
            await update.message.reply_text("Часы работы обновлены ✅")
        else:
            await update.message.reply_text("Не получилось обновить часы работы с первого раза. Попробуйте ещё раз, пожалуйста.")
    except Exception as e:
        print(f"ERROR in set_work_hours: {e}")
        await update.message.reply_text("Сейчас не получилось обновить часы работы. Попробуйте ещё раз чуть позже, пожалуйста.")


async def set_slot_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /setslotstep called")
    try:
        if not await require_admin_chat(update):
            return
        # Expect: /setslotstep <minutes>
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("Использование: /setslotstep <минуты>\\nПример: /setslotstep 30")
            return
        
        try:
            minutes = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Укажите число минут (например, 30 или 60).")
            return
        
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        success = update_slot_step(minutes, clinic_id)

        
        if success:
            await update.message.reply_text("Длительность слота обновлена ✅")
        else:
            await update.message.reply_text("Не получилось обновить длительность слота с первого раза. Попробуйте ещё раз, пожалуйста.")
    except Exception as e:
        print(f"ERROR in set_slot_step: {e}")
        await update.message.reply_text("Сейчас не получилось обновить длительность слота. Попробуйте ещё раз чуть позже, пожалуйста.")


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /faq called")
    try:
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        faq_items = get_all_active_faq_items(clinic_id)
        
        if not faq_items:
            await update.message.reply_text("FAQ пока пуст.")
            return
        
        faq_lines = []
        for item in faq_items:
            faq_lines.append(f"❓ {item['question']}\n✅ {item['answer']}")
        
        message = "\n\n".join(faq_lines)
        await update.message.reply_text(message)
    except Exception as e:
        print(f"ERROR in show_faq: {e}")
        await update.message.reply_text("Сейчас не получилось показать ответы на вопросы. Попробуйте ещё раз чуть позже, пожалуйста.")


async def add_new_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /addfaq called")
    try:
        if not await require_admin_chat(update):
            return
        # Expect: /addfaq <question> | <answer>
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("Использование: /addfaq <вопрос> | <ответ>\nПример: /addfaq сколько стоит чистка | Чистка стоит 15000 тг.")
            return
        
        full_text = " ".join(context.args)
        
        if "|" not in full_text:
            await update.message.reply_text("Используйте разделитель | между вопросом и ответом.\nПример: /addfaq сколько стоит | 15000 тг.")
            return
        
        parts = full_text.split("|", 1)
        question = parts[0].strip()
        answer = parts[1].strip()
        
        if not question or not answer:
            await update.message.reply_text("Вопрос и ответ не могут быть пусты.")
            return
        
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        success = add_faq_item(question, answer, clinic_id)
        
        if success:
            await update.message.reply_text("FAQ добавлен ✅")
        else:
            await update.message.reply_text("Этот вопрос уже существует в FAQ.")
    except Exception as e:
        print(f"ERROR in add_new_faq: {e}")
        await update.message.reply_text("Сейчас не получилось добавить вопрос. Попробуйте ещё раз чуть позже, пожалуйста.")


async def remove_faq_item_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /removefaq called")
    try:
        if not await require_admin_chat(update):
            return
        # Expect: /removefaq <question>
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("Использование: /removefaq <вопрос>")
            return
        
        question = " ".join(context.args)
        chat_id = str(update.message.chat.id)
        clinic_id = get_clinic_by_chat_id(chat_id)
        success = remove_faq_item(question, clinic_id)
        
        if success:
            await update.message.reply_text("FAQ удалён ✅")
        else:
            await update.message.reply_text("Вопрос не найден в FAQ.")
    except Exception as e:
        print(f"ERROR in remove_faq_item_cmd: {e}")
        await update.message.reply_text("Сейчас не получилось удалить вопрос. Попробуйте ещё раз чуть позже, пожалуйста.")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: /history called")
    try:
        chat_id = str(update.message.chat.id)
        await update.message.reply_text(build_booking_history_text(chat_id), reply_markup=get_main_menu_markup("idle"))
    except Exception as e:
        print("ERROR in show_booking_history:", repr(e))
        import traceback
        traceback.print_exc()
        await update.message.reply_text("Сейчас не удалось показать историю записей. Попробуйте чуть позже, пожалуйста.", reply_markup=get_main_menu_markup("idle"))


async def today_bookings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    chat_id = str(update.message.chat.id)
    clinic_id = get_clinic_by_chat_id(chat_id)
    bookings = get_today_bookings(clinic_id)
    if not bookings:
        await update.message.reply_text("На сегодня активных записей нет.", reply_markup=get_main_menu_markup("idle"))
        return
    await update.message.reply_text(
        "Записи на сегодня:\n\n" + "\n".join(format_booking_for_display(item) for item in bookings),
        reply_markup=get_main_menu_markup("idle"),
    )


async def upcoming_bookings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    chat_id = str(update.message.chat.id)
    clinic_id = get_clinic_by_chat_id(chat_id)
    bookings = get_upcoming_bookings(clinic_id)
    if not bookings:
        await update.message.reply_text("Ближайших активных записей нет.", reply_markup=get_main_menu_markup("idle"))
        return
    await update.message.reply_text(
        "Ближайшие записи:\n\n" + "\n".join(format_booking_for_display(item) for item in bookings[:20]),
        reply_markup=get_main_menu_markup("idle"),
    )


async def confirm_booking_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /confirmbooking <id>", reply_markup=get_main_menu_markup("idle"))
        return

    try:
        booking_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID записи должен быть числом.", reply_markup=get_main_menu_markup("idle"))
        return

    result = confirm_booking_by_id(booking_id)
    booking = result.get("booking")
    await update.message.reply_text(result.get("message", "Готово."), reply_markup=get_main_menu_markup("idle"))
    if result.get("success") and booking and str(booking.get("chat_id", "")).lstrip("-").isdigit():
        await send_telegram_text(
            booking["chat_id"],
            f"Администратор подтвердил вашу запись на {format_slot_for_display(booking.get('appointment_at', ''))}.",
        )
    logger.info("ADMIN_CONFIRM_BOOKING booking_id=%s success=%s", booking_id, result.get("success"))


async def reject_booking_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /rejectbooking <id> [причина]", reply_markup=get_main_menu_markup("idle"))
        return

    try:
        booking_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID записи должен быть числом.", reply_markup=get_main_menu_markup("idle"))
        return

    reason = " ".join(context.args[1:]).strip()
    booking = get_booking_by_id(booking_id)
    success = cancel_booking_by_id(booking_id)
    if not success:
        await update.message.reply_text("Запись не найдена или уже не активна.", reply_markup=get_main_menu_markup("idle"))
        return

    if booking and str(booking.get("chat_id", "")).lstrip("-").isdigit():
        reason_text = f"\nПричина: {reason}" if reason else ""
        await send_telegram_text(
            booking["chat_id"],
            f"Администратор отклонил запись на {format_slot_for_display(booking.get('appointment_at', ''))}.{reason_text}",
        )

    await update.message.reply_text("Запись отклонена и отменена.", reply_markup=get_main_menu_markup("idle"))
    await notify_admins(build_admin_booking_notification("Администратор отклонил запись", booking))
    logger.info("ADMIN_REJECT_BOOKING booking_id=%s reason=%r", booking_id, reason)


async def delete_booking_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /deletebooking <id>", reply_markup=get_main_menu_markup("idle"))
        return

    try:
        booking_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID записи должен быть числом.", reply_markup=get_main_menu_markup("idle"))
        return

    booking = get_booking_by_id(booking_id)
    success = cancel_booking_by_id(booking_id)
    await update.message.reply_text(
        "Запись удалена через отмену." if success else "Запись не найдена или уже не активна.",
        reply_markup=get_main_menu_markup("idle"),
    )
    if success:
        await notify_admins(build_admin_booking_notification("Администратор удалил запись", booking))
    logger.info("ADMIN_DELETE_BOOKING booking_id=%s success=%s", booking_id, success)


async def edit_booking_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "Использование: /editbooking <id> <YYYY-MM-DD HH:MM> [услуга]",
            reply_markup=get_main_menu_markup("idle"),
        )
        return

    try:
        booking_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID записи должен быть числом.", reply_markup=get_main_menu_markup("idle"))
        return

    new_datetime = f"{context.args[1]} {context.args[2]}"
    try:
        datetime.strptime(new_datetime, "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("Дата должна быть в формате YYYY-MM-DD HH:MM.", reply_markup=get_main_menu_markup("idle"))
        return

    booking = get_booking_by_id(booking_id)
    if not booking:
        await update.message.reply_text("Запись не найдена.", reply_markup=get_main_menu_markup("idle"))
        return

    new_service = " ".join(context.args[3:]).strip() or booking.get("service", "")
    payload = {
        "chat_id": booking.get("chat_id", ""),
        "service": new_service,
        "full_name": booking.get("full_name", ""),
        "phone": booking.get("phone", ""),
        "preferred_datetime": new_datetime,
    }

    result = update_booking(booking_id, payload)
    await update.message.reply_text(result.get("message", "Готово."), reply_markup=get_main_menu_markup("idle"))
    updated_booking = get_booking_by_id(booking_id)
    if result.get("success") and updated_booking:
        await notify_admins(build_admin_booking_notification("Администратор изменил запись", updated_booking))
        if str(updated_booking.get("chat_id", "")).lstrip("-").isdigit():
            await send_telegram_text(
                updated_booking["chat_id"],
                f"Администратор изменил вашу запись. Новое время: {format_slot_for_display(updated_booking.get('appointment_at', ''))}.",
            )
    logger.info("ADMIN_EDIT_BOOKING booking_id=%s success=%s", booking_id, result.get("success"))
   
async def process_client_message(chat_id, user_text, user_name, send_func, source_clinic_id=None):
    try:
        chat_id = str(chat_id)
        clinic_id = assign_user_to_clinic(chat_id, source_clinic_id) if source_clinic_id else assign_user_to_clinic(chat_id)
        user_text = (user_text or "").strip()
        text_low = user_text.lower().replace("ё", "е")
        telegram_name = (user_name or "").strip()

        async def send_text(text):
            result = send_func(text)
            if asyncio.iscoroutine(result):
                await result

        logger.info(f"MSG chat_id={chat_id} text={user_text[:80]!r}")
        print(f"PROCESS MESSAGE: chat_id={chat_id}, text={user_text}", flush=True)

        current_data = get_user_state(chat_id)
        session = get_runtime_session(chat_id, current_data, telegram_name)
        existing_booking = get_active_booking_by_chat_id(chat_id)

        if existing_booking:
            for field, booking_key in {
                "service": "service",
                "phone": "phone",
                "preferred_datetime": "appointment_at",
                "full_name": "full_name",
            }.items():
                if not session.get(field):
                    session[field] = existing_booking.get(booking_key, "") or session.get(field, "")

        if session.get("full_name") in [None, ""]:
            session["full_name"] = telegram_name or current_data.get("full_name") or ""

        normalized_user_text = re.sub(r"\s+", " ", text_low).strip()
        previous_text = (session.get("last_user_message") or "").strip()
        repeat_count = session.get("repeat_count", 0) + 1 if normalized_user_text and normalized_user_text == previous_text else 0
        save_runtime_session(chat_id, last_user_message=normalized_user_text, repeat_count=repeat_count)

        flow_state = session.get("flow_state", "idle")
        intent = detect_intent(user_text)
        service_candidate = detect_service_from_text(user_text, clinic_id)
        phone_candidate = extract_phone_number(user_text)
        name_candidate = extract_person_name(
            user_text,
            relaxed=flow_state == "waiting_name" or not session.get("full_name")
        )

        edit_phrases = [
            "изменить имя",
            "изменить услугу",
            "изменить номер",
            "изменить телефон",
            "изменить время",
            "поменять имя",
            "поменять услугу",
            "поменять номер",
            "поменять телефон",
            "поменять время",
            "редактировать имя",
            "редактировать услугу",
            "редактировать номер",
            "редактировать телефон",
            "редактировать время",
        ]

        if any(phrase in user_text.lower() for phrase in edit_phrases):
            name_candidate = ""

        # ❌ не даём брать имя из услуги
        if service_candidate and name_candidate:
            name_candidate = ""

        looks_like_datetime = bool(
            re.search(r"\d{1,2}[:.]\d{2}", text_low)
            or re.search(r"\bв\s*\d{1,2}\b", text_low)
            or any(word in text_low for word in [
                "сегодня", "завтра", "послезавтра", "утром", "вечером",
                "после обеда", "днем", "днём", "понедельник", "вторник",
                "среда", "среду", "четверг", "пятница", "пятницу",
                "суббота", "субботу", "воскресенье"
            ])
        )
        
        asks_slot_availability = looks_like_datetime and any(phrase in text_low for phrase in [
            "можно", "свободно", "свободен", "свободна", "свободны",
            "есть место", "есть окно", "есть запись", "доступно",
            "получится", "можете", "принимаете", "примете",
        ])

        if service_candidate and not session.get("service"):
            save_runtime_session(chat_id, service=service_candidate)

        if phone_candidate:
            save_runtime_session(chat_id, phone=phone_candidate)

        explicit_name_markers = ["меня зовут", "мое имя", "моё имя", "это "]
        if (service_candidate or phone_candidate or looks_like_datetime) and not any(marker in text_low for marker in explicit_name_markers):
            name_candidate = ""
            
        if name_candidate \
            and not service_candidate \
            and (not session.get("full_name") or flow_state == "waiting_name" or session.get("full_name") in {telegram_name, "Клиент"}):
            save_runtime_session(chat_id, full_name=name_candidate)

        session = RUNTIME_SESSIONS.get(chat_id, session)
        selected_suggested_slot = pick_suggested_slot(user_text, session.get("suggested_slots", []))

        conversation_before_message = get_conversation_by_chat_id(clinic_id, chat_id)
        conversation = update_conversation_from_user_message(
            clinic_id,
            chat_id,
            full_name=session.get("full_name", telegram_name or ""),
            phone=session.get("phone", ""),
            user_message=user_text,
        )

        if not conversation_before_message:
            await notify_clinic_owner(
                clinic_id,
                "lead",
                (
                    "Новый лид в CRM\n"
                    f"Клиент: {session.get('full_name') or telegram_name or 'Клиент'}\n"
                    f"Телефон/chat: {session.get('phone') or chat_id}\n"
                    f"Сообщение: {user_text[:400]}"
                ),
            )

        if conversation and conversation.get("needs_operator"):
            if is_bot_pause_expired(conversation):
                clear_conversation_operator_flag(conversation["id"])
                conversation = get_conversation_by_chat_id(clinic_id, chat_id)
                logger.info("BOT_RESUMED_AUTO chat_id=%s clinic_id=%s", chat_id, clinic_id)
            else:
                logger.info("BOT_PAUSED chat_id=%s clinic_id=%s; message stored for operator", chat_id, clinic_id)
                return

        field_flow_map = {
            "doctor_profession": "choosing_doctor",
            "service": "choosing_service",
            "full_name": "waiting_name",
            "phone": "waiting_phone",
            "preferred_datetime": "waiting_datetime",
        }
        def normalize_word_token(word: str) -> str:
            word = (word or "").lower().replace("ё", "е").strip()
            word = re.sub(r"[^а-яa-z0-9-]", "", word)
            if not word:
                return ""

            endings = (
                "ами", "ями", "ого", "его", "ому", "ему", "ыми", "ими",
                "ая", "яя", "ое", "ее", "ые", "ие", "ой", "ей", "ою", "ею",
                "ам", "ям", "ах", "ях", "ом", "ем", "ым", "им", "ую", "юю",
                "а", "я", "у", "ю", "ы", "и", "е", "о",
            )

            for ending in endings:
                if len(word) > len(ending) + 3 and word.endswith(ending):
                    return word[:-len(ending)]

            return word

        def normalize_words(text: str) -> set:
            cleaned = re.sub(r"[^а-яa-z0-9\s-]", " ", (text or "").lower().replace("ё", "е"))
            words = cleaned.split()

            bad = {
                "к", "ко", "у", "на", "в", "во", "за", "по",
                "доктору", "врачу", "врач", "доктор", "специалисту",
            }

            result = set()
            for word in words:
                if word in bad or len(word) <= 1:
                    continue
                result.add(word)
                stem = normalize_word_token(word)
                if stem and len(stem) > 1:
                    result.add(stem)
            return result
        
        def words_overlap(user_words: set, target_words: set) -> bool:
            for user_word in user_words:
                for target_word in target_words:
                    if user_word == target_word:
                        return True
                    shorter, longer = sorted([user_word, target_word], key=len)
                    if len(shorter) >= 4 and longer.startswith(shorter):
                        return True
            return False

        
        async def reply_and_track(text: str, flow_state: str = None, intent: str = "booking", booking_status: str = "in_progress"):
            safe_text = (text or "").strip() or get_clarifying_question()
            current_runtime = RUNTIME_SESSIONS.get(chat_id, session)
            previous_bot_message = (current_runtime.get("last_bot_message") or "").strip()
            effective_flow = flow_state or current_runtime.get("flow_state") or "idle"

            if previous_bot_message and safe_text == previous_bot_message:
                alternate_text = get_repeat_guidance(effective_flow, clinic_id)
                if alternate_text and alternate_text != safe_text:
                    safe_text = alternate_text

            if flow_state is not None:
                save_runtime_session(chat_id, flow_state=flow_state, last_intent=intent, last_requested_action=intent, last_bot_message=safe_text)
            else:
                save_runtime_session(chat_id, last_intent=intent, last_requested_action=intent, last_bot_message=safe_text)

            sync_user_state(chat_id, RUNTIME_SESSIONS.get(chat_id, session), intent=intent, booking_status=booking_status)
            await send_text(safe_text)
            update_conversation_bot_reply(clinic_id, chat_id, safe_text)

        async def prompt_for_missing_data(repeated: bool = False):
            current_session = RUNTIME_SESSIONS.get(chat_id, session)
            missing_field = get_first_missing_field(current_session)

            if not missing_field:
                await reply_and_track(get_flow_prompt("waiting_datetime", clinic_id), flow_state="waiting_datetime")
                return

            next_flow = field_flow_map.get(missing_field, "idle")
            save_runtime_session(chat_id, flow_state=next_flow)

            if repeated:
                prompt = get_repeat_guidance(next_flow, clinic_id)
            elif missing_field == "phone" and current_session.get("service"):
                prompt = f"Хорошо, по услуге {current_session.get('service')}. Теперь нужен номер телефона для подтверждения."
            elif missing_field == "preferred_datetime" and current_session.get("service"):
                prompt = f"По услуге {current_session.get('service')} всё отмечено. Теперь подскажите удобную дату и время."
            else:
                prompt = get_flow_prompt(next_flow, clinic_id)

            await reply_and_track(prompt, flow_state=next_flow)

        async def prepare_confirmation(target_datetime: str, is_reschedule: bool = False):
            current_session = RUNTIME_SESSIONS.get(chat_id, session)
            flow = "reschedule_confirmation" if is_reschedule else "booking_confirmation"
            action = "reschedule" if is_reschedule else "booking"
            service_name = current_session.get("service") or (existing_booking.get("service") if existing_booking else "")
            duration = get_service_duration(clinic_id, service_name or "")
            exclude_booking_id = existing_booking.get("id") if is_reschedule and existing_booking else None

            if not check_slot_available(
                target_datetime,
                clinic_id,
                duration_minutes=duration,
                exclude_booking_id=exclude_booking_id,
            ):
                message, error_code, alternatives = get_slot_issue_message(
                    target_datetime,
                    clinic_id,
                    duration,
                    exclude_booking_id=exclude_booking_id,
                )
                fallback_flow = "reschedule_flow" if is_reschedule else "waiting_datetime"
                save_runtime_session(
                    chat_id,
                    flow_state=fallback_flow,
                    pending_datetime="",
                    pending_action=action,
                    suggested_slots=alternatives,
                )
                await reply_and_track(
                    message,
                    flow_state=fallback_flow,
                    intent=action,
                    booking_status=error_code,
                )
                return

            save_runtime_session(
                chat_id,
                preferred_datetime=target_datetime,
                pending_datetime=target_datetime,
                pending_action=action,
                suggested_slots=[],
            )

            current_session = RUNTIME_SESSIONS.get(chat_id, current_session)

            await reply_and_track(
                build_confirmation_text(current_session, target_datetime, is_reschedule=is_reschedule),
                flow_state=flow,
                intent=action,
            )

        async def attempt_booking(target_datetime: str, is_reschedule: bool = False):
            current_session = RUNTIME_SESSIONS.get(chat_id, session)

            payload = {
                "service": current_session.get("service") or (existing_booking.get("service") if existing_booking else ""),
                "full_name": current_session.get("full_name") or telegram_name or (existing_booking.get("full_name") if existing_booking else "") or "Клиент",
                "phone": current_session.get("phone") or (existing_booking.get("phone") if existing_booking else ""),
                "preferred_datetime": target_datetime,
                "status": "ready_to_book",
                "next_field": "completed",
                "booking_status": "in_progress",
                "intent": "booking",
                "chat_id": chat_id,
                "source_channel": "whatsapp" if source_clinic_id else "telegram",
            }

            missing_field = get_first_missing_field(payload)

            if missing_field:
                save_runtime_session(chat_id, pending_datetime=target_datetime)
                await prompt_for_missing_data(repeated=current_session.get("repeat_count", 0) > 0)
                return

            save_runtime_session(
                chat_id,
                service=payload["service"],
                full_name=payload["full_name"],
                phone=payload["phone"],
                preferred_datetime=target_datetime,
                pending_datetime="",
                pending_action="",
                suggested_slots=[],
            )

            sync_user_state(chat_id, RUNTIME_SESSIONS[chat_id], intent="booking")

            if is_reschedule:
                result = reschedule_booking_by_chat_id(chat_id, target_datetime, payload)
            else:
                result = create_or_update_booking(chat_id, payload)

            if result.get("success"):
                save_runtime_session(
                    chat_id,
                    flow_state="confirmation",
                    preferred_datetime=target_datetime,
                    pending_datetime="",
                    pending_action="",
                    suggested_slots=[],
                    repeat_count=0,
                )

                sync_user_state(chat_id, RUNTIME_SESSIONS[chat_id], intent="booking", booking_status="confirmed")

                await reply_and_track(
                    result.get("message", "Готово, запись подтверждена."),
                    flow_state="confirmation",
                    booking_status="confirmed",
                )
                created_booking = get_booking_by_id(result.get("booking_id")) if result.get("booking_id") else None
                await notify_admins(
                    build_admin_booking_notification(
                        "Запись перенесена" if is_reschedule else "Новая запись",
                        created_booking,
                        payload,
                    )
                )
                await notify_clinic_owner(
                    clinic_id,
                    "booking",
                    build_admin_booking_notification(
                        "Запись перенесена" if is_reschedule else "Новая запись",
                        created_booking,
                        payload,
                    ),
                )
                return

            next_flow = "reschedule_flow" if is_reschedule else "waiting_datetime"

            if result.get("error") == "active_booking_exists":
                next_flow = "confirmation"

            save_runtime_session(
                chat_id,
                flow_state=next_flow,
                preferred_datetime=target_datetime if next_flow != "confirmation" else current_session.get("preferred_datetime", ""),
                pending_datetime="",
                pending_action="",
                suggested_slots=result.get("alternative_slots", []),
            )

            sync_user_state(chat_id, RUNTIME_SESSIONS[chat_id], intent="booking")

            await reply_and_track(
                result.get("message", "Не удалось завершить запись. Давайте подберём другое время."),
                flow_state=next_flow,
            )

        flow_state = session.get("flow_state", "idle")

        if not user_text or not re.search(r"[0-9a-zA-Zа-яА-ЯёЁ]", user_text):
            await reply_and_track(
                "Не совсем понял сообщение. Выберите действие кнопкой или напишите, что нужно: запись, перенос, отмена, услуги или вопрос.",
                flow_state=flow_state or "idle",
                intent="unknown",
            )
            return

        if is_menu_request(user_text, {"помощь", "help", "что умеешь", "команды"}):
            await reply_and_track(get_public_help_text(), flow_state=flow_state or "idle", intent="question")
            return

        if is_menu_request(user_text, {"моя запись", "мои записи", "посмотреть запись", "текущая запись"}):
            await reply_and_track(
                build_user_booking_text(existing_booking),
                flow_state="confirmation" if existing_booking else "idle",
                intent="question",
                booking_status="confirmed" if existing_booking else "in_progress",
            )
            return

        if is_menu_request(user_text, {"история", "история записей"}):
            await reply_and_track(build_booking_history_text(chat_id), flow_state=flow_state or "idle", intent="question")
            return

        if is_menu_request(user_text, {"услуги", "список услуг", "цены", "стоимость"}):
            await reply_and_track(get_services_reply(clinic_id), flow_state=flow_state or "idle", intent="question")
            return
        
        if is_doctors_question(user_text) or (flow_state == "choosing_doctor" and is_doctor_list_request(user_text)):
            await reply_and_track(
                get_doctors_reply(clinic_id),
                flow_state=flow_state or "idle",
                intent="question"
            )
            return        

        if is_greeting_message(user_text) and flow_state == "idle" and intent in {"unknown", "greeting"}:
            is_returning = is_returning_client(chat_id)
            if is_returning:
                greeting_text = get_returning_client_greeting()
            else:
                greeting_text = get_clinic_greeting_reply(clinic_id, telegram_name)

            await reply_and_track(greeting_text, flow_state="idle", intent="greeting")
            return

        if flow_state == "cancel_flow":
            if is_yes_message(user_text) or any(word in text_low for word in CANCEL_KEYWORDS):
                cancel_result = cancel_active_booking_by_chat_id(chat_id)
                reset_runtime_session(chat_id, preserve_contact=True)

                await reply_and_track(
                    cancel_result.get("message", get_no_active_booking_response()),
                    flow_state="idle",
                    booking_status="cancelled",
                )
                if cancel_result.get("success"):
                    await notify_admins(build_admin_booking_notification("Клиент отменил запись", cancel_result.get("booking")))
                return

            if is_no_message(user_text):
                save_runtime_session(chat_id, flow_state="confirmation", pending_action="")
                await reply_and_track("Хорошо, оставляем запись без изменений.", flow_state="confirmation")
                return

            await reply_and_track(get_flow_prompt("cancel_flow", clinic_id), flow_state="cancel_flow", intent="cancel")
            return

        if intent == "cancel":
            if not existing_booking:
                reset_runtime_session(chat_id, preserve_contact=True)
                await reply_and_track(get_no_active_booking_response(), flow_state="idle")
                return

            appointment_text = format_slot_for_display(existing_booking.get("appointment_at", ""))
            service_text = existing_booking.get("service", "визит")

            save_runtime_session(chat_id, flow_state="cancel_flow", pending_action="cancel")

            await reply_and_track(
                f"Сейчас у вас запись на {appointment_text} ({service_text}). Отменяем?",
                flow_state="cancel_flow",
                intent="cancel",
            )
            return

        if intent == "operator":
            mark_conversation_waiting_operator(clinic_id, chat_id, bot_paused_until=get_bot_pause_until(clinic_id))
            await notify_clinic_owner(
                clinic_id,
                "operator",
                (
                    "Клиент просит оператора\n"
                    f"Клиент: {session.get('full_name') or telegram_name or 'Клиент'}\n"
                    f"Телефон/chat: {session.get('phone') or chat_id}\n"
                    f"Сообщение: {user_text[:400]}"
                ),
            )
            await reply_and_track(get_operator_request_response(), flow_state=flow_state, intent="operator")
            return

        if intent == "question" and not looks_like_datetime:

            answer = answer_direct_question(user_text, clinic_id)
            await reply_and_track(answer, flow_state=flow_state, intent="question")
            return

        if intent == "reschedule":
            if not existing_booking:
                reset_runtime_session(chat_id, preserve_contact=True)
                save_runtime_session(chat_id, flow_state="choosing_service")

                await reply_and_track(
                    "Сейчас активной записи нет. Если нужно, помогу оформить новую.",
                    flow_state="choosing_service",
                )
                return

            save_runtime_session(
                chat_id,
                flow_state="reschedule_flow",
                service=existing_booking.get("service") or session.get("service"),
                phone=existing_booking.get("phone") or session.get("phone"),
                full_name=existing_booking.get("full_name") or session.get("full_name") or telegram_name or "Клиент",
                suggested_slots=[],
            )

            flow_state = "reschedule_flow"

        if flow_state == "reschedule_flow":
            if not existing_booking:
                reset_runtime_session(chat_id, preserve_contact=True)
                save_runtime_session(chat_id, flow_state="choosing_service")

                await reply_and_track(
                    "Похоже, активной записи уже нет. Если нужно, помогу оформить новую.",
                    flow_state="choosing_service",
                )
                return

            if selected_suggested_slot or (is_yes_message(user_text) and session.get("suggested_slots")):
                chosen_slot = selected_suggested_slot or session.get("suggested_slots", [""])[0]
                if chosen_slot:
                    await prepare_confirmation(chosen_slot, is_reschedule=True)
                    return

            if is_flexible_time_message(user_text):
                flexible_slot = get_best_available_slot(
                    clinic_id,
                    existing_booking.get("service") or session.get("service", ""),
                    existing_booking.get("appointment_at", "") or session.get("preferred_datetime", ""),
                    exclude_booking_id=existing_booking.get("id"),
                )

                if flexible_slot:
                    await prepare_confirmation(flexible_slot, is_reschedule=True)
                else:
                    await reply_and_track(get_no_alternatives_message(), flow_state="reschedule_flow", intent="reschedule")
                return

            if not looks_like_datetime:
                prompt = get_repeat_guidance("reschedule_flow", clinic_id) if repeat_count else get_flow_prompt("reschedule_flow", clinic_id)
                current_time = format_slot_for_display(existing_booking.get("appointment_at", ""))

                await reply_and_track(
                    f"Сейчас запись стоит на {current_time}. {prompt}",
                    flow_state="reschedule_flow",
                    intent="reschedule",
                )
                return

            parsed_dt, error_text = parse_human_datetime(user_text, existing_booking.get("appointment_at", session.get("preferred_datetime", "")))

            if not parsed_dt:
                await reply_and_track(error_text, flow_state="reschedule_flow", intent="reschedule")
                return

            await prepare_confirmation(parsed_dt, is_reschedule=True)
            return

        if flow_state == "reschedule_confirmation":
            if is_yes_message(user_text):
                await reply_and_track("Хорошо, переношу запись на новое время.", flow_state="reschedule_confirmation", intent="reschedule")
                await attempt_booking(session.get("pending_datetime") or session.get("preferred_datetime", ""), is_reschedule=True)
                return

            if is_no_message(user_text):
                save_runtime_session(chat_id, flow_state="reschedule_flow", pending_datetime="")
                await reply_and_track("Хорошо, пришлите другое удобное время для переноса.", flow_state="reschedule_flow", intent="reschedule")
                return

            if selected_suggested_slot:
                await prepare_confirmation(selected_suggested_slot, is_reschedule=True)
                return

            if looks_like_datetime:
                parsed_dt, error_text = parse_human_datetime(user_text, session.get("preferred_datetime", ""))

                if not parsed_dt:
                    await reply_and_track(error_text, flow_state="reschedule_confirmation", intent="reschedule")
                    return

                await prepare_confirmation(parsed_dt, is_reschedule=True)
                return

            await reply_and_track(get_flow_prompt("reschedule_confirmation", clinic_id), flow_state="reschedule_confirmation", intent="reschedule")
            return

        if existing_booking and flow_state in {"idle", "confirmation"} and (intent == "booking" or service_candidate or looks_like_datetime):
            appointment_text = format_slot_for_display(existing_booking.get("appointment_at", ""))
            service_text = existing_booking.get("service", "визит")

            # Если клиент указал ДРУГУЮ услугу — предложить перенос с новой услугой
            if service_candidate and service_candidate.lower() != (existing_booking.get("service") or "").lower():
                save_runtime_session(
                    chat_id,
                    flow_state="reschedule_flow",
                    service=service_candidate,
                    phone=existing_booking.get("phone") or session.get("phone"),
                    full_name=existing_booking.get("full_name") or session.get("full_name") or telegram_name or "Клиент",
                    suggested_slots=[],
                )
                await reply_and_track(
                    f"Вы записаны на «{service_text}» ({appointment_text}). "
                    f"Хотите сменить на «{service_candidate}»? Подскажите удобное время.",
                    flow_state="reschedule_flow",
                    intent="reschedule",
                )
                return

            # Если клиент указал конкретное новое время — сразу идём в перенос
            if looks_like_datetime:
                parsed_dt, error_text = parse_human_datetime(user_text, existing_booking.get("appointment_at", ""))
                if parsed_dt:
                    save_runtime_session(
                        chat_id,
                        flow_state="reschedule_flow",
                        service=existing_booking.get("service") or session.get("service"),
                        phone=existing_booking.get("phone") or session.get("phone"),
                        full_name=existing_booking.get("full_name") or session.get("full_name") or telegram_name or "Клиент",
                        suggested_slots=[],
                    )
                    await prepare_confirmation(parsed_dt, is_reschedule=True)
                    return

            # Иначе — сообщаем о существующей записи и предлагаем опции
            await reply_and_track(
                get_booking_already_exists_response(appointment_text, service_text),
                flow_state="confirmation",
            )
            return
        if is_vague_doctor_request(user_text):
            save_runtime_session(chat_id, flow_state="choosing_doctor")
            await reply_and_track(
                "К какому специалисту вас записать?\nНапишите пожалуйста имя врача.",
                flow_state="choosing_doctor"
            )
            return


        if flow_state == "idle":
            if asks_slot_availability and not existing_booking:
                parsed_dt, error_text = parse_human_datetime(user_text, session.get("preferred_datetime", ""))

                if not parsed_dt:
                    await reply_and_track(error_text, flow_state="idle")
                    return

                service_for_check = session.get("service") or service_candidate or ""
                duration = get_service_duration(clinic_id, service_for_check) if service_for_check else 60

                if check_slot_available(parsed_dt, clinic_id, duration):
                    save_runtime_session(
                        chat_id,
                        preferred_datetime=parsed_dt,
                        pending_datetime=parsed_dt,
                        suggested_slots=[],
                    )
                    current_session = RUNTIME_SESSIONS.get(chat_id, session)
                    missing_field = get_first_missing_field(current_session)

                    if missing_field:
                        next_flow = field_flow_map.get(missing_field, "idle")
                        save_runtime_session(chat_id, flow_state=next_flow)
                        await reply_and_track(
                            f"Да, {format_slot_for_display(parsed_dt)} свободно. {get_flow_prompt(next_flow, clinic_id)}",
                            flow_state=next_flow,
                        )
                    else:
                        await prepare_confirmation(parsed_dt, is_reschedule=False)
                    return

                alternatives = find_alternative_slots(parsed_dt, clinic_id, duration_minutes=duration)
                save_runtime_session(chat_id, suggested_slots=alternatives)

                if alternatives:
                    alt_text = "\n".join(
                        [f"{i + 1}. {format_slot_for_display(slot)}" for i, slot in enumerate(alternatives)]
                    )
                    await reply_and_track(
                        f"На {format_slot_for_display(parsed_dt)} уже занято. Могу предложить:\n\n{alt_text}",
                        flow_state="waiting_datetime",
                    )
                    return

                await reply_and_track(
                    "На это время свободных окон нет. Попробуйте другую дату или время.",
                    flow_state="waiting_datetime",
                )
                return
        
            if service_candidate or intent == "booking":
                if service_candidate:
                    save_runtime_session(chat_id, service=service_candidate)

                await prompt_for_missing_data(repeated=repeat_count > 0)
                return

            if looks_like_datetime and not existing_booking:
                await prompt_for_missing_data(repeated=False)
                return

            if intent == "question" and not looks_like_datetime:

                answer = answer_direct_question(user_text, clinic_id)
                await reply_and_track(answer, flow_state="idle", intent="question")
                return

            await reply_and_track(get_clarifying_question(), flow_state="idle")
            return

    
        
        
        
        if flow_state == "choosing_doctor":
            doctors = get_active_doctors(clinic_id)

            if not doctors:
                await reply_and_track(
                    "Сейчас список врачей пуст. Администратор скоро добавит специалистов.",
                    flow_state="choosing_doctor"
                )
                return
            

            
            doctor_words = normalize_words(user_text)

            def overlap_count(user_words: set, target_words: set) -> int:
                return sum(1 for target_word in target_words if words_overlap(user_words, {target_word}))

            matched_doctor = None
            best_score = 0

            for doctor_item in doctors:
                name_words = normalize_words(doctor_item.get("full_name", ""))
                profession_words = normalize_words(doctor_item.get("profession", ""))
                name_score = overlap_count(doctor_words, name_words)
                profession_score = overlap_count(doctor_words, profession_words)
                score = name_score * 2 + profession_score

                if score > best_score:
                    best_score = score
                    matched_doctor = doctor_item

            if matched_doctor and best_score > 0:
                save_runtime_session(
                    chat_id,
                    doctor_profession=matched_doctor["profession"],
                    doctor_id=matched_doctor["id"],
                    selected_doctor_name=matched_doctor["full_name"],
                    service=matched_doctor["profession"],
                    flow_state="waiting_datetime"
                )

                await reply_and_track(
                    f"Хорошо. Записываем к врачу {matched_doctor['full_name']}.\n\nНа какую дату и время вас записать?",
                    flow_state="waiting_datetime"
                )
                return

            if intent == "booking":
                doctors_text = "\n".join(
                    f"• {d['full_name']} — {d['profession']}"
                    for d in doctors
                )

                await reply_and_track(
                    "К какому специалисту вас записать?\n\nСейчас доступны:\n" + doctors_text,
                    flow_state="choosing_doctor"
                )
                return

            doctors_text = "\n".join(
                f"• {d['full_name']} — {d['profession']}"
                for d in doctors
            )

            await reply_and_track(
                "Не смог найти такого врача. Напишите имя врача или специальность ещё раз.\n\nСейчас доступны:\n" + doctors_text,
                flow_state="choosing_doctor"
            )
            return

        if flow_state == "choosing_service":
            if not service_candidate:
                active_services = get_active_services(clinic_id)

                if is_yes_message(user_text) and len(active_services) == 1:
                    save_runtime_session(chat_id, service=active_services[0])
                    await prompt_for_missing_data()
                    return

                prompt = get_repeat_guidance("choosing_service", clinic_id) if repeat_count else get_flow_prompt("choosing_service", clinic_id)
                await reply_and_track(prompt, flow_state="choosing_service")
                return

            save_runtime_session(chat_id, service=service_candidate)
            await prompt_for_missing_data()
            return

        if flow_state == "waiting_name":
            bad_names = ["изменить услугу", "изменить время", "изменить телефон", "изменить имя"]

            if user_text.strip().lower() in bad_names:
                await reply_and_track(
                    "Напишите ваше имя, пожалуйста.",
                    flow_state="waiting_name"
                )
                return            
            if not name_candidate:
                prompt = get_repeat_guidance("waiting_name", clinic_id) if repeat_count else get_flow_prompt("waiting_name", clinic_id)
                await reply_and_track(prompt, flow_state="waiting_name")
                return

            save_runtime_session(chat_id, full_name=name_candidate)
            await prompt_for_missing_data()
            return

        if flow_state == "waiting_phone":
            if not phone_candidate:
                prompt = get_repeat_guidance("waiting_phone", clinic_id) if repeat_count else get_flow_prompt("waiting_phone", clinic_id)
                await reply_and_track(prompt, flow_state="waiting_phone")
                return

            save_runtime_session(chat_id, phone=phone_candidate)
            await prompt_for_missing_data()
            return

        if flow_state == "waiting_datetime":
            if selected_suggested_slot or (is_yes_message(user_text) and session.get("suggested_slots")):
                chosen_slot = selected_suggested_slot or session.get("suggested_slots", [""])[0]
                if chosen_slot:
                    await prepare_confirmation(chosen_slot, is_reschedule=False)
                    return

            if is_flexible_time_message(user_text):
                flexible_slot = get_best_available_slot(clinic_id, session.get("service", ""), session.get("preferred_datetime", ""))

                if flexible_slot:
                    await prepare_confirmation(flexible_slot, is_reschedule=False)
                else:
                    await reply_and_track(get_no_alternatives_message(), flow_state="waiting_datetime")
                return

            # Клиент хочет исправить другое поле — не время
            edit_field = detect_field_edit_request(user_text)
            if edit_field and edit_field != "preferred_datetime":
                field_flow = {"full_name": "waiting_name", "phone": "waiting_phone", "service": "choosing_service"}
                field_label = {"full_name": "имя", "phone": "телефон", "service": "услугу"}
                next_flow = field_flow.get(edit_field, "idle")
                save_runtime_session(chat_id, **{edit_field: ""}, flow_state=next_flow)
                await reply_and_track(
                    f"Хорошо, давайте исправим {field_label.get(edit_field, edit_field)}. "
                    + get_flow_prompt(next_flow, clinic_id),
                    flow_state=next_flow,
                )
                return

            if not looks_like_datetime:
                prompt = get_repeat_guidance("waiting_datetime", clinic_id) if repeat_count else get_flow_prompt("waiting_datetime", clinic_id)
                await reply_and_track(prompt, flow_state="waiting_datetime")
                return

            parsed_dt, error_text = parse_human_datetime(user_text, session.get("preferred_datetime", ""))

            if not parsed_dt:
                await reply_and_track(error_text, flow_state="waiting_datetime")
                return

            await prepare_confirmation(parsed_dt, is_reschedule=False)
            return

        if flow_state == "booking_confirmation":
            if is_yes_message(user_text):
                target_slot = session.get("pending_datetime") or session.get("preferred_datetime", "")

                if not target_slot and session.get("suggested_slots"):
                    target_slot = session.get("suggested_slots", [""])[0]

                await reply_and_track("Сейчас быстро подтвержу запись.", flow_state="booking_confirmation")
                await attempt_booking(target_slot, is_reschedule=False)
                return

            if is_no_message(user_text):
                save_runtime_session(chat_id, flow_state="waiting_datetime", pending_datetime="")
                await reply_and_track("Хорошо, пришлите другое удобное время.", flow_state="waiting_datetime")
                return

            if selected_suggested_slot:
                await prepare_confirmation(selected_suggested_slot, is_reschedule=False)
                return

            # Клиент хочет исправить конкретное поле
            edit_field = detect_field_edit_request(user_text)
            if edit_field:
                field_flow = {
                    "full_name": "waiting_name",
                    "phone": "waiting_phone",
                    "service": "choosing_service",
                    "preferred_datetime": "waiting_datetime",
                }
                field_label = {
                    "full_name": "имя",
                    "phone": "телефон",
                    "service": "услугу",
                    "preferred_datetime": "время",
                }

                next_flow = field_flow.get(edit_field, "idle")
                updates = {"flow_state": next_flow, edit_field: ""}
                if edit_field == "preferred_datetime":
                    updates["pending_datetime"] = ""
                save_runtime_session(chat_id, **updates)


                await reply_and_track(
                    f"Хорошо, давайте исправим {field_label.get(edit_field, edit_field)}. "
                    + get_flow_prompt(next_flow, clinic_id),
                    flow_state=next_flow,
                )
                return

            if looks_like_datetime:
                parsed_dt, error_text = parse_human_datetime(user_text, session.get("preferred_datetime", ""))

                if not parsed_dt:
                    await reply_and_track(error_text, flow_state="booking_confirmation")
                    return

                await prepare_confirmation(parsed_dt, is_reschedule=False)
                return

            await reply_and_track(get_flow_prompt("booking_confirmation", clinic_id), flow_state="booking_confirmation")
            return

        if flow_state == "confirmation":
            if any(word in text_low for word in ["спасибо", "благодарю", "благодарим", "спс", "thanks", "thank"]):
                await reply_and_track(
                    get_thanks_response(),
                    flow_state="confirmation",
                    booking_status="confirmed",
                )
                return
            if looks_like_datetime and not existing_booking:
                parsed_dt, error_text = parse_human_datetime(
                    user_text,
                    session.get("preferred_datetime", "")
                )

                if not parsed_dt:
                    await reply_and_track(error_text, flow_state="waiting_datetime")
                    return

                save_runtime_session(
                    chat_id,
                    preferred_datetime=parsed_dt,
                    pending_datetime=parsed_dt,
                    flow_state="booking_confirmation",
                )

                await prepare_confirmation(parsed_dt, is_reschedule=False)
                return

            if intent == "question" and not looks_like_datetime:

                answer = answer_direct_question(user_text, clinic_id)
                await reply_and_track(answer, flow_state="confirmation", intent="question")
                return

            if intent == "booking" and not existing_booking:
                reset_runtime_session(chat_id, preserve_contact=True)

                if service_candidate:
                    save_runtime_session(chat_id, service=service_candidate)

                await prompt_for_missing_data(repeated=False)
                return

            await reply_and_track(
                "Я на связи. Если нужно — помогу с переносом, отменой или новой записью.",
                flow_state="confirmation",
                booking_status="confirmed" if existing_booking else "in_progress",
            )
            return

        await reply_and_track(get_clarifying_question(), flow_state=flow_state or "idle")

    except Exception as e:
        logger.error(f"process_client_message error chat_id={chat_id}: {repr(e)}")
        traceback.print_exc()

        try:
            fallback_text = "Я на связи. Чем помочь: запись, перенос, отмена или вопрос?"
            await send_text(fallback_text)
        except Exception:
            pass
    
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.effective_chat and update.effective_chat.type != "private":
        logger.info("Telegram message skipped non-private chat_id=%s type=%s", update.effective_chat.id, update.effective_chat.type)
        return

    chat_id = str(update.message.chat.id)
    telegram_name = ""
    if update.effective_user:
        telegram_name = (update.effective_user.full_name or update.effective_user.first_name or "").strip()

    async def send_reply(text: str):
        flow_state = RUNTIME_SESSIONS.get(chat_id, {}).get("flow_state", "idle")
        await update.message.reply_text(text, reply_markup=get_main_menu_markup(flow_state))

    await process_client_message(chat_id, update.message.text, telegram_name, send_reply)

# Global variables for tracking today's automation metrics
automation_metrics = {
    "reminders_sent_today": 0,
    "followups_sent_today": 0,
    "last_reset_date": datetime.now().date()
}
AUTOMATION_TASK = None
AUTOMATION_TELEGRAM_APP = None


async def automation_checker():
    """
    Safe background automation task that handles booking reminders and lead follow-ups.
    Runs every 60 seconds, protected with try/except to prevent bot crashes.
    """
    logger.info("AUTOMATION: Starting safe automation checker")

    while True:
        try:
            # Reset daily counters if it's a new day
            today = datetime.now().date()
            if automation_metrics["last_reset_date"] != today:
                automation_metrics["reminders_sent_today"] = 0
                automation_metrics["followups_sent_today"] = 0
                automation_metrics["last_reset_date"] = today

            clinic_id = get_default_clinic()

            # 1. BOOKING REMINDERS - 24 hours
            telegram_app = AUTOMATION_TELEGRAM_APP
            try:
                bookings_24h = get_bookings_needing_24h_reminder()
                for booking in bookings_24h:
                    try:
                        if await send_booking_reminder_message(telegram_app, booking, "завтра"):
                            mark_reminder_24h_sent(booking["id"])
                            automation_metrics["reminders_sent_today"] += 1
                            logger.info("AUTOMATION: Sent 24h reminder booking=%s", booking["id"])
                    except Exception as e:
                        logger.error(f"AUTOMATION: Failed 24h reminder booking {booking['id']}: {e}")
            except Exception as e:
                logger.error(f"AUTOMATION: Failed to process 24h reminders: {e}")

            # 2. BOOKING REMINDERS - 2 hours
            try:
                bookings_2h = get_bookings_needing_2h_reminder()
                for booking in bookings_2h:
                    try:
                        if await send_booking_reminder_message(telegram_app, booking, "через 2 часа"):
                            mark_reminder_2h_sent(booking["id"])
                            automation_metrics["reminders_sent_today"] += 1
                            logger.info("AUTOMATION: Sent 2h reminder booking=%s", booking["id"])
                    except Exception as e:
                        logger.error(f"AUTOMATION: Failed 2h reminder booking {booking['id']}: {e}")
            except Exception as e:
                logger.error(f"AUTOMATION: Failed to process 2h reminders: {e}")

            # 3. LEAD FOLLOW-UPS
            try:
                conversations = get_conversations_needing_followup(clinic_id)
                for conv in conversations:
                    try:
                        if not telegram_app:
                            logger.info("AUTOMATION: Skip Telegram follow-up because Telegram app is not running")
                            continue
                        chat_id_raw = str(conv["chat_id"]).strip()
                        if not chat_id_raw or not chat_id_raw.lstrip("-").isdigit():
                            logger.info(f"AUTOMATION: Skip follow-up for non-Telegram chat_id={conv['chat_id']}")
                            continue
                        message = "Если запись ещё актуальна, могу помочь подобрать удобное время."
                        await app.bot.send_message(chat_id=int(chat_id_raw), text=message)
                        mark_followup_sent(conv["id"])
                        automation_metrics["followups_sent_today"] += 1
                        logger.info(f"AUTOMATION: Sent follow-up to chat {chat_id_raw}")
                    except Exception as e:
                        logger.error(f"AUTOMATION: Failed follow-up conv {conv['id']}: {e}")
            except Exception as e:
                logger.error(f"AUTOMATION: Failed to process follow-ups: {e}")

            logger.info(
                f"AUTOMATION: Cycle done. Reminders: {automation_metrics['reminders_sent_today']}, "
                f"Follow-ups: {automation_metrics['followups_sent_today']}"
            )

        except Exception as e:
            logger.error(f"AUTOMATION CRITICAL ERROR: {e}")

        await asyncio.sleep(60)


async def post_init_callback(app):
    """Start background automation after the Telegram bot initializes."""
    start_automation_once(app)


def start_automation_once(telegram_app=None):
    global AUTOMATION_TASK, AUTOMATION_TELEGRAM_APP
    if telegram_app:
        AUTOMATION_TELEGRAM_APP = telegram_app
    if AUTOMATION_TASK and not AUTOMATION_TASK.done():
        return
    logger.info("AUTOMATION: Initializing background automation")
    AUTOMATION_TASK = asyncio.create_task(automation_checker())


@app.on_event("startup")
async def fastapi_startup_callback():
    start_automation_once(None)



    
    
async def adddoctor_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return

    text = " ".join(context.args)

    if "|" not in text:
        await update.message.reply_text("Формат: /adddoctor Имя Фамилия | профессия")
        return

    full_name, profession = [x.strip() for x in text.split("|", 1)]

    chat_id = str(update.message.chat.id)
    clinic_id = get_clinic_by_chat_id(chat_id)
    ok = add_doctor(full_name, profession, clinic_id)

    if ok:
        await update.message.reply_text(f"Врач добавлен: {full_name} — {profession}")
    else:
        await update.message.reply_text("Не удалось добавить врача.")

async def doctors_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin_chat(update):
        return

    chat_id = str(update.message.chat.id)
    clinic_id = get_clinic_by_chat_id(chat_id)
    doctors = get_active_doctors(clinic_id)

    if not doctors:
        await update.message.reply_text("Врачей пока нет.")
        return

    text = "Врачи:\n\n" + "\n".join(
        [f"ID {d['id']}: {d['full_name']} — {d['profession']}" for d in doctors]
    )

    await update.message.reply_text(text)


if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="127.0.0.1", port=8000)


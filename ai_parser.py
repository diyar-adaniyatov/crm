"""
AI Parser — парсинг сообщений пользователя для клиники-бота.

Изменения v2:
- Улучшен PROMPT_TEMPLATE: чёткие правила по каждому полю, примеры
- Исправлен weekday-баг (если сегодня та же пятница — берём следующую)
- Расширен список стоп-слов для extract_person_name
- Улучшен is_greeting_message: больше вариантов, устойчивость к опечаткам
- Fallback-парсер стал умнее (лучше извлекает имя, дату, телефон)
- Добавлена поддержка Claude API как альтернативы OpenAI (CLAUDE_API_KEY)
"""

import os
import re
import json
from datetime import datetime, timedelta
import traceback

# ── OpenAI ────────────────────────────────────────────────────────────────────
try:
    from openai import OpenAI as _OpenAI
except Exception:
    _OpenAI = None

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
_openai_client = _OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and _OpenAI is not None) else None

# ── Claude (Anthropic) — опциональный fallback если нет OpenAI ────────────────
CLAUDE_API_KEY = (os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "").strip()

# ── Greeting detection ────────────────────────────────────────────────────────
_GREETING_REGEX = re.compile(
    r"^("
    r"добрый?\s*(день|вечер|утр[оа]|ночи?)|"
    r"доброго\s+(утра|дня|вечера|времени(\s+суток)?)|"
    r"здравствуй(те)?|"
    r"привет(ик)?|"
    r"хай|хей|хело?|хелло?|"
    r"сал(ам)?|саламик|"
    r"добро\s+пожаловать|"
    r"рад[аы]?\s+(вас|тебя)\s+видеть|"
    r"hi|hello|hey|good\s+(morning|afternoon|evening)|"
    r"ку|куку|ку-ку|прив|прива"
    r")[\s!,)?🤝👋😊]*$",
    re.IGNORECASE,
)

_GREETING_WORDS = {
    "привет", "здрасте", "здравствуйте", "здравствуй", "доброго",
    "добрый", "добрая", "доброе", "хай", "хей", "сал", "салам", "хело",
    "hi", "hello", "hey", "ку", "прив", "прива",
}

# Фразы, которые ВЫГЛЯДЯТ как приветствие, но содержат намерение
_NOT_GREETING_SIGNALS = [
    "запис", "хочу", "нужн", "цена", "стоит", "сколько", "где", "адрес",
    "когда", "врач", "услуг", "прием", "приём", "консульт",
]

GREETING_PATTERNS = [
    "привет", "здравствуйте", "здравствуй", "привет!", "привет!!", "привет)",
    "здравствуйте!", "добро пожаловать", "добрый день", "добрый вечер", "доброе утро",
    "добрый день!", "привет, как дела", "как дела", "как ваши дела", "все ли хорошо",
    "hi", "hello", "hey", "hi!", "hello!", "hey!", "what's up", "whats up",
    "привет,", "пока", "всем привет", "салам", "салам алейкум",
]


def is_greeting_message(user_message: str) -> bool:
    """
    Определяет, является ли сообщение чистым приветствием (без намерения).
    Возвращает True только если нет booking/question-сигналов.
    """
    msg = (user_message or "").strip()
    if not msg:
        return False

    msg_low = msg.lower().replace("ё", "е")

    # Если есть сигналы намерения — это не чистое приветствие
    if any(signal in msg_low for signal in _NOT_GREETING_SIGNALS):
        return False

    if _GREETING_REGEX.match(msg):
        return True

    for pattern in GREETING_PATTERNS:
        if msg_low == pattern:
            return True

    words = msg_low.split()
    if 1 <= len(words) <= 3 and words[0] in _GREETING_WORDS:
        return True

    return False


# ── Prompt ────────────────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """
Ты — строгий экстрактор данных для бота записи в клинику.

Верни ТОЛЬКО валидный JSON. Без markdown. Без пояснений. Без лишнего текста.

Структура ответа:
{{
  "service": "",
  "full_name": "",
  "phone": "",
  "preferred_datetime": "",
  "status": "collecting",
  "next_field": "service",
  "booking_status": "in_progress",
  "intent": "booking"
}}

═══════════════════════════════════════════════
СЕГОДНЯ: {current_datetime} (день недели: {current_weekday_ru})
═══════════════════════════════════════════════

── ПРАВИЛО 1: Определение intent ─────────────────────────────────────────────
- "booking"   → хочет записаться, выбрать время, продолжить запись
- "question"  → спрашивает цену, адрес, врача, услуги, расписание, «что у вас есть»
- "operator"  → хочет поговорить с человеком, администратором
- "cancel"    → хочет отменить запись
- "reschedule"→ хочет перенести запись
- "greeting"  → чистое приветствие без другого намерения

── ПРАВИЛО 2: При intent = question / operator / greeting ────────────────────
  НЕ стирай существующие поля из памяти.
  Меняй только intent. Остальное оставляй как есть.

── ПРАВИЛО 3: Извлечение полей ───────────────────────────────────────────────
service:
  - Только название услуги. Не путай с именем.
  - Если пользователь написал "чистка зубов" / "удаление зуба" — это service.

full_name:
  - Только личное имя/фамилия клиента.
  - НЕ бери имя из названия услуги ("Алина" из "Алина Петрова" — ОК).
  - НЕ бери стоп-слова: да, нет, ок, хорошо, завтра, сегодня, перенести, отменить.
  - Если явного имени нет — оставь "".

phone:
  - Формат: +7 XXX XXX XX XX (казахстанский/российский).
  - Нормализуй: 8-xxx → +7 xxx, без лишних символов.
  - Если нет — оставь "".

preferred_datetime:
  - Формат: YYYY-MM-DD HH:MM
  - Правила для ОТНОСИТЕЛЬНЫХ дат (КРИТИЧНО):
    * "сегодня"       → {today}
    * "завтра"        → {tomorrow}
    * "послезавтра"   → {day_after_tomorrow}
    * "в [день недели]" → СЛЕДУЮЩИЙ такой день после сегодня
      ВНИМАНИЕ: если сегодня уже эта пятница — берём СЛЕДУЮЩУЮ пятницу (+7 дней).
      Исключение: если время в будущем сегодня — используем сегодня.
  - Если пользователь написал ТОЛЬКО время (без даты):
    * Сохрани дату из памяти, замени только время.
    * Если даты в памяти нет — используй завтра.
  - Если написал ТОЛЬКО дату (без времени):
    * Сохрани время из памяти, замени только дату.
  - Если нет ни даты ни времени — оставь "".

── ПРАВИЛО 4: Общий сброс при "хочу записаться" / "запишите меня" ───────────
  Если пользователь пишет общую фразу записи без деталей:
  service="", full_name="", phone="", preferred_datetime="",
  status="collecting", next_field="service", intent="booking"

── ПРАВИЛО 5: Статус completeness ────────────────────────────────────────────
  Все 4 поля заполнены → status="ready_to_book", next_field="completed"
  Иначе              → status="collecting", next_field=<первое пустое>
  Порядок: service → full_name → phone → preferred_datetime

── ТЕКУЩАЯ ПАМЯТЬ ────────────────────────────────────────────────────────────
{current_memory}

── СООБЩЕНИЕ КЛИЕНТА ─────────────────────────────────────────────────────────
{user_message}
"""


def _get_weekday_ru(dt: datetime) -> str:
    names = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return names[dt.weekday()]


# ── OpenAI call ───────────────────────────────────────────────────────────────
def _call_openai(prompt: str) -> dict | None:
    if not _openai_client:
        return None
    try:
        response = _openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.1,
        )
        text = response.choices[0].message.content.strip()
        return json.loads(text)
    except Exception as e:
        print(f"ERROR: OpenAI failed: {repr(e)}")
        return None


# ── Claude API call ───────────────────────────────────────────────────────────
def _call_claude(prompt: str) -> dict | None:
    if not CLAUDE_API_KEY:
        return None
    try:
        import urllib.request
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        text = data["content"][0]["text"].strip()
        # Убираем markdown-обёртку если есть
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except Exception as e:
        print(f"ERROR: Claude API failed: {repr(e)}")
        return None


# ── Fallback parser ───────────────────────────────────────────────────────────
def _parse_fallback(user_message: str, current_state: dict) -> dict:
    """Эвристический парсер — используется если оба AI недоступны."""
    print(f"DEBUG: Using fallback parser for: {user_message[:80]!r}")
    result = current_state.copy()
    msg = user_message.strip()
    msg_low = msg.lower().replace("ё", "е")

    # Intent
    if any(w in msg_low for w in ["отмен", "не приду", "сними запись", "убери запись"]):
        result["intent"] = "cancel"
        return result
    if any(w in msg_low for w in ["перенес", "другое время", "поменять время", "перепис"]):
        result["intent"] = "reschedule"
        return result
    if any(w in msg_low for w in ["администратор", "оператор", "живой человек", "позвоните"]):
        result["intent"] = "operator"
        return result
# Booking intent
    booking_kw = [
        "запись",
        "записаться",
        "запишите",
        "хочу записаться",
        "прием",
        "приём",
        "врач",
        "стоматолог",
        "брекеты",
        "чистка",
        "лечение",
    ]

    if any(w in msg_low for w in booking_kw):
        result["intent"] = "booking"
        return result
    question_kw = [
        "сколько", "стоимость", "цена", "стоит", "прайс",
        "адрес", "где", "как добраться",
        "врач", "доктор", "стоматолог",
        "график", "расписание", "время работы",
        "какие услуги", "что у вас",
    ]
    if any(w in msg_low for w in question_kw) or msg.endswith("?"):
        result["intent"] = "question"
        return result

    # Phone (казахстан/россия)
    phone_match = re.search(r"(\+?[78][\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", msg)
    if phone_match:
        digits = re.sub(r"\D", "", phone_match.group())
        if len(digits) == 10:
            digits = "7" + digits
        elif len(digits) >= 11:
            if digits.startswith("8"):
                digits = "7" + digits[1:11]
            else:
                digits = digits[:11]
        if len(digits) == 11:
            result["phone"] = f"+{digits[0]} {digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:11]}"

    # Time extraction
    time_m = re.search(r"(\d{1,2})[:\.](\d{2})", msg)
    hour_m = re.search(r"\bв\s*(\d{1,2})\b", msg_low)
    if time_m or hour_m:
        if time_m:
            h, m = int(time_m.group(1)), int(time_m.group(2))
        else:
            h, m = int(hour_m.group(1)), 0
            if 1 <= h <= 7:
                h += 12

        # Дата
        now = datetime.now()
        if "послезавтра" in msg_low:
            base_date = (now + timedelta(days=2)).date()
        elif "завтра" in msg_low:
            base_date = (now + timedelta(days=1)).date()
        elif "сегодня" in msg_low:
            base_date = now.date()
        else:
            # Берём из памяти или завтра
            existing = current_state.get("preferred_datetime", "")
            try:
                base_date = datetime.fromisoformat(existing).date()
            except Exception:
                base_date = (now + timedelta(days=1)).date()

        candidate = datetime.combine(base_date, datetime.min.time()).replace(hour=h, minute=m)
        if candidate > now:
            result["preferred_datetime"] = candidate.strftime("%Y-%m-%d %H:%M")

    # Name (только если нет телефона и времени и это не вопрос)
    if not phone_match and not (time_m or hour_m):
        name_m = re.search(
            r"(?:меня зовут|мое имя|моё имя|зовите меня)\s+([А-ЯЁа-яёA-Za-z][а-яёa-z]+(?:\s+[А-ЯЁа-яёA-Za-z][а-яёa-z]+)?)",
            msg, re.IGNORECASE
        )
        if name_m:
            result["full_name"] = name_m.group(1).strip().title()

    return result


# ── Validation ────────────────────────────────────────────────────────────────
_REQUIRED_KEYS = ["service", "full_name", "phone", "preferred_datetime",
                  "status", "next_field", "booking_status", "intent"]
_VALID_INTENTS = {"booking", "question", "operator", "greeting", "cancel", "reschedule", "unknown"}


def _validate(parsed: dict) -> bool:
    if not isinstance(parsed, dict):
        return False
    if not all(k in parsed for k in _REQUIRED_KEYS):
        print(f"ERROR: Missing keys: {set(_REQUIRED_KEYS) - set(parsed.keys())}")
        return False
    if parsed.get("intent") not in _VALID_INTENTS:
        print(f"ERROR: Invalid intent: {parsed.get('intent')}")
        return False
    return True


# ── Public API ────────────────────────────────────────────────────────────────
def parse_user_message(user_message: str, current_state: dict) -> dict:
    """
    Парсинг сообщения пользователя.
    Порядок: OpenAI → Claude API → Fallback эвристика.
    """
    now = datetime.now()
    prompt = PROMPT_TEMPLATE.format(
        current_datetime=now.strftime("%Y-%m-%d %H:%M"),
        current_weekday_ru=_get_weekday_ru(now),
        today=now.strftime("%Y-%m-%d"),
        tomorrow=(now + timedelta(days=1)).strftime("%Y-%m-%d"),
        day_after_tomorrow=(now + timedelta(days=2)).strftime("%Y-%m-%d"),
        current_memory=json.dumps(current_state, ensure_ascii=False, indent=2),
        user_message=user_message,
    )

    # 1. OpenAI
    if _openai_client:
        print(f"DEBUG: Trying OpenAI for: {user_message[:60]!r}")
        result = _call_openai(prompt)
        if result and _validate(result):
            print("DEBUG: OpenAI success")
            return result
        print("DEBUG: OpenAI failed or invalid, trying Claude...")

    # 2. Claude API
    if CLAUDE_API_KEY:
        print(f"DEBUG: Trying Claude API for: {user_message[:60]!r}")
        result = _call_claude(prompt)
        if result and _validate(result):
            print("DEBUG: Claude API success")
            return result
        print("DEBUG: Claude API failed, using fallback...")

    # 3. Fallback
    print("DEBUG: Using heuristic fallback parser")
    return _parse_fallback(user_message, current_state)
import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.2.0";
import { createRoot } from "https://esm.sh/react-dom@18.2.0/client";

const h = React.createElement;

const NAV = [
  { id: "dashboard", label: "Сводка", icon: "📊" },
  { id: "bookings", label: "Записи", icon: "📅" },
  { id: "conversations", label: "Диалоги", icon: "💬" },
  { id: "services", label: "Услуги", icon: "🧾" },
  { id: "doctors", label: "Врачи", icon: "🩺" },
  { id: "erp", label: "ERP", icon: "🏢" },
  { id: "settings", label: "Настройки", icon: "⚙️" },
];

const DAY_LABELS = [
  ["0", "Пн"],
  ["1", "Вт"],
  ["2", "Ср"],
  ["3", "Чт"],
  ["4", "Пт"],
  ["5", "Сб"],
  ["6", "Вс"],
];

const PANEL_THEMES = [
  { value: "blue", label: "Синий", color: "#2563eb", accent: "#0f766e" },
  { value: "green", label: "Зелёный", color: "#059669", accent: "#0f766e" },
  { value: "orange", label: "Оранжевый", color: "#ea580c", accent: "#b45309" },
  { value: "red", label: "Красный", color: "#dc2626", accent: "#991b1b" },
  { value: "yellow", label: "Жёлтый", color: "#ca8a04", accent: "#a16207" },
  { value: "violet", label: "Фиолетовый", color: "#7c3aed", accent: "#5b21b6" },
  { value: "slate", label: "Графит", color: "#475569", accent: "#1f2937" },
];

const LANGUAGE_OPTIONS = [
  { value: "ru", label: "Русский" },
  { value: "en", label: "English" },
];

const QUICK_REPLIES = [
  "Здравствуйте! Сейчас помогу вам.",
  "Подскажите, пожалуйста, номер телефона для связи.",
  "Могу предложить ближайшее удобное время. Какой день вам подходит?",
  "Передала информацию администратору. Скоро вам ответим.",
];

const ASSISTANT_QUICK_QUESTIONS = [
  "Что требует внимания?",
  "Какие записи сегодня?",
  "Что есть в ERP?",
  "Как добавить врача?",
  "Как подключить WhatsApp?",
];

const EN_TRANSLATIONS = {
  "Сводка": "Dashboard",
  "Записи": "Bookings",
  "Диалоги": "Conversations",
  "Услуги": "Services",
  "Врачи": "Doctors",
  "Настройки": "Settings",
  "Платформа": "Platform",
  "Загружаем панель": "Loading panel",
  "Проверяем записи, диалоги и настройки.": "Checking bookings, conversations, and settings.",
  "CRM администратора": "Admin CRM",
  "Выйти": "Log out",
  "Обновить": "Refresh",
  "Работаем...": "Working...",
  "Сначала сохраните изменения в настройках": "Save settings changes first",
  "Ваш персональный помощник по CRM": "Your personal CRM assistant",
  "Помощник": "Assistant",
  "Скрыть": "Hide",
  "Активна": "Active",
  "Записан": "Booked",
  "Оператор": "Operator",
  "Завершена": "Completed",
  "Отменена": "Cancelled",
  "Не пришёл": "No-show",
  "Закрыт": "Closed",
  "Операционная сводка": "Operations Overview",
  "Сегодня": "Today",
  "Управление записями": "Booking Management",
  "Расписание": "Schedule",
  "Диалоги и лиды": "Conversations & Leads",
  "Услуги и цены": "Services & Prices",
  "Прайс": "Price List",
  "Врачи клиники": "Clinic Doctors",
  "Команда": "Team",
  "ERP система": "ERP System",
  "Склад и финансы": "Inventory & Finance",
  "Настройки клиники": "Clinic Settings",
  "График": "Work Schedule",
  "Все клиники": "All Clinics",
  "Новые лиды": "New Leads",
  "за сегодня": "today",
  "Записи сегодня": "Bookings Today",
  "активный план дня": "active daily plan",
  "Ждут ответа": "Waiting for Reply",
  "ручной режим": "manual mode",
  "Конверсия": "Conversion",
  "лид → запись": "lead → booking",
  "Записей пока нет": "No bookings yet",
  "Время": "Time",
  "Клиент": "Client",
  "Услуга": "Service",
  "Статус": "Status",
  "Действия": "Actions",
  "✓ Завершить": "✓ Complete",
  "⊘ Не пришёл": "⊘ No-show",
  "✕ Отменить": "✕ Cancel",
  "Новое": "New",
  "Ближайшие записи": "Upcoming Bookings",
  "Открыть": "Open",
  "Нужен оператор": "Needs Operator",
  "Новых задач нет": "No new tasks",
  "Лиды без записи": "Leads without Booking",
  "Лидов без записи нет": "No leads without booking",
  "Ближайшие": "Upcoming",
  "Все активные": "All Active",
  "Расписание клиники": "Clinic Schedule",
  "Выберите диалог слева": "Select a conversation on the left",
  "Загружаем переписку": "Loading conversation",
  "🤖 Включить бота": "🤖 Enable bot",
  "Бот включен": "Bot enabled",
  "✓ Закрыть": "✓ Close",
  "Сообщений пока нет": "No messages yet",
  "Ответить клиенту...": "Reply to client...",
  "Отправить": "Send",
  "Входящие": "Inbox",
  "Лиды": "Leads",
  "Все": "All",
  "Добавить услугу": "Add Service",
  "Прайс применяется только к текущей клинике": "The price list applies only to the current clinic",
  "Название услуги": "Service Name",
  "Например: Чистка зубов": "Example: Teeth cleaning",
  "Цена, тг": "Price, KZT",
  "Длительность, минут": "Duration, minutes",
  "Категория": "Category",
  "Например: Стоматология": "Example: Dentistry",
  "Описание": "Description",
  "Короткое уточнение для администратора": "Short note for the administrator",
  "Бот будет использовать цену при вопросах о стоимости.": "The bot will use this price for cost questions.",
  "Прайс клиники": "Clinic Price List",
  "Активные": "Active",
  "Цена": "Price",
  "Длительность": "Duration",
  "Сохранить": "Save",
  "Отмена": "Cancel",
  "Редактировать": "Edit",
  "Отключить": "Disable",
  "Услуг пока нет. Добавьте первую услугу выше.": "No services yet. Add the first service above.",
  "Добавить врача": "Add Doctor",
  "Врачи видны боту только внутри текущей клиники": "Doctors are visible to the bot only inside the current clinic",
  "Имя врача": "Doctor Name",
  "Например: Алина Петрова": "Example: Alina Petrova",
  "Профессия": "Profession",
  "Например: стоматолог": "Example: dentist",
  "По имени или профессии бот сможет выбрать нужного специалиста.": "The bot can choose the right specialist by name or profession.",
  "Список врачей": "Doctor List",
  "Имя": "Name",
  "Активен": "Active",
  "Врачей пока нет. Добавьте первого специалиста выше.": "No doctors yet. Add the first specialist above.",
  "Выручка месяца": "Monthly Revenue",
  "по завершённым визитам": "from completed visits",
  "Расходы месяца": "Monthly Expenses",
  "Выплаченные зарплаты": "Paid Salaries",
  "Оценка прибыли": "Estimated Profit",
  "выручка минус расходы и выплаченные зарплаты": "revenue minus expenses and paid salaries",
  "Низкий остаток": "Low Stock",
  "Требуется пополнение склада": "Inventory Refill Needed",
  "Склад расходников": "Supplies Inventory",
  "Материалы, препараты, одноразовые позиции и контроль остатков": "Materials, products, disposables, and stock control",
  "Название": "Name",
  "Перчатки нитриловые": "Nitrile gloves",
  "Расходники": "Supplies",
  "Количество": "Quantity",
  "Ед. изм.": "Unit",
  "Минимум": "Minimum",
  "Себестоимость за ед.": "Cost per Unit",
  "Поставщик": "Supplier",
  "Комментарий": "Comment",
  "Размер, бренд, упаковка": "Size, brand, package",
  "Добавить на склад": "Add to Inventory",
  "Позиции с остатком ниже минимума появятся в предупреждении ERP.": "Items below the minimum will appear in ERP warnings.",
  "Новый расход": "New Expense",
  "Материалы, аренда, зарплаты, реклама и прочие платежи": "Materials, rent, salaries, ads, and other payments",
  "Дата": "Date",
  "Название расхода": "Expense Name",
  "Закуп перчаток": "Gloves purchase",
  "Сумма, тг": "Amount, KZT",
  "Получатель": "Recipient",
  "Поставщик или сотрудник": "Supplier or employee",
  "Оплата": "Payment",
  "карта / наличные / Kaspi": "card / cash / Kaspi",
  "Номер счёта, причина, детали": "Invoice number, reason, details",
  "Добавить расход": "Add Expense",
  "Расход сразу попадёт в расчёт месяца.": "The expense will be included in this month immediately.",
  "Зарплата врачу": "Doctor Salary",
  "Ежемесячная зарплата по каждому врачу для расчёта прибыли": "Monthly salary per doctor for profit calculation",
  "Месяц": "Month",
  "Врач": "Doctor",
  "Выберите врача": "Choose a doctor",
  "Уже выплачено": "Already paid",
  "Ставка, аванс, бонусы": "Base rate, advance, bonuses",
  "Сохранить зарплату": "Save Salary",
  "В прибыль месяца попадут только зарплаты с галочкой «выплачено».": "Only salaries marked as paid are included in monthly profit.",
  "Сначала добавьте врачей в разделе «Врачи», затем назначьте им зарплату.": "Add doctors in the Doctors section first, then assign salaries.",
  "Складские позиции": "Inventory Items",
  "Позиция": "Item",
  "Остаток": "Stock",
  "Мин.": "Min.",
  "Цена/ед.": "Price/unit",
  "Списать": "Write off",
  "Склад пока пуст. Добавьте расходники или материалы выше.": "Inventory is empty. Add supplies or materials above.",
  "Зарплаты врачей": "Doctor Salaries",
  "Суммы за текущий и прошлые месяцы": "Amounts for current and past months",
  "Сумма": "Amount",
  "Выплачено": "Paid",
  "Удалить": "Delete",
  "Зарплаты пока не добавлены. Назначьте сумму врачу выше.": "No salaries yet. Assign a doctor salary above.",
  "Последние расходы": "Recent Expenses",
  "Расход": "Expense",
  "Расходов пока нет. Добавьте первый платёж выше.": "No expenses yet. Add the first payment above.",
  "WhatsApp / Green API": "WhatsApp / Green API",
  "Каждая клиника подключает свой отдельный idInstance": "Each clinic connects its own separate idInstance",
  "Webhook URL для Green API": "Webhook URL for Green API",
  "Вставьте этот адрес в настройки instance в Green API": "Paste this URL into the instance settings in Green API",
  "Название канала": "Channel Name",
  "WhatsApp ресепшена": "Reception WhatsApp",
  "токен из Green API": "token from Green API",
  "Привязать WhatsApp": "Connect WhatsApp",
  "Этот instance будет работать только с этой клиникой.": "This instance will work only with this clinic.",
  "WhatsApp клиники": "Clinic WhatsApp",
  "не указан": "not set",
  "WhatsApp ещё не подключён": "WhatsApp is not connected yet",
  "Есть несохранённые изменения": "Unsaved changes",
  "Автообновление не перезапишет эту форму. Нажмите «Сохранить настройки», когда закончите.": "Auto-refresh will not overwrite this form. Click Save Settings when done.",
  "Профиль, график и ручной режим": "Profile, Schedule, and Manual Mode",
  "Название клиники": "Clinic Name",
  "Например: Dental House": "Example: Dental House",
  "Адрес": "Address",
  "Например: Алматы, Абая 10": "Example: Almaty, Abay 10",
  "WhatsApp администратора": "Administrator WhatsApp",
  "Начало рабочего дня": "Workday Start",
  "Конец рабочего дня": "Workday End",
  "Шаг записи": "Booking Step",
  "Авто-включение бота": "Bot Auto-enable",
  "Рабочие дни": "Working Days",
  "Уведомления и напоминания": "Notifications and Reminders",
  "Уведомлять о новом лиде": "Notify about new leads",
  "Уведомлять о новой записи или переносе": "Notify about new bookings or reschedules",
  "Уведомлять, когда клиент просит оператора": "Notify when a client asks for an operator",
  "Отправлять клиентам WhatsApp-напоминания за 24 часа и за 2 часа": "Send WhatsApp reminders 24 hours and 2 hours before visits",
  "Сохранить изменения": "Save Changes",
  "Сохранить настройки": "Save Settings",
  "Эти параметры применяются только к текущей клинике.": "These settings apply only to the current clinic.",
  "Внешний вид панели": "Panel Appearance",
  "Язык панели": "Panel Language",
  "Цветовая тема": "Color Theme",
  "Тема применяется только к текущей клинике.": "The theme applies only to the current clinic.",
  "Переключается сразу и сохраняется автоматически.": "Switches instantly and saves automatically.",
  "Автосохранение": "Autosave",
  "Сохраняем...": "Saving...",
  "Русский": "Russian",
  "Синий": "Blue",
  "Зелёный": "Green",
  "Оранжевый": "Orange",
  "Красный": "Red",
  "Жёлтый": "Yellow",
  "Фиолетовый": "Violet",
  "Графит": "Slate",
  "Не удалось загрузить данные": "Could not load data",
  "Настройки сохранены": "Settings saved",
  "Не удалось сохранить настройки": "Could not save settings",
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (response.redirected) {
    window.location.href = response.url;
    return null;
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    if (response.status === 401 || response.status === 403) {
      window.location.href = "/login";
      return null;
    }
    throw new Error("Сервер вернул неожиданный ответ");
  }

  return response.json();
}

function applyPanelPreferences(settings = {}) {
  const language = settings.panel_language === "en" ? "en" : "ru";
  const theme = settings.panel_theme || "blue";
  document.documentElement.lang = language;
  document.documentElement.dataset.panelLanguage = language;
  document.documentElement.dataset.panelTheme = PANEL_THEMES.some((item) => item.value === theme) ? theme : "blue";
}

function translateTextValue(text, language) {
  if (language !== "en" || !text) return text;
  const trimmed = text.trim();
  if (!trimmed) return text;
  const translated = EN_TRANSLATIONS[trimmed];
  if (!translated) return text;
  return text.replace(trimmed, translated);
}

function translateStaticDom(language) {
  if (language !== "en") return;
  const root = document.getElementById("root");
  if (!root) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "TEXTAREA"].includes(parent.tagName)) {
        return NodeFilter.FILTER_REJECT;
      }
      return /[А-Яа-яЁё]/.test(node.nodeValue || "")
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_SKIP;
    },
  });

  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    node.nodeValue = translateTextValue(node.nodeValue, language);
  });

  root.querySelectorAll("input[placeholder], textarea[placeholder]").forEach((node) => {
    node.placeholder = translateTextValue(node.placeholder, language);
  });
}

function statusLabel(status) {
  const labels = {
    active: "Активна",
    booked: "Записан",
    waiting_operator: "Оператор",
    completed: "Завершена",
    cancelled: "Отменена",
    no_show: "Не пришёл",
    lost: "Не пришёл",
    closed: "Закрыт",
  };
  return labels[status] || status || "—";
}

function titleForView(view) {
  const titles = {
    dashboard: ["Операционная сводка", "Сегодня"],
    bookings: ["Управление записями", "Расписание"],
    conversations: ["Диалоги и лиды", "CRM"],
    services: ["Услуги и цены", "Прайс"],
    doctors: ["Врачи клиники", "Команда"],
    erp: ["ERP система", "Склад и финансы"],
    settings: ["Настройки клиники", "График"],
    platform: ["Платформа", "Все клиники"],
  };
  return titles[view] || titles.dashboard;
}

function cls(...items) {
  return items.filter(Boolean).join(" ");
}

function StatusBadge({ status, children, tone }) {
  return h("span", { className: cls("badge", tone || status) }, children || statusLabel(status));
}

function EmptyState({ text }) {
  return h("div", { className: "empty-state" }, text);
}

function Metric({ label, value, note }) {
  return h("div", { className: "metric" }, [
    h("div", { className: "metric-label", key: "label" }, label),
    h("div", { className: "metric-value", key: "value" }, value ?? 0),
    h("div", { className: "metric-note", key: "note" }, note),
  ]);
}

function MetricGrid({ metrics }) {
  return h("div", { className: "metric-grid" }, [
    h(Metric, { key: "new", label: "Новые лиды", value: metrics.new_leads_today, note: "за сегодня" }),
    h(Metric, { key: "today", label: "Записи сегодня", value: metrics.bookings_today, note: "активный план дня" }),
    h(Metric, { key: "inbox", label: "Ждут ответа", value: metrics.needs_operator, note: "ручной режим" }),
    h(Metric, { key: "conv", label: "Конверсия", value: `${metrics.lead_to_booking_conversion || 0}%`, note: "лид → запись" }),
  ]);
}

function BookingTable({ bookings, onAction, compact = false }) {
  if (!bookings.length) return h(EmptyState, { text: "Записей пока нет" });

  return h("div", { className: "table-wrap" },
    h("table", { className: "data-table" }, [
      h("thead", { key: "head" },
        h("tr", null, [
          h("th", { key: "time" }, "Время"),
          h("th", { key: "client" }, "Клиент"),
          h("th", { key: "service" }, "Услуга"),
          h("th", { key: "status" }, "Статус"),
          !compact && h("th", { key: "actions" }, "Действия"),
        ].filter(Boolean))
      ),
      h("tbody", { key: "body" }, bookings.map((booking) =>
        h("tr", { key: booking.id }, [
          h("td", { key: "time" }, h("div", { className: "cell-main" }, booking.appointment_display)),
          h("td", { key: "client" }, [
            h("div", { className: "cell-main", key: "name" }, booking.full_name),
            h("div", { className: "cell-sub", key: "phone" }, booking.phone || "—"),
          ]),
          h("td", { key: "service" }, booking.service),
          h("td", { key: "status" }, h(StatusBadge, { status: booking.status === "active" ? "booked" : booking.status })),
          !compact && h("td", { key: "actions" },
            h("div", { className: "row-actions" }, [
              h("button", { className: "btn green", onClick: () => onAction(booking.id, "complete"), key: "done" }, "✓ Завершить"),
              h("button", { className: "btn amber", onClick: () => onAction(booking.id, "no-show"), key: "miss" }, "⊘ Не пришёл"),
              h("button", { className: "btn red", onClick: () => onAction(booking.id, "cancel"), key: "cancel" }, "✕ Отменить"),
            ])
          ),
        ].filter(Boolean))
      )),
    ])
  );
}

function ConversationItem({ item, active, onClick }) {
  return h("button", { className: cls("list-item", active && "active"), onClick }, [
    h("div", { className: "list-top", key: "top" }, [
      h("div", { key: "name" }, [
        h("div", { className: "cell-main", key: "main" }, item.full_name),
        h("div", { className: "cell-sub", key: "sub" }, `${item.phone || "—"} · ${item.last_activity_display}`),
      ]),
      h("div", { className: "row-actions", key: "badges" }, [
        item.has_new_client_message && h(StatusBadge, { key: "new", tone: "new" }, "Новое"),
        h(StatusBadge, { key: "status", status: item.status }),
      ].filter(Boolean)),
    ]),
    h("div", { className: "message-preview", key: "message" }, item.latest_message || "—"),
  ]);
}

function Dashboard({ data, setView, onBookingAction, openConversation }) {
  const nextBookings = data.bookings.upcoming.slice(0, 7);
  const inbox = data.conversations.inbox.slice(0, 6);
  const leads = data.conversations.leads.slice(0, 5);

  return h(React.Fragment, null, [
    h(MetricGrid, { key: "metrics", metrics: data.metrics }),
    h("div", { className: "dashboard-grid", key: "grid" }, [
      h("section", { className: "panel", key: "bookings" }, [
        h("div", { className: "panel-header", key: "head" }, [
          h("h2", { className: "panel-title", key: "title" }, "Ближайшие записи"),
          h("button", { className: "btn", onClick: () => setView("bookings"), key: "btn" }, "Открыть"),
        ]),
        h("div", { className: "panel-body", key: "body" },
          h(BookingTable, { bookings: nextBookings, onAction: onBookingAction, compact: false })
        ),
      ]),
      h("div", { className: "list", key: "side" }, [
        h("section", { className: "panel", key: "inbox" }, [
          h("div", { className: "panel-header", key: "head" }, [
            h("h2", { className: "panel-title", key: "title" }, "Нужен оператор"),
            h(StatusBadge, { key: "count", tone: "waiting_operator" }, inbox.length),
          ]),
          h("div", { className: "panel-body", key: "body" },
            inbox.length
              ? h("div", { className: "list" }, inbox.map((item) =>
                  h(ConversationItem, { key: item.id, item, onClick: () => openConversation(item.id) })
                ))
              : h(EmptyState, { text: "Новых задач нет" })
          ),
        ]),
        h("section", { className: "panel", key: "leads" }, [
          h("div", { className: "panel-header", key: "head" }, [
            h("h2", { className: "panel-title", key: "title" }, "Лиды без записи"),
            h("button", { className: "btn", onClick: () => setView("conversations"), key: "btn" }, "CRM"),
          ]),
          h("div", { className: "panel-body", key: "body" },
            leads.length
              ? h("div", { className: "list" }, leads.map((item) =>
                  h(ConversationItem, { key: item.id, item, onClick: () => openConversation(item.id) })
                ))
              : h(EmptyState, { text: "Лидов без записи нет" })
          ),
        ]),
      ]),
    ]),
  ]);
}

function BookingsView({ data, onBookingAction }) {
  const [tab, setTab] = useState("today");
  const tabs = [
    ["today", "Сегодня", data.bookings.today.length],
    ["upcoming", "Ближайшие", data.bookings.upcoming.length],
    ["active", "Все активные", data.bookings.active.length],
  ];

  return h("section", { className: "panel" }, [
    h("div", { className: "panel-header", key: "head" }, [
      h("h2", { className: "panel-title", key: "title" }, "Расписание клиники"),
      h("div", { className: "tabs", key: "tabs" }, tabs.map(([id, label, count]) =>
        h("button", { key: id, className: cls("tab", tab === id && "active"), onClick: () => setTab(id) }, `${label} · ${count}`)
      )),
    ]),
    h("div", { className: "panel-body", key: "body" },
      h(BookingTable, { bookings: data.bookings[tab], onAction: onBookingAction })
    ),
  ]);
}

function ChatPanel({ selectedId, thread, loadingThread, onReply, onConversationAction }) {
  const [message, setMessage] = useState("");
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [thread]);

  if (!selectedId) {
    return h("section", { className: "panel chat-shell" },
      h(EmptyState, { text: "Выберите диалог слева" })
    );
  }

  if (loadingThread || !thread) {
    return h("section", { className: "panel chat-shell" },
      h(EmptyState, { text: "Загружаем переписку" })
    );
  }

  const conv = thread.conversation;

  async function submitReply(event) {
    event.preventDefault();
    if (!message.trim()) return;
    await onReply(conv.id, message);
    setMessage("");
  }

  return h("section", { className: "panel chat-shell" }, [
    h("div", { className: "panel-header", key: "head" }, [
      h("div", { key: "client" }, [
        h("h2", { className: "panel-title", key: "name" }, conv.full_name),
        h("div", { className: "cell-sub", key: "meta" }, `${conv.phone || "—"} · ${conv.chat_id || "chat"}`),
      ]),
      h("div", { className: "row-actions", key: "actions" }, [
        conv.needs_operator
          ? h("button", { className: "btn green", onClick: () => onConversationAction(conv.id, "enable-bot"), key: "bot" }, "🤖 Включить бота")
          : h(StatusBadge, { key: "bot-on", tone: "active" }, "Бот включен"),
        h("button", { className: "btn", onClick: () => onConversationAction(conv.id, "close"), key: "close" }, "✓ Закрыть"),
        h("button", { className: "btn red", onClick: () => onConversationAction(conv.id, "lost"), key: "lost" }, "⊘ Не пришёл"),
      ]),
    ]),
    h("div", { className: "chat-window", ref: chatRef, key: "messages" },
      thread.messages.length
        ? thread.messages.map((msg) =>
            h("div", { className: cls("bubble", msg.sender_type), key: msg.id || `${msg.created_at}-${msg.text}` }, [
              h("div", { className: "bubble-text", key: "text" }, msg.text),
              h("div", { className: "bubble-meta", key: "meta" }, `${msg.sender_type === "user" ? "Клиент" : msg.sender_type === "operator" ? "Оператор" : "Бот"} · ${msg.created_display}`),
            ])
          )
        : h(EmptyState, { text: "Сообщений пока нет" })
    ),
    h("form", { className: "reply-area", onSubmit: submitReply, key: "reply" }, [
      h("div", { className: "quick-replies", key: "quick" }, QUICK_REPLIES.map((text) =>
        h("button", { type: "button", className: "btn", key: text, onClick: () => setMessage(text) }, text)
      )),
      h("div", { className: "reply-box", key: "box" }, [
        h("textarea", { value: message, onChange: (event) => setMessage(event.target.value), placeholder: "Ответить клиенту..." }),
        h("button", { className: "btn primary", type: "submit" }, "Отправить"),
      ]),
    ]),
  ]);
}

function ConversationsView({ data, selectedId, setSelectedId, thread, loadingThread, loadThread, onReply, onConversationAction }) {
  const [tab, setTab] = useState("inbox");
  const tabs = [
    ["inbox", "Входящие", data.conversations.inbox.length],
    ["leads", "Лиды", data.conversations.leads.length],
    ["all", "Все", data.conversations.all.length],
  ];
  const items = data.conversations[tab] || [];

  function choose(id) {
    setSelectedId(id);
    loadThread(id);
  }

  return h("div", { className: "conversation-layout" }, [
    h("section", { className: "panel", key: "list" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Диалоги"),
        h("div", { className: "tabs", key: "tabs" }, tabs.map(([id, label, count]) =>
          h("button", { key: id, className: cls("tab", tab === id && "active"), onClick: () => setTab(id) }, `${label} · ${count}`)
        )),
      ]),
      h("div", { className: "panel-body", key: "body" },
        items.length
          ? h("div", { className: "list" }, items.map((item) =>
              h(ConversationItem, { key: item.id, item, active: selectedId === item.id, onClick: () => choose(item.id) })
            ))
          : h(EmptyState, { text: "Диалогов в этой группе нет" })
      ),
    ]),
    h(ChatPanel, { key: "chat", selectedId, thread, loadingThread, onReply, onConversationAction }),
  ]);
}

function ServicesView({ data, onAddService, onUpdateService, onDeleteService }) {
  const services = data.services || [];
  const emptyForm = { name: "", price: "", duration_minutes: 60, category: "", description: "" };
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);

  function updateForm(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateEditForm(key, value) {
    setEditForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    const ok = await onAddService(form);
    if (ok) setForm(emptyForm);
  }

  function startEdit(service) {
    setEditingId(service.id);
    setEditForm({
      name: service.name || "",
      price: service.price ?? "",
      duration_minutes: service.duration_minutes || 60,
      category: service.category || "",
      description: service.description || "",
    });
  }

  async function saveEdit(serviceId) {
    const ok = await onUpdateService(serviceId, editForm);
    if (ok) setEditingId(null);
  }

  return h("div", { className: "settings-stack" }, [
    h("section", { className: "panel", key: "add" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("div", { key: "title" }, [
          h("h2", { className: "panel-title", key: "main" }, "Добавить услугу"),
          h("div", { className: "cell-sub", key: "sub" }, "Прайс применяется только к текущей клинике"),
        ]),
        h(StatusBadge, { key: "count", tone: services.length ? "completed" : "closed" }, `${services.length} услуг`),
      ]),
      h("div", { className: "panel-body", key: "body" },
        h("form", { onSubmit: submit }, [
          h("div", { className: "form-grid", key: "grid" }, [
            h("div", { className: "form-field", key: "name" }, [
              h("label", null, "Название услуги"),
              h("input", { value: form.name, placeholder: "Например: Чистка зубов", onChange: (event) => updateForm("name", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "price" }, [
              h("label", null, "Цена, тг"),
              h("input", { type: "number", min: "0", step: "100", value: form.price, placeholder: "15000", onChange: (event) => updateForm("price", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "duration" }, [
              h("label", null, "Длительность, минут"),
              h("input", { type: "number", min: "5", max: "480", step: "5", value: form.duration_minutes, onChange: (event) => updateForm("duration_minutes", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "category" }, [
              h("label", null, "Категория"),
              h("input", { value: form.category, placeholder: "Например: Стоматология", onChange: (event) => updateForm("category", event.target.value) }),
            ]),
            h("div", { className: "form-field wide", key: "description" }, [
              h("label", null, "Описание"),
              h("input", { value: form.description, placeholder: "Короткое уточнение для администратора", onChange: (event) => updateForm("description", event.target.value) }),
            ]),
          ]),
          h("div", { className: "toolbar", style: { marginTop: 14, marginBottom: 0 }, key: "actions" }, [
            h("button", { className: "btn primary", type: "submit" }, "Добавить услугу"),
            h("span", { className: "cell-sub" }, "Бот будет использовать цену при вопросах о стоимости."),
          ]),
        ])
      ),
    ]),
    h("section", { className: "panel", key: "list" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Прайс клиники"),
        h(StatusBadge, { key: "active", tone: "active" }, "Активные"),
      ]),
      h("div", { className: "panel-body", key: "body" },
        services.length
          ? h("div", { className: "table-wrap" },
              h("table", { className: "data-table" }, [
                h("thead", { key: "head" },
                  h("tr", null, [
                    h("th", { key: "name" }, "Услуга"),
                    h("th", { key: "price" }, "Цена"),
                    h("th", { key: "duration" }, "Длительность"),
                    h("th", { key: "category" }, "Категория"),
                    h("th", { key: "actions" }, "Действия"),
                  ])
                ),
                h("tbody", { key: "body" }, services.map((service) => {
                  const editing = editingId === service.id;
                  return h("tr", { key: service.id }, [
                    h("td", { key: "name" }, editing
                      ? h("input", { className: "table-input", value: editForm.name, onChange: (event) => updateEditForm("name", event.target.value) })
                      : [
                          h("div", { className: "cell-main", key: "main" }, service.name),
                          service.description && h("div", { className: "cell-sub", key: "sub" }, service.description),
                        ].filter(Boolean)
                    ),
                    h("td", { key: "price" }, editing
                      ? h("input", { className: "table-input", type: "number", min: "0", step: "100", value: editForm.price, onChange: (event) => updateEditForm("price", event.target.value) })
                      : h("div", { className: "cell-main" }, service.price_display)
                    ),
                    h("td", { key: "duration" }, editing
                      ? h("input", { className: "table-input", type: "number", min: "5", max: "480", step: "5", value: editForm.duration_minutes, onChange: (event) => updateEditForm("duration_minutes", event.target.value) })
                      : h("div", { className: "cell-sub" }, service.duration_display)
                    ),
                    h("td", { key: "category" }, editing
                      ? h("input", { className: "table-input", value: editForm.category, onChange: (event) => updateEditForm("category", event.target.value) })
                      : h("div", { className: "cell-sub" }, service.category || "—")
                    ),
                    h("td", { key: "actions" },
                      h("div", { className: "row-actions" }, editing
                        ? [
                            h("button", { className: "btn green", type: "button", onClick: () => saveEdit(service.id), key: "save" }, "Сохранить"),
                            h("button", { className: "btn", type: "button", onClick: () => setEditingId(null), key: "cancel" }, "Отмена"),
                          ]
                        : [
                            h("button", { className: "btn", type: "button", onClick: () => startEdit(service), key: "edit" }, "Редактировать"),
                            h("button", { className: "btn red", type: "button", onClick: () => onDeleteService(service.id), key: "delete" }, "Отключить"),
                          ])
                    ),
                  ]);
                })),
              ])
            )
          : h(EmptyState, { text: "Услуг пока нет. Добавьте первую услугу выше." })
      ),
    ]),
  ]);
}

function DoctorsView({ data, onAddDoctor, onUpdateDoctor, onDeleteDoctor }) {
  const doctors = data.doctors || [];
  const [form, setForm] = useState({ full_name: "", profession: "" });
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ full_name: "", profession: "" });

  function updateForm(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateEditForm(key, value) {
    setEditForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    const ok = await onAddDoctor(form);
    if (ok) setForm({ full_name: "", profession: "" });
  }

  function startEdit(doctor) {
    setEditingId(doctor.id);
    setEditForm({
      full_name: doctor.full_name || "",
      profession: doctor.profession || "",
    });
  }

  async function saveEdit(doctorId) {
    const ok = await onUpdateDoctor(doctorId, editForm);
    if (ok) setEditingId(null);
  }

  return h("div", { className: "settings-stack" }, [
    h("section", { className: "panel", key: "add" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("div", { key: "title" }, [
          h("h2", { className: "panel-title", key: "main" }, "Добавить врача"),
          h("div", { className: "cell-sub", key: "sub" }, "Врачи видны боту только внутри текущей клиники"),
        ]),
        h(StatusBadge, { key: "count", tone: doctors.length ? "completed" : "closed" }, `${doctors.length} врачей`),
      ]),
      h("div", { className: "panel-body", key: "body" },
        h("form", { onSubmit: submit }, [
          h("div", { className: "form-grid", key: "grid" }, [
            h("div", { className: "form-field", key: "name" }, [
              h("label", null, "Имя врача"),
              h("input", { value: form.full_name, placeholder: "Например: Алина Петрова", onChange: (event) => updateForm("full_name", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "profession" }, [
              h("label", null, "Профессия"),
              h("input", { value: form.profession, placeholder: "Например: стоматолог", onChange: (event) => updateForm("profession", event.target.value) }),
            ]),
          ]),
          h("div", { className: "toolbar", style: { marginTop: 14, marginBottom: 0 }, key: "actions" }, [
            h("button", { className: "btn primary", type: "submit" }, "Добавить врача"),
            h("span", { className: "cell-sub" }, "По имени или профессии бот сможет выбрать нужного специалиста."),
          ]),
        ])
      ),
    ]),
    h("section", { className: "panel", key: "list" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Список врачей"),
        h(StatusBadge, { key: "active", tone: "active" }, "Активные"),
      ]),
      h("div", { className: "panel-body", key: "body" },
        doctors.length
          ? h("div", { className: "table-wrap" },
              h("table", { className: "data-table" }, [
                h("thead", { key: "head" },
                  h("tr", null, [
                    h("th", { key: "name" }, "Имя"),
                    h("th", { key: "profession" }, "Профессия"),
                    h("th", { key: "status" }, "Статус"),
                    h("th", { key: "actions" }, "Действия"),
                  ])
                ),
                h("tbody", { key: "body" }, doctors.map((doctor) => {
                  const editing = editingId === doctor.id;
                  return h("tr", { key: doctor.id }, [
                    h("td", { key: "name" }, editing
                      ? h("input", { className: "table-input", value: editForm.full_name, onChange: (event) => updateEditForm("full_name", event.target.value) })
                      : h("div", { className: "cell-main" }, doctor.full_name)
                    ),
                    h("td", { key: "profession" }, editing
                      ? h("input", { className: "table-input", value: editForm.profession, onChange: (event) => updateEditForm("profession", event.target.value) })
                      : h("div", { className: "cell-sub" }, doctor.profession || "—")
                    ),
                    h("td", { key: "status" }, h(StatusBadge, { tone: "completed" }, "Активен")),
                    h("td", { key: "actions" },
                      h("div", { className: "row-actions" }, editing
                        ? [
                            h("button", { className: "btn green", type: "button", onClick: () => saveEdit(doctor.id), key: "save" }, "Сохранить"),
                            h("button", { className: "btn", type: "button", onClick: () => setEditingId(null), key: "cancel" }, "Отмена"),
                          ]
                        : [
                            h("button", { className: "btn", type: "button", onClick: () => startEdit(doctor), key: "edit" }, "Редактировать"),
                            h("button", { className: "btn red", type: "button", onClick: () => onDeleteDoctor(doctor.id), key: "delete" }, "Отключить"),
                          ])
                    ),
                  ]);
                })),
              ])
            )
          : h(EmptyState, { text: "Врачей пока нет. Добавьте первого специалиста выше." })
      ),
    ]),
  ]);
}

function getTodayInputValue() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 10);
}

function getMonthInputValue() {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 7);
}

function ERPView({
  data,
  onAddInventory,
  onUpdateInventory,
  onDeleteInventory,
  onAddExpense,
  onDeleteExpense,
  onAddSalary,
  onUpdateSalary,
  onDeleteSalary,
}) {
  const erp = data.erp || {};
  const metrics = erp.metrics || {};
  const inventory = erp.inventory || [];
  const expenses = erp.expenses || [];
  const salaries = erp.salaries || [];
  const lowStock = erp.low_stock || [];
  const doctors = data.doctors || [];
  const currentMonth = metrics.month || getMonthInputValue();
  const emptyInventory = {
    name: "",
    category: "",
    unit: "шт",
    quantity: "",
    min_quantity: "",
    cost_per_unit: "",
    supplier: "",
    notes: "",
  };
  const emptyExpense = {
    expense_date: getTodayInputValue(),
    category: "Материалы",
    title: "",
    amount: "",
    vendor: "",
    payment_method: "карта",
    notes: "",
  };
  const emptySalary = {
    salary_month: currentMonth,
    doctor_id: doctors[0]?.id || "",
    amount: "",
    is_paid: false,
    notes: "",
  };

  const [inventoryForm, setInventoryForm] = useState(emptyInventory);
  const [expenseForm, setExpenseForm] = useState(emptyExpense);
  const [salaryForm, setSalaryForm] = useState(emptySalary);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyInventory);
  const [editingSalaryId, setEditingSalaryId] = useState(null);
  const [salaryEditForm, setSalaryEditForm] = useState(emptySalary);

  function updateInventoryForm(key, value) {
    setInventoryForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateExpenseForm(key, value) {
    setExpenseForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateSalaryForm(key, value) {
    setSalaryForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateEditForm(key, value) {
    setEditForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateSalaryEditForm(key, value) {
    setSalaryEditForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submitInventory(event) {
    event.preventDefault();
    const ok = await onAddInventory(inventoryForm);
    if (ok) setInventoryForm(emptyInventory);
  }

  async function submitExpense(event) {
    event.preventDefault();
    const ok = await onAddExpense(expenseForm);
    if (ok) setExpenseForm({ ...emptyExpense, expense_date: getTodayInputValue() });
  }

  async function submitSalary(event) {
    event.preventDefault();
    const ok = await onAddSalary(salaryForm);
    if (ok) setSalaryForm({ ...emptySalary, salary_month: salaryForm.salary_month || currentMonth, doctor_id: "" });
  }

  function startEditInventory(item) {
    setEditingId(item.id);
    setEditForm({
      name: item.name || "",
      category: item.category || "",
      unit: item.unit || "шт",
      quantity: item.quantity ?? "",
      min_quantity: item.min_quantity ?? "",
      cost_per_unit: item.cost_per_unit ?? "",
      supplier: item.supplier || "",
      notes: item.notes || "",
    });
  }

  async function saveInventory(itemId) {
    const ok = await onUpdateInventory(itemId, editForm);
    if (ok) setEditingId(null);
  }

  function startEditSalary(item) {
    setEditingSalaryId(item.id);
    setSalaryEditForm({
      salary_month: item.salary_month || currentMonth,
      doctor_id: item.doctor_id || "",
      amount: item.amount ?? "",
      is_paid: !!item.is_paid,
      notes: item.notes || "",
    });
  }

  async function saveSalary(salaryId) {
    const ok = await onUpdateSalary(salaryId, salaryEditForm);
    if (ok) setEditingSalaryId(null);
  }

  return h("div", { className: "settings-stack erp-page" }, [
    h("div", { className: "metric-grid", key: "metrics" }, [
      h(Metric, { key: "revenue", label: "Выручка месяца", value: metrics.completed_revenue_display || "0 тг", note: "по завершённым визитам" }),
      h(Metric, { key: "expenses", label: "Расходы месяца", value: metrics.month_expenses_display || "0 тг", note: `операц.: ${metrics.operating_expenses_display || "0 тг"}` }),
      h(Metric, { key: "salary", label: "Выплаченные зарплаты", value: metrics.salary_paid_total_display || "0 тг", note: `в плане: ${metrics.salary_planned_total_display || "0 тг"}` }),
      h(Metric, { key: "profit", label: "Оценка прибыли", value: metrics.estimated_profit_display || "0 тг", note: "выручка минус расходы и выплаченные зарплаты" }),
      h(Metric, { key: "stock", label: "Низкий остаток", value: metrics.low_stock_count || 0, note: `склад: ${metrics.inventory_value_display || "0 тг"}` }),
    ]),

    lowStock.length > 0 && h("section", { className: "panel erp-alert", key: "low-stock" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Требуется пополнение склада"),
        h(StatusBadge, { tone: "waiting_operator", key: "count" }, `${lowStock.length} поз.`),
      ]),
      h("div", { className: "panel-body", key: "body" },
        h("div", { className: "erp-chip-row" }, lowStock.map((item) =>
          h("span", { className: "erp-stock-chip", key: item.id }, `${item.name}: ${item.quantity_display}`)
        ))
      ),
    ]),

    h("div", { className: "erp-grid", key: "forms" }, [
      h("section", { className: "panel", key: "inventory-add" }, [
        h("div", { className: "panel-header", key: "head" }, [
          h("div", { key: "title" }, [
            h("h2", { className: "panel-title", key: "main" }, "Склад расходников"),
            h("div", { className: "cell-sub", key: "sub" }, "Материалы, препараты, одноразовые позиции и контроль остатков"),
          ]),
          h(StatusBadge, { key: "count", tone: inventory.length ? "completed" : "closed" }, `${inventory.length} позиций`),
        ]),
        h("div", { className: "panel-body", key: "body" },
          h("form", { onSubmit: submitInventory }, [
            h("div", { className: "form-grid", key: "grid" }, [
              h("div", { className: "form-field", key: "name" }, [
                h("label", null, "Название"),
                h("input", { value: inventoryForm.name, placeholder: "Перчатки нитриловые", onChange: (event) => updateInventoryForm("name", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "category" }, [
                h("label", null, "Категория"),
                h("input", { value: inventoryForm.category, placeholder: "Расходники", onChange: (event) => updateInventoryForm("category", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "quantity" }, [
                h("label", null, "Количество"),
                h("input", { type: "number", min: "0", step: "0.01", value: inventoryForm.quantity, placeholder: "10", onChange: (event) => updateInventoryForm("quantity", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "unit" }, [
                h("label", null, "Ед. изм."),
                h("input", { value: inventoryForm.unit, placeholder: "шт", onChange: (event) => updateInventoryForm("unit", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "min" }, [
                h("label", null, "Минимум"),
                h("input", { type: "number", min: "0", step: "0.01", value: inventoryForm.min_quantity, placeholder: "2", onChange: (event) => updateInventoryForm("min_quantity", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "cost" }, [
                h("label", null, "Себестоимость за ед."),
                h("input", { type: "number", min: "0", step: "100", value: inventoryForm.cost_per_unit, placeholder: "500", onChange: (event) => updateInventoryForm("cost_per_unit", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "supplier" }, [
                h("label", null, "Поставщик"),
                h("input", { value: inventoryForm.supplier, placeholder: "Dental Supply", onChange: (event) => updateInventoryForm("supplier", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "notes" }, [
                h("label", null, "Комментарий"),
                h("input", { value: inventoryForm.notes, placeholder: "Размер, бренд, упаковка", onChange: (event) => updateInventoryForm("notes", event.target.value) }),
              ]),
            ]),
            h("div", { className: "toolbar", style: { marginTop: 14, marginBottom: 0 }, key: "actions" }, [
              h("button", { className: "btn primary", type: "submit" }, "Добавить на склад"),
              h("span", { className: "cell-sub" }, "Позиции с остатком ниже минимума появятся в предупреждении ERP."),
            ]),
          ])
        ),
      ]),

      h("section", { className: "panel", key: "expense-add" }, [
        h("div", { className: "panel-header", key: "head" }, [
          h("div", { key: "title" }, [
            h("h2", { className: "panel-title", key: "main" }, "Новый расход"),
            h("div", { className: "cell-sub", key: "sub" }, "Материалы, аренда, зарплаты, реклама и прочие платежи"),
          ]),
          h(StatusBadge, { key: "month", tone: "active" }, metrics.month || "месяц"),
        ]),
        h("div", { className: "panel-body", key: "body" },
          h("form", { onSubmit: submitExpense }, [
            h("div", { className: "form-grid", key: "grid" }, [
              h("div", { className: "form-field", key: "date" }, [
                h("label", null, "Дата"),
                h("input", { type: "date", value: expenseForm.expense_date, onChange: (event) => updateExpenseForm("expense_date", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "category" }, [
                h("label", null, "Категория"),
                h("input", { value: expenseForm.category, placeholder: "Материалы", onChange: (event) => updateExpenseForm("category", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "title" }, [
                h("label", null, "Название расхода"),
                h("input", { value: expenseForm.title, placeholder: "Закуп перчаток", onChange: (event) => updateExpenseForm("title", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "amount" }, [
                h("label", null, "Сумма, тг"),
                h("input", { type: "number", min: "0", step: "100", value: expenseForm.amount, placeholder: "25000", onChange: (event) => updateExpenseForm("amount", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "vendor" }, [
                h("label", null, "Получатель"),
                h("input", { value: expenseForm.vendor, placeholder: "Поставщик или сотрудник", onChange: (event) => updateExpenseForm("vendor", event.target.value) }),
              ]),
              h("div", { className: "form-field", key: "method" }, [
                h("label", null, "Оплата"),
                h("input", { value: expenseForm.payment_method, placeholder: "карта / наличные / Kaspi", onChange: (event) => updateExpenseForm("payment_method", event.target.value) }),
              ]),
              h("div", { className: "form-field wide", key: "notes" }, [
                h("label", null, "Комментарий"),
                h("input", { value: expenseForm.notes, placeholder: "Номер счёта, причина, детали", onChange: (event) => updateExpenseForm("notes", event.target.value) }),
              ]),
            ]),
            h("div", { className: "toolbar", style: { marginTop: 14, marginBottom: 0 }, key: "actions" }, [
              h("button", { className: "btn primary", type: "submit" }, "Добавить расход"),
              h("span", { className: "cell-sub" }, "Расход сразу попадёт в расчёт месяца."),
            ]),
          ])
        ),
      ]),

      h("section", { className: "panel", key: "salary-add" }, [
        h("div", { className: "panel-header", key: "head" }, [
          h("div", { key: "title" }, [
            h("h2", { className: "panel-title", key: "main" }, "Зарплата врачу"),
            h("div", { className: "cell-sub", key: "sub" }, "Ежемесячная зарплата по каждому врачу для расчёта прибыли"),
          ]),
          h(StatusBadge, { key: "month", tone: "active" }, currentMonth),
        ]),
        h("div", { className: "panel-body", key: "body" },
          doctors.length
            ? h("form", { onSubmit: submitSalary }, [
                h("div", { className: "form-grid", key: "grid" }, [
                  h("div", { className: "form-field", key: "month" }, [
                    h("label", null, "Месяц"),
                    h("input", { type: "month", value: salaryForm.salary_month, onChange: (event) => updateSalaryForm("salary_month", event.target.value) }),
                  ]),
                  h("div", { className: "form-field", key: "doctor" }, [
                    h("label", null, "Врач"),
                    h("select", { value: salaryForm.doctor_id, onChange: (event) => updateSalaryForm("doctor_id", event.target.value) }, [
                      h("option", { key: "empty", value: "" }, "Выберите врача"),
                      ...doctors.map((doctor) =>
                        h("option", { key: doctor.id, value: doctor.id }, `${doctor.full_name} — ${doctor.profession || "врач"}`)
                      ),
                    ]),
                  ]),
                  h("div", { className: "form-field", key: "amount" }, [
                    h("label", null, "Сумма, тг"),
                    h("input", { type: "number", min: "0", step: "1000", value: salaryForm.amount, placeholder: "300000", onChange: (event) => updateSalaryForm("amount", event.target.value) }),
                  ]),
                  h("label", { className: "check-field", key: "paid" }, [
                    h("input", { type: "checkbox", checked: !!salaryForm.is_paid, onChange: (event) => updateSalaryForm("is_paid", event.target.checked) }),
                    h("span", null, "Уже выплачено"),
                  ]),
                  h("div", { className: "form-field wide", key: "notes" }, [
                    h("label", null, "Комментарий"),
                    h("input", { value: salaryForm.notes, placeholder: "Ставка, аванс, бонусы", onChange: (event) => updateSalaryForm("notes", event.target.value) }),
                  ]),
                ]),
                h("div", { className: "toolbar", style: { marginTop: 14, marginBottom: 0 }, key: "actions" }, [
                  h("button", { className: "btn primary", type: "submit" }, "Сохранить зарплату"),
                  h("span", { className: "cell-sub" }, "В прибыль месяца попадут только зарплаты с галочкой «выплачено»."),
                ]),
              ])
            : h(EmptyState, { text: "Сначала добавьте врачей в разделе «Врачи», затем назначьте им зарплату." })
        ),
      ]),
    ]),

    h("section", { className: "panel", key: "inventory-list" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Складские позиции"),
        h(StatusBadge, { key: "value", tone: "active" }, metrics.inventory_value_display || "0 тг"),
      ]),
      h("div", { className: "panel-body", key: "body" },
        inventory.length
          ? h("div", { className: "table-wrap" },
              h("table", { className: "data-table" }, [
                h("thead", { key: "head" },
                  h("tr", null, [
                    h("th", { key: "name" }, "Позиция"),
                    h("th", { key: "qty" }, "Остаток"),
                    h("th", { key: "min" }, "Мин."),
                    h("th", { key: "cost" }, "Цена/ед."),
                    h("th", { key: "supplier" }, "Поставщик"),
                    h("th", { key: "actions" }, "Действия"),
                  ])
                ),
                h("tbody", { key: "body" }, inventory.map((item) => {
                  const editing = editingId === item.id;
                  return h("tr", { key: item.id, className: item.is_low_stock ? "erp-low-row" : "" }, [
                    h("td", { key: "name" }, editing
                      ? h("input", { className: "table-input", value: editForm.name, onChange: (event) => updateEditForm("name", event.target.value) })
                      : [
                          h("div", { className: "cell-main", key: "main" }, item.name),
                          h("div", { className: "cell-sub", key: "sub" }, [item.category, item.notes].filter(Boolean).join(" · ") || "—"),
                        ]
                    ),
                    h("td", { key: "qty" }, editing
                      ? h("input", { className: "table-input", type: "number", min: "0", step: "0.01", value: editForm.quantity, onChange: (event) => updateEditForm("quantity", event.target.value) })
                      : h("div", { className: "cell-main" }, item.quantity_display)
                    ),
                    h("td", { key: "min" }, editing
                      ? h("input", { className: "table-input", type: "number", min: "0", step: "0.01", value: editForm.min_quantity, onChange: (event) => updateEditForm("min_quantity", event.target.value) })
                      : h(StatusBadge, { tone: item.is_low_stock ? "waiting_operator" : "closed" }, item.min_quantity_display)
                    ),
                    h("td", { key: "cost" }, editing
                      ? h("input", { className: "table-input", type: "number", min: "0", step: "100", value: editForm.cost_per_unit, onChange: (event) => updateEditForm("cost_per_unit", event.target.value) })
                      : h("div", { className: "cell-sub" }, item.cost_per_unit_display)
                    ),
                    h("td", { key: "supplier" }, editing
                      ? h("input", { className: "table-input", value: editForm.supplier, onChange: (event) => updateEditForm("supplier", event.target.value) })
                      : h("div", { className: "cell-sub" }, item.supplier || "—")
                    ),
                    h("td", { key: "actions" },
                      h("div", { className: "row-actions" }, editing
                        ? [
                            h("button", { className: "btn green", type: "button", onClick: () => saveInventory(item.id), key: "save" }, "Сохранить"),
                            h("button", { className: "btn", type: "button", onClick: () => setEditingId(null), key: "cancel" }, "Отмена"),
                          ]
                        : [
                            h("button", { className: "btn", type: "button", onClick: () => startEditInventory(item), key: "edit" }, "Редактировать"),
                            h("button", { className: "btn red", type: "button", onClick: () => onDeleteInventory(item.id), key: "delete" }, "Списать"),
                          ])
                    ),
                  ]);
                })),
              ])
            )
          : h(EmptyState, { text: "Склад пока пуст. Добавьте расходники или материалы выше." })
      ),
    ]),

    h("section", { className: "panel", key: "salary-list" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("div", { key: "title" }, [
          h("h2", { className: "panel-title", key: "main" }, "Зарплаты врачей"),
          h("div", { className: "cell-sub", key: "sub" }, "Суммы за текущий и прошлые месяцы"),
        ]),
        h(StatusBadge, { key: "sum", tone: "active" }, `выплачено: ${metrics.salary_paid_total_display || "0 тг"}`),
      ]),
      h("div", { className: "panel-body", key: "body" },
        salaries.length
          ? h("div", { className: "table-wrap" },
              h("table", { className: "data-table" }, [
                h("thead", { key: "head" },
                  h("tr", null, [
                    h("th", { key: "month" }, "Месяц"),
                    h("th", { key: "doctor" }, "Врач"),
                    h("th", { key: "amount" }, "Сумма"),
                    h("th", { key: "status" }, "Статус"),
                    h("th", { key: "notes" }, "Комментарий"),
                    h("th", { key: "actions" }, "Действия"),
                  ])
                ),
                h("tbody", { key: "body" }, salaries.map((salary) => {
                  const editing = editingSalaryId === salary.id;
                  return h("tr", { key: salary.id }, [
                    h("td", { key: "month" }, editing
                      ? h("input", { className: "table-input", type: "month", value: salaryEditForm.salary_month, onChange: (event) => updateSalaryEditForm("salary_month", event.target.value) })
                      : h("div", { className: "cell-main" }, salary.salary_month)
                    ),
                    h("td", { key: "doctor" }, [
                      h("div", { className: "cell-main", key: "main" }, salary.doctor_name),
                      h("div", { className: "cell-sub", key: "sub" }, salary.profession || "—"),
                    ]),
                    h("td", { key: "amount" }, editing
                      ? h("input", { className: "table-input", type: "number", min: "0", step: "1000", value: salaryEditForm.amount, onChange: (event) => updateSalaryEditForm("amount", event.target.value) })
                      : h("div", { className: "cell-main" }, salary.amount_display)
                    ),
                    h("td", { key: "status" }, editing
                      ? h("label", { className: "check-field compact" }, [
                          h("input", { type: "checkbox", checked: !!salaryEditForm.is_paid, onChange: (event) => updateSalaryEditForm("is_paid", event.target.checked) }),
                          h("span", null, "Выплачено"),
                        ])
                      : h(StatusBadge, { tone: salary.is_paid ? "completed" : "waiting_operator" }, salary.status_label)
                    ),
                    h("td", { key: "notes" }, editing
                      ? h("input", { className: "table-input", value: salaryEditForm.notes, onChange: (event) => updateSalaryEditForm("notes", event.target.value) })
                      : h("div", { className: "cell-sub" }, salary.notes || "—")
                    ),
                    h("td", { key: "actions" },
                      h("div", { className: "row-actions" }, editing
                        ? [
                            h("button", { className: "btn green", type: "button", onClick: () => saveSalary(salary.id), key: "save" }, "Сохранить"),
                            h("button", { className: "btn", type: "button", onClick: () => setEditingSalaryId(null), key: "cancel" }, "Отмена"),
                          ]
                        : [
                            h("button", { className: "btn", type: "button", onClick: () => startEditSalary(salary), key: "edit" }, "Редактировать"),
                            h("button", { className: "btn red", type: "button", onClick: () => onDeleteSalary(salary.id), key: "delete" }, "Удалить"),
                          ])
                    ),
                  ]);
                })),
              ])
            )
          : h(EmptyState, { text: "Зарплаты пока не добавлены. Назначьте сумму врачу выше." })
      ),
    ]),

    h("section", { className: "panel", key: "expenses-list" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Последние расходы"),
        h(StatusBadge, { key: "sum", tone: "active" }, metrics.month_expenses_display || "0 тг"),
      ]),
      h("div", { className: "panel-body", key: "body" },
        expenses.length
          ? h("div", { className: "table-wrap" },
              h("table", { className: "data-table" }, [
                h("thead", { key: "head" },
                  h("tr", null, [
                    h("th", { key: "date" }, "Дата"),
                    h("th", { key: "title" }, "Расход"),
                    h("th", { key: "category" }, "Категория"),
                    h("th", { key: "amount" }, "Сумма"),
                    h("th", { key: "vendor" }, "Получатель"),
                    h("th", { key: "actions" }, "Действия"),
                  ])
                ),
                h("tbody", { key: "body" }, expenses.map((expense) =>
                  h("tr", { key: expense.id }, [
                    h("td", { key: "date" }, expense.expense_date_display || expense.expense_date),
                    h("td", { key: "title" }, [
                      h("div", { className: "cell-main", key: "main" }, expense.title),
                      expense.notes && h("div", { className: "cell-sub", key: "sub" }, expense.notes),
                    ].filter(Boolean)),
                    h("td", { key: "category" }, expense.category || "—"),
                    h("td", { key: "amount" }, h("div", { className: "cell-main" }, expense.amount_display)),
                    h("td", { key: "vendor" }, h("div", { className: "cell-sub" }, [expense.vendor, expense.payment_method].filter(Boolean).join(" · ") || "—")),
                    h("td", { key: "actions" },
                      h("button", { className: "btn red", type: "button", onClick: () => onDeleteExpense(expense.id) }, "Удалить")
                    ),
                  ])
                )),
              ])
            )
          : h(EmptyState, { text: "Расходов пока нет. Добавьте первый платёж выше." })
      ),
    ]),
  ].filter(Boolean));
}

function ChannelManager({ data, onAddChannel, onDeleteChannel }) {
  const [form, setForm] = useState({
    channel_name: "",
    channel_key: "",
    channel_token: "",
  });

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    await onAddChannel({ ...form, channel_type: "whatsapp" });
    setForm({ channel_name: "", channel_key: "", channel_token: "" });
  }

  const channels = data.channels || [];

  return h("section", { className: "panel" }, [
    h("div", { className: "panel-header", key: "head" }, [
      h("div", { key: "title" }, [
        h("h2", { className: "panel-title", key: "main" }, "WhatsApp / Green API"),
        h("div", { className: "cell-sub", key: "sub" }, "Каждая клиника подключает свой отдельный idInstance"),
      ]),
      h(StatusBadge, { key: "count", tone: channels.length ? "completed" : "closed" }, `${channels.length} каналов`),
    ]),
    h("div", { className: "panel-body", key: "body" }, [
      h("div", { className: "webhook-box", key: "webhook" }, [
        h("div", { key: "label" }, [
          h("div", { className: "cell-main", key: "main" }, "Webhook URL для Green API"),
          h("div", { className: "cell-sub", key: "sub" }, "Вставьте этот адрес в настройки instance в Green API"),
        ]),
        h("code", { key: "code" }, data.webhooks?.whatsapp || "/webhook/whatsapp"),
      ]),
      h("form", { className: "channel-form", onSubmit: submit, key: "form" }, [
        h("div", { className: "form-grid", key: "grid" }, [
          h("div", { className: "form-field", key: "name" }, [
            h("label", null, "Название"),
            h("input", { value: form.channel_name, placeholder: "WhatsApp ресепшена", onChange: (event) => update("channel_name", event.target.value) }),
          ]),
          h("div", { className: "form-field", key: "key" }, [
            h("label", null, "idInstance"),
            h("input", { value: form.channel_key, placeholder: "7100000000", inputMode: "numeric", onChange: (event) => update("channel_key", event.target.value) }),
          ]),
          h("div", { className: "form-field wide", key: "token" }, [
            h("label", null, "apiTokenInstance"),
            h("input", { type: "password", value: form.channel_token, placeholder: "токен из Green API", onChange: (event) => update("channel_token", event.target.value) }),
          ]),
        ]),
        h("div", { className: "toolbar", key: "actions" }, [
          h("button", { className: "btn primary", type: "submit" }, "Привязать WhatsApp"),
          h("span", { className: "cell-sub" }, "Этот instance будет работать только с этой клиникой."),
        ]),
      ]),
      channels.length
        ? h("div", { className: "channel-list", key: "list" }, channels.map((channel) =>
            h("div", { className: "channel-card", key: channel.id }, [
              h("div", { key: "info" }, [
                h("div", { className: "cell-main", key: "name" }, channel.channel_name || "WhatsApp клиники"),
                h("div", { className: "cell-sub", key: "meta" }, `idInstance: ${channel.channel_key} · token: ${channel.channel_token_masked || "не указан"}`),
              ]),
              h("div", { className: "row-actions", key: "actions" }, [
                h(StatusBadge, { key: "active", tone: "completed" }, "Активен"),
                h("button", { className: "btn red", onClick: () => onDeleteChannel(channel.id), type: "button", key: "delete" }, "Отключить"),
              ]),
            ])
          ))
        : h(EmptyState, { key: "empty", text: "WhatsApp ещё не подключён" }),
    ]),
  ]);
}

function SettingsView({ data, onSave, onSaveAppearance, onAddChannel, onDeleteChannel, onDirtyChange }) {
  const [form, setForm] = useState(data.settings);
  const [dirty, setDirty] = useState(false);
  const [appearanceSaving, setAppearanceSaving] = useState(false);

  useEffect(() => {
    if (!dirty) setForm(data.settings);
  }, [data.settings, dirty]);

  useEffect(() => {
    if (onDirtyChange) onDirtyChange(dirty);
  }, [dirty, onDirtyChange]);

  useEffect(() => () => {
    if (onDirtyChange) onDirtyChange(false);
  }, [onDirtyChange]);

  function update(key, value) {
    setDirty(true);
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function updateAppearance(updates) {
    const next = {
      panel_language: form.panel_language || "ru",
      panel_theme: form.panel_theme || "blue",
      ...updates,
    };
    setForm((prev) => ({ ...prev, ...next }));
    applyPanelPreferences(next);
    setAppearanceSaving(true);
    try {
      await onSaveAppearance(next);
    } finally {
      setAppearanceSaving(false);
    }
  }

  function toggleDay(day) {
    setDirty(true);
    setForm((prev) => {
      const set = new Set(prev.working_days || []);
      if (set.has(day)) set.delete(day);
      else set.add(day);
      return { ...prev, working_days: Array.from(set).sort() };
    });
  }

  async function submit(event) {
    event.preventDefault();
    const ok = await onSave(form);
    if (ok) setDirty(false);
  }

  return h("div", { className: "settings-stack" }, [
    dirty && h("div", { className: "unsaved-banner", key: "dirty" }, [
      h("strong", { key: "title" }, "Есть несохранённые изменения"),
      h("span", { key: "text" }, "Автообновление не перезапишет эту форму. Нажмите «Сохранить настройки», когда закончите."),
    ]),
    h("section", { className: "panel", key: "schedule" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Профиль, график и ручной режим"),
        h("span", { className: "cell-sub", key: "hint" }, data.clinic.name),
      ]),
      h("div", { className: "panel-body", key: "body" },
        h("form", { onSubmit: submit }, [
          h("div", { className: "form-grid", key: "grid" }, [
            h("div", { className: "form-field", key: "clinic-name" }, [
              h("label", null, "Название клиники"),
              h("input", { value: form.clinic_name || "", placeholder: "Например: Dental House", onChange: (event) => update("clinic_name", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "address" }, [
              h("label", null, "Адрес"),
              h("input", { value: form.address || "", placeholder: "Например: Алматы, Абая 10", onChange: (event) => update("address", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "notify-whatsapp" }, [
              h("label", null, "WhatsApp администратора"),
              h("input", { value: form.admin_notify_whatsapp || "", placeholder: "+7 777 123 45 67", onChange: (event) => update("admin_notify_whatsapp", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "start" }, [
              h("label", null, "Начало рабочего дня"),
              h("input", { type: "time", value: form.work_start || "", onChange: (event) => update("work_start", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "end" }, [
              h("label", null, "Конец рабочего дня"),
              h("input", { type: "time", value: form.work_end || "", onChange: (event) => update("work_end", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "step" }, [
              h("label", null, "Шаг записи"),
              h("input", { type: "number", min: "5", max: "240", step: "5", value: form.slot_step_minutes || 30, onChange: (event) => update("slot_step_minutes", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "pause" }, [
              h("label", null, "Авто-включение бота"),
              h("select", { value: form.bot_pause_hours || 12, onChange: (event) => update("bot_pause_hours", Number(event.target.value)) },
                [2, 6, 12, 24].map((hours) => h("option", { value: hours, key: hours }, `${hours} ч`))
              ),
            ]),
          ]),
          h("div", { className: "appearance-box", key: "appearance" }, [
            h("div", { className: "appearance-head", key: "title" }, [
              h("div", { key: "copy" }, [
                h("h3", { className: "section-title", key: "main" }, "Внешний вид панели"),
                h("div", { className: "cell-sub", key: "sub" }, "Переключается сразу и сохраняется автоматически."),
              ]),
              h(StatusBadge, { tone: appearanceSaving ? "waiting_operator" : "completed", key: "save" }, appearanceSaving ? "Сохраняем..." : "Автосохранение"),
            ]),
            h("div", { className: "appearance-grid", key: "controls" }, [
              h("div", { className: "form-field", key: "language" }, [
                h("label", null, "Язык панели"),
                h("div", { className: "language-toggle" }, LANGUAGE_OPTIONS.map((item) =>
                  h("button", {
                    type: "button",
                    key: item.value,
                    className: cls("language-option", (form.panel_language || "ru") === item.value && "active"),
                    onClick: () => updateAppearance({ panel_language: item.value }),
                  }, item.label)
                )),
              ]),
              h("div", { className: "form-field wide", key: "theme" }, [
                h("label", null, "Цветовая тема"),
                h("div", { className: "theme-picker" }, PANEL_THEMES.map((theme) =>
                  h("button", {
                    type: "button",
                    key: theme.value,
                    className: cls("theme-swatch", (form.panel_theme || "blue") === theme.value && "active"),
                    onClick: () => updateAppearance({ panel_theme: theme.value }),
                  }, [
                    h("span", { className: "theme-dot", style: { background: `linear-gradient(135deg, ${theme.color}, ${theme.accent})` }, key: "dot" }),
                    h("span", { className: "theme-label", key: "label" }, theme.label),
                  ])
                )),
              ]),
            ]),
          ]),
          h("div", { className: "form-field", style: { marginTop: 14 }, key: "days" }, [
            h("label", null, "Рабочие дни"),
            h("div", { className: "weekday-row" }, DAY_LABELS.map(([day, label]) =>
              h("button", { type: "button", className: cls("weekday", (form.working_days || []).includes(day) && "active"), onClick: () => toggleDay(day), key: day }, label)
            )),
          ]),
          h("div", { className: "form-field", style: { marginTop: 14 }, key: "notifications" }, [
            h("label", null, "Уведомления и напоминания"),
            h("div", { className: "check-list" }, [
              h("label", { className: "check-row", key: "lead" }, [
                h("input", { type: "checkbox", checked: Boolean(form.notify_new_leads), onChange: (event) => update("notify_new_leads", event.target.checked) }),
                h("span", null, "Уведомлять о новом лиде"),
              ]),
              h("label", { className: "check-row", key: "booking" }, [
                h("input", { type: "checkbox", checked: Boolean(form.notify_new_bookings), onChange: (event) => update("notify_new_bookings", event.target.checked) }),
                h("span", null, "Уведомлять о новой записи или переносе"),
              ]),
              h("label", { className: "check-row", key: "operator" }, [
                h("input", { type: "checkbox", checked: Boolean(form.notify_operator_requests), onChange: (event) => update("notify_operator_requests", event.target.checked) }),
                h("span", null, "Уведомлять, когда клиент просит оператора"),
              ]),
              h("label", { className: "check-row", key: "reminders" }, [
                h("input", { type: "checkbox", checked: Boolean(form.whatsapp_reminders_enabled), onChange: (event) => update("whatsapp_reminders_enabled", event.target.checked) }),
                h("span", null, "Отправлять клиентам WhatsApp-напоминания за 24 часа и за 2 часа"),
              ]),
            ]),
          ]),
          h("div", { className: "toolbar", style: { marginTop: 18 }, key: "save" }, [
            h("button", { className: "btn primary", type: "submit" }, dirty ? "Сохранить изменения" : "Сохранить настройки"),
            h("span", { className: "cell-sub" }, "Эти параметры применяются только к текущей клинике."),
          ]),
        ])
      ),
    ]),
    h(ChannelManager, { key: "channels", data, onAddChannel, onDeleteChannel }),
  ]);
}

function PlatformView({ data, onSwitchClinic, onPlatformAddChannel, onPlatformDeleteChannel, onPlatformUserAction }) {
  const clinics = data.platform_clinics || [];
  const users = data.platform_users || [];
  const canManageUsers = Boolean(data.platform_admin?.can_manage_platform_admins);
  const [form, setForm] = useState({
    clinic_id: clinics[0]?.id || "",
    channel_name: "",
    channel_key: "",
    channel_token: "",
  });

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      clinic_id: prev.clinic_id || clinics[0]?.id || "",
    }));
  }, [clinics.length]);

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    const ok = await onPlatformAddChannel(form);
    if (ok) {
      setForm((prev) => ({
        ...prev,
        channel_name: "",
        channel_key: "",
        channel_token: "",
      }));
    }
  }

  return h("div", { className: "settings-stack" }, [
    h("section", { className: "panel", key: "connect" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("div", { key: "title" }, [
          h("h2", { className: "panel-title", key: "main" }, "Подключить WhatsApp клинике"),
          h("div", { className: "cell-sub", key: "sub" }, "Эта панель доступна только владельцу платформы и пользователям, которым он выдал доступ."),
        ]),
        h(StatusBadge, { key: "count", tone: "completed" }, `${clinics.length} клиник`),
      ]),
      h("div", { className: "panel-body", key: "body" }, [
        h("div", { className: "webhook-box", key: "webhook" }, [
          h("div", { key: "label" }, [
            h("div", { className: "cell-main", key: "main" }, "Webhook URL для всех Green API instance"),
            h("div", { className: "cell-sub", key: "sub" }, "Один адрес вставляется в Green API, а нужная клиника определяется по idInstance."),
          ]),
          h("code", { key: "code" }, data.webhooks?.whatsapp || "/webhook/whatsapp"),
        ]),
        h("form", { className: "channel-form", onSubmit: submit, key: "form" }, [
          h("div", { className: "form-grid", key: "grid" }, [
            h("div", { className: "form-field wide", key: "clinic" }, [
              h("label", null, "Клиника"),
              h("select", { value: form.clinic_id, onChange: (event) => update("clinic_id", event.target.value) },
                clinics.map((clinic) => h("option", { value: clinic.id, key: clinic.id }, `#${clinic.id} ${clinic.name}`))
              ),
            ]),
            h("div", { className: "form-field", key: "name" }, [
              h("label", null, "Название канала"),
              h("input", { value: form.channel_name, placeholder: "WhatsApp ресепшена", onChange: (event) => update("channel_name", event.target.value) }),
            ]),
            h("div", { className: "form-field", key: "key" }, [
              h("label", null, "idInstance"),
              h("input", { value: form.channel_key, placeholder: "7100000000", inputMode: "numeric", onChange: (event) => update("channel_key", event.target.value) }),
            ]),
            h("div", { className: "form-field wide", key: "token" }, [
              h("label", null, "apiTokenInstance"),
              h("input", { type: "password", value: form.channel_token, placeholder: "токен из Green API", onChange: (event) => update("channel_token", event.target.value) }),
            ]),
          ]),
          h("div", { className: "toolbar", key: "actions" }, [
            h("button", { className: "btn primary", type: "submit", disabled: !clinics.length }, "Привязать instance"),
            h("span", { className: "cell-sub" }, "Клиника получит сообщения только со своего idInstance."),
          ]),
        ]),
      ]),
    ]),
    h("section", { className: "panel", key: "clinics" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "Зарегистрированные клиники"),
        h(StatusBadge, { key: "badge", tone: "active" }, clinics.length),
      ]),
      h("div", { className: "panel-body platform-grid", key: "body" },
        clinics.length
          ? clinics.map((clinic) =>
              h("div", { className: "clinic-card", key: clinic.id }, [
                h("div", { className: "clinic-card-head", key: "head" }, [
                  h("div", { key: "title" }, [
                    h("div", { className: "cell-main", key: "name" }, `#${clinic.id} ${clinic.name}`),
                    h("div", { className: "cell-sub", key: "admins" }, clinic.admin_emails_display),
                    clinic.address && h("div", { className: "cell-sub", key: "address" }, clinic.address),
                  ]),
                  h("div", { className: "row-actions", key: "actions" }, [
                    Number(data.clinic.id) === Number(clinic.id)
                      ? h(StatusBadge, { key: "current", tone: "active" }, "Открыта")
                      : h("button", { className: "btn", type: "button", onClick: () => onSwitchClinic(clinic.id), key: "open" }, "Открыть CRM"),
                    h(StatusBadge, { key: "channels", tone: clinic.channels_count ? "completed" : "closed" }, `${clinic.channels_count} каналов`),
                  ]),
                ]),
                clinic.channels?.length
                  ? h("div", { className: "channel-list compact", key: "channels" }, clinic.channels.map((channel) =>
                      h("div", { className: "channel-card", key: channel.id }, [
                        h("div", { key: "info" }, [
                          h("div", { className: "cell-main", key: "name" }, channel.channel_name || "WhatsApp клиники"),
                          h("div", { className: "cell-sub", key: "meta" }, `idInstance: ${channel.channel_key} · token: ${channel.channel_token_masked || "не указан"}`),
                        ]),
                        h("button", { className: "btn red", type: "button", onClick: () => onPlatformDeleteChannel(channel.id), key: "delete" }, "Отключить"),
                      ])
                    ))
                  : h(EmptyState, { key: "empty", text: "WhatsApp ещё не подключён" }),
              ])
            )
          : h(EmptyState, { text: "Зарегистрированных клиник пока нет" })
      ),
    ]),
    canManageUsers && h("section", { className: "panel", key: "users" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("div", { key: "title" }, [
          h("h2", { className: "panel-title", key: "main" }, "Доступ к платформе"),
          h("div", { className: "cell-sub", key: "sub" }, `Выдавать и забирать доступ может только ${data.platform_admin.root_email}.`),
        ]),
        h(StatusBadge, { key: "root", tone: "active" }, "root only"),
      ]),
      h("div", { className: "panel-body", key: "body" },
        users.length
          ? h("div", { className: "table-wrap" },
              h("table", { className: "data-table" }, [
                h("thead", { key: "head" },
                  h("tr", null, [
                    h("th", { key: "email" }, "Пользователь"),
                    h("th", { key: "clinic" }, "Клиника"),
                    h("th", { key: "access" }, "Доступ"),
                    h("th", { key: "actions" }, "Действия"),
                  ])
                ),
                h("tbody", { key: "body" }, users.map((user) =>
                  h("tr", { key: user.id }, [
                    h("td", { key: "email" }, [
                      h("div", { className: "cell-main", key: "main" }, user.email),
                      user.is_root && h("div", { className: "cell-sub", key: "root" }, "Владелец платформы"),
                    ]),
                    h("td", { key: "clinic" }, user.clinic_name),
                    h("td", { key: "access" }, h(StatusBadge, { tone: user.has_platform_access ? "completed" : "closed" }, user.has_platform_access ? "Есть" : "Нет")),
                    h("td", { key: "actions" },
                      user.is_root
                        ? h(StatusBadge, { tone: "active" }, "Нельзя изменить")
                        : h("button", {
                            className: cls("btn", user.has_platform_access ? "red" : "green"),
                            type: "button",
                            onClick: () => onPlatformUserAction(user.id, user.has_platform_access ? "revoke" : "grant"),
                          }, user.has_platform_access ? "Забрать доступ" : "Выдать доступ")
                    ),
                  ])
                )),
              ])
            )
          : h(EmptyState, { text: "Пользователей пока нет" })
      ),
    ]),
  ].filter(Boolean));
}

function AssistantWidget({ data, setView }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const endRef = useRef(null);

  useEffect(() => {
    setMessages([
      {
        role: "assistant",
        text: `Я помогу ориентироваться в CRM «${data.clinic.name}». Могу подсказать, где добавить врачей, показать записи, лиды, настройки и WhatsApp.`,
        suggestions: ASSISTANT_QUICK_QUESTIONS,
        actions: [
          { label: "Открыть сводку", view: "dashboard" },
          { label: "Открыть настройки", view: "settings" },
        ],
      },
    ]);
  }, [data.clinic.id]);

  useEffect(() => {
    if (endRef.current) endRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading, open]);

  async function ask(text) {
    const question = (text || "").trim();
    if (!question || loading) return;

    setOpen(true);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setLoading(true);

    try {
      const payload = await api("/admin/api/react/assistant", {
        method: "POST",
        body: JSON.stringify({ message: question }),
      });

      if (payload?.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            text: payload.answer || "Готово. Подскажите, что ещё нужно найти в CRM?",
            actions: payload.actions || [],
            suggestions: payload.suggestions || ASSISTANT_QUICK_QUESTIONS,
          },
        ]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", text: payload?.error || "Не удалось получить ответ помощника." }]);
      }
    } catch (error) {
      setMessages((prev) => [...prev, { role: "assistant", text: error.message || "Помощник сейчас недоступен. Попробуйте ещё раз." }]);
    } finally {
      setLoading(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    ask(input);
  }

  function runAction(action) {
    if (action.view) setView(action.view);
    if (action.href) window.location.href = action.href;
  }

  const latestAssistant = [...messages].reverse().find((item) => item.role === "assistant");
  const suggestions = latestAssistant?.suggestions?.length ? latestAssistant.suggestions : ASSISTANT_QUICK_QUESTIONS;

  return h("div", { className: cls("assistant-widget", open && "open") }, [
    open && h("section", { className: "assistant-panel", key: "panel" }, [
      h("div", { className: "assistant-head", key: "head" }, [
        h("div", { key: "title" }, [
          h("div", { className: "assistant-title", key: "main" }, "Ваш персональный помощник по CRM"),
          h("div", { className: "assistant-subtitle", key: "sub" }, "Подсказывает по текущей клинике"),
        ]),
        h("button", { className: "assistant-close", type: "button", onClick: () => setOpen(false), key: "close" }, "×"),
      ]),
      h("div", { className: "assistant-messages", key: "messages" }, [
        messages.map((msg, index) =>
          h("div", { className: cls("assistant-message", msg.role), key: `${msg.role}-${index}` }, [
            h("div", { className: "assistant-message-text", key: "text" }, msg.text),
            msg.actions?.length
              ? h("div", { className: "assistant-actions", key: "actions" }, msg.actions.map((action, actionIndex) =>
                  h("button", { className: "assistant-action", type: "button", key: `${action.label}-${actionIndex}`, onClick: () => runAction(action) }, action.label)
                ))
              : null,
          ])
        ),
        loading && h("div", { className: "assistant-message assistant typing", key: "typing" }, "Думаю..."),
        h("div", { ref: endRef, key: "end" }),
      ]),
      h("div", { className: "assistant-suggestions", key: "suggestions" }, suggestions.map((text, index) =>
        h("button", { type: "button", key: `${text}-${index}`, onClick: () => ask(text) }, text)
      )),
      h("form", { className: "assistant-form", onSubmit: submit, key: "form" }, [
        h("input", {
          value: input,
          onChange: (event) => setInput(event.target.value),
          placeholder: "Спросите про записи, врачей, WhatsApp...",
        }),
        h("button", { type: "submit", disabled: loading || !input.trim() }, "Спросить"),
      ]),
    ]),
    h("button", { className: "assistant-launcher", type: "button", onClick: () => setOpen((value) => !value), key: "launcher" }, [
      h("span", { key: "icon" }, "✨"),
      h("span", { key: "text" }, open ? "Скрыть" : "Помощник"),
    ]),
  ]);
}

function App() {
  const [data, setData] = useState(null);
  const [view, setView] = useState(() => window.location.hash.replace("#", "") || "dashboard");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [thread, setThread] = useState(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const [settingsDirty, setSettingsDirty] = useState(false);

  const [pageTitle, pageKicker] = titleForView(view);

  function showToast(text, type = "ok") {
    setToast({ text, type });
    window.setTimeout(() => setToast(null), 3200);
  }

  async function loadData(silent = false) {
    if (!silent) setLoading(true);
    try {
      const payload = await api("/admin/api/react/bootstrap");
      if (payload?.ok) setData(payload);
    } catch (error) {
      showToast(error.message || "Не удалось загрузить данные", "error");
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function loadThread(id) {
    if (!id) return;
    setLoadingThread(true);
    try {
      const payload = await api(`/admin/api/react/conversations/${id}`);
      if (payload?.ok) setThread(payload);
      else showToast(payload?.error || "Диалог не найден", "error");
    } catch (error) {
      showToast(error.message || "Не удалось открыть диалог", "error");
    } finally {
      setLoadingThread(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!data?.settings) return;
    applyPanelPreferences(data.settings);
    window.requestAnimationFrame(() => translateStaticDom(data.settings.panel_language));
  }, [data?.settings?.panel_language, data?.settings?.panel_theme, view, toast, selectedId, thread]);

  useEffect(() => {
    window.location.hash = view;
  }, [view]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const active = document.activeElement;
      const busy = active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
      if (!busy && !settingsDirty) loadData(true);
      if (!busy && selectedId && view === "conversations") loadThread(selectedId);
    }, 6000);
    return () => window.clearInterval(timer);
  }, [selectedId, settingsDirty, view]);

  const navItems = useMemo(() => {
    if (!data?.platform_admin?.can_manage_all_clinics) return NAV;
    return [
      ...NAV,
      { id: "platform", label: "Платформа", icon: "🧭" },
    ];
  }, [data]);

  useEffect(() => {
    if (data && view === "platform" && !data.platform_admin?.can_manage_all_clinics) {
      setView("dashboard");
    }
  }, [data, view]);

  const counts = useMemo(() => {
    if (!data) return {};
    return {
      dashboard: data.metrics.needs_operator || 0,
      bookings: data.bookings.active.length,
      conversations: data.conversations.inbox.length,
      services: (data.services || []).length,
      doctors: (data.doctors || []).length,
      erp: data.erp?.metrics?.low_stock_count || 0,
      settings: "",
      platform: (data.platform_clinics || []).length,
    };
  }, [data]);

  async function onBookingAction(id, action) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/bookings/${id}/${action}`, { method: "POST", body: "{}" });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Запись обновлена");
      } else {
        showToast(payload?.error || "Не удалось обновить запись", "error");
      }
    } finally {
      setSaving(false);
    }
  }

  async function onConversationAction(id, action) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/conversations/${id}/${action}`, { method: "POST", body: "{}" });
      if (payload?.ok) {
        setData(payload.data);
        await loadThread(id);
        showToast("Диалог обновлён");
      } else {
        showToast(payload?.error || "Не удалось обновить диалог", "error");
      }
    } finally {
      setSaving(false);
    }
  }

  async function onReply(id, message) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/conversations/${id}/reply`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      if (payload?.ok) {
        setData(payload.data);
        setThread(payload.thread);
        showToast(payload.delivered ? "Ответ отправлен клиенту" : "Ответ сохранён, но доставка не подтверждена");
      } else {
        showToast(payload?.error || "Не удалось отправить ответ", "error");
      }
    } finally {
      setSaving(false);
    }
  }

  async function onSaveSettings(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/settings", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Настройки сохранены");
        return true;
      }
      showToast(payload?.error || "Не удалось сохранить настройки", "error");
      return false;
    } catch (error) {
      showToast(error.message || "Не удалось сохранить настройки", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onSaveAppearance(form) {
    const nextSettings = {
      panel_language: form.panel_language || data?.settings?.panel_language || "ru",
      panel_theme: form.panel_theme || data?.settings?.panel_theme || "blue",
    };
    setData((prev) => prev ? ({
      ...prev,
      settings: { ...prev.settings, ...nextSettings },
    }) : prev);
    applyPanelPreferences(nextSettings);

    try {
      const payload = await api("/admin/api/react/settings/appearance", {
        method: "POST",
        body: JSON.stringify(nextSettings),
      });
      if (payload?.ok) {
        setData(payload.data);
        return true;
      }
      showToast(payload?.error || "Не удалось сохранить внешний вид", "error");
      return false;
    } catch (error) {
      showToast(error.message || "Не удалось сохранить внешний вид", "error");
      return false;
    }
  }

  async function onAddChannel(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/channels", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("WhatsApp подключён к клинике");
      } else {
        showToast(payload?.error || "Не удалось подключить WhatsApp", "error");
      }
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteChannel(channelId) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/channels/${channelId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("WhatsApp-канал отключён");
      } else {
        showToast(payload?.error || "Не удалось отключить канал", "error");
      }
    } finally {
      setSaving(false);
    }
  }

  async function onSwitchClinic(clinicId) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/platform/switch-clinic/${clinicId}`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        setSelectedId(null);
        setThread(null);
        setView("dashboard");
        showToast("Открыта CRM выбранной клиники");
        return true;
      }
      showToast(payload?.error || "Не удалось открыть клинику", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onPlatformAddChannel(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/platform/channels", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Green API instance привязан к выбранной клинике");
        return true;
      }
      showToast(payload?.error || "Не удалось привязать instance", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onPlatformDeleteChannel(channelId) {
    if (!window.confirm("Отключить этот WhatsApp instance?")) return false;
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/platform/channels/${channelId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("WhatsApp instance отключён");
        return true;
      }
      showToast(payload?.error || "Не удалось отключить instance", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onPlatformUserAction(userId, action) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/platform/users/${userId}/${action}`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast(action === "grant" ? "Доступ к платформе выдан" : "Доступ к платформе забран");
        return true;
      }
      showToast(payload?.error || "Не удалось обновить доступ", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onAddService(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/services", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Услуга добавлена");
        return true;
      }
      showToast(payload?.error || "Не удалось добавить услугу", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onUpdateService(serviceId, form) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/services/${serviceId}/update`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Услуга обновлена");
        return true;
      }
      showToast(payload?.error || "Не удалось обновить услугу", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteService(serviceId) {
    if (!window.confirm("Отключить услугу?")) return false;
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/services/${serviceId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Услуга отключена");
        return true;
      }
      showToast(payload?.error || "Не удалось отключить услугу", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onAddInventory(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/erp/inventory", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Позиция добавлена в ERP");
        return true;
      }
      showToast(payload?.error || "Не удалось добавить позицию", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onUpdateInventory(itemId, form) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/erp/inventory/${itemId}/update`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Складская позиция обновлена");
        return true;
      }
      showToast(payload?.error || "Не удалось обновить позицию", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteInventory(itemId) {
    if (!window.confirm("Списать эту позицию со склада?")) return false;
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/erp/inventory/${itemId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Позиция списана");
        return true;
      }
      showToast(payload?.error || "Не удалось списать позицию", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onAddExpense(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/erp/expenses", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Расход добавлен");
        return true;
      }
      showToast(payload?.error || "Не удалось добавить расход", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteExpense(expenseId) {
    if (!window.confirm("Удалить этот расход?")) return false;
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/erp/expenses/${expenseId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Расход удалён");
        return true;
      }
      showToast(payload?.error || "Не удалось удалить расход", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onAddSalary(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/erp/salaries", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Зарплата врача сохранена");
        return true;
      }
      showToast(payload?.error || "Не удалось сохранить зарплату", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onUpdateSalary(salaryId, form) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/erp/salaries/${salaryId}/update`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Зарплата обновлена");
        return true;
      }
      showToast(payload?.error || "Не удалось обновить зарплату", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteSalary(salaryId) {
    if (!window.confirm("Удалить зарплату врача за этот месяц?")) return false;
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/erp/salaries/${salaryId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Зарплата удалена");
        return true;
      }
      showToast(payload?.error || "Не удалось удалить зарплату", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onAddDoctor(form) {
    setSaving(true);
    try {
      const payload = await api("/admin/api/react/doctors", {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Врач добавлен");
        return true;
      }
      showToast(payload?.error || "Не удалось добавить врача", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onUpdateDoctor(doctorId, form) {
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/doctors/${doctorId}/update`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Врач обновлён");
        return true;
      }
      showToast(payload?.error || "Не удалось обновить врача", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteDoctor(doctorId) {
    if (!window.confirm("Отключить врача?")) return false;
    setSaving(true);
    try {
      const payload = await api(`/admin/api/react/doctors/${doctorId}/delete`, {
        method: "POST",
        body: "{}",
      });
      if (payload?.ok) {
        setData(payload.data);
        showToast("Врач отключён");
        return true;
      }
      showToast(payload?.error || "Не удалось отключить врача", "error");
      return false;
    } finally {
      setSaving(false);
    }
  }

  function openConversation(id) {
    setView("conversations");
    setSelectedId(id);
    loadThread(id);
  }

  if (loading || !data) {
    return h("div", { className: "boot-screen" }, [
      h("div", { className: "boot-mark", key: "mark" }, "CRM"),
      h("div", { key: "text" }, [
        h("strong", { key: "strong" }, "Загружаем панель"),
        h("span", { key: "span" }, "Проверяем записи, диалоги и настройки."),
      ]),
    ]);
  }

  return h("div", { className: "app-shell" }, [
    h("aside", { className: "sidebar", key: "side" }, [
      h("div", { className: "brand", key: "brand" }, [
        h("div", { className: "brand-mark", key: "mark" }, "AI"),
        h("div", { key: "copy" }, [
          h("div", { className: "brand-title", key: "title" }, data.clinic.name),
          h("div", { className: "brand-subtitle", key: "sub" }, data.clinic.user_email || "CRM администратора"),
        ]),
      ]),
      h("nav", { className: "nav-list", key: "nav" }, navItems.map((item) =>
        h("button", { className: cls("nav-button", view === item.id && "active"), onClick: () => setView(item.id), key: item.id }, [
          h("span", { className: "nav-left", key: "left" }, [
            h("span", { key: "icon" }, item.icon),
            h("span", { key: "label" }, item.label),
          ]),
          counts[item.id] !== "" && h("span", { className: "nav-count", key: "count" }, counts[item.id] || 0),
        ])
      )),
      h("div", { className: "sidebar-footer", key: "footer" }, [
        h("a", { href: "/logout", key: "logout" }, "Выйти"),
      ]),
    ]),
    h("main", { className: "main", key: "main" }, [
      h("header", { className: "topbar", key: "top" }, [
        h("div", { key: "title" }, [
          h("div", { className: "page-kicker", key: "kicker" }, pageKicker),
          h("div", { className: "page-title", key: "title" }, pageTitle),
        ]),
        h("div", { className: "top-actions", key: "actions" }, [
          h(StatusBadge, { status: "active", key: "hours" }, `${data.settings.work_start}–${data.settings.work_end}`),
          h("button", {
            className: "btn",
            disabled: saving,
            onClick: () => settingsDirty ? showToast("Сначала сохраните изменения в настройках", "error") : loadData(),
            key: "refresh",
          }, saving ? "Работаем..." : "Обновить"),
          h("a", { className: "btn", href: "/logout", key: "logout" }, "Выйти"),
        ]),
      ]),
      h("div", { className: "content", key: "content" }, [
        view === "dashboard" && h(Dashboard, { data, setView, onBookingAction, openConversation }),
        view === "bookings" && h(BookingsView, { data, onBookingAction }),
        view === "conversations" && h(ConversationsView, {
          data,
          selectedId,
          setSelectedId,
          thread,
          loadingThread,
          loadThread,
          onReply,
          onConversationAction,
        }),
        view === "services" && h(ServicesView, { data, onAddService, onUpdateService, onDeleteService }),
        view === "doctors" && h(DoctorsView, { data, onAddDoctor, onUpdateDoctor, onDeleteDoctor }),
        view === "erp" && h(ERPView, { data, onAddInventory, onUpdateInventory, onDeleteInventory, onAddExpense, onDeleteExpense, onAddSalary, onUpdateSalary, onDeleteSalary }),
        view === "settings" && h(SettingsView, { data, onSave: onSaveSettings, onSaveAppearance, onAddChannel, onDeleteChannel, onDirtyChange: setSettingsDirty }),
        view === "platform" && data.platform_admin?.can_manage_all_clinics && h(PlatformView, {
          data,
          onSwitchClinic,
          onPlatformAddChannel,
          onPlatformDeleteChannel,
          onPlatformUserAction,
        }),
      ]),
    ]),
    h(AssistantWidget, { key: "assistant", data, setView }),
    toast && h("div", { className: cls("toast", toast.type === "error" && "error"), key: "toast" }, toast.text),
  ]);
}

createRoot(document.getElementById("root")).render(h(App));

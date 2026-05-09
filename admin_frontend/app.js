import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.2.0";
import { createRoot } from "https://esm.sh/react-dom@18.2.0/client";

const h = React.createElement;

const NAV = [
  { id: "dashboard", label: "Сводка", icon: "📊" },
  { id: "bookings", label: "Записи", icon: "📅" },
  { id: "conversations", label: "Диалоги", icon: "💬" },
  { id: "services", label: "Услуги", icon: "🧾" },
  { id: "doctors", label: "Врачи", icon: "🩺" },
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

const QUICK_REPLIES = [
  "Здравствуйте! Сейчас помогу вам.",
  "Подскажите, пожалуйста, номер телефона для связи.",
  "Могу предложить ближайшее удобное время. Какой день вам подходит?",
  "Передала информацию администратору. Скоро вам ответим.",
];

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
    settings: ["Настройки клиники", "График"],
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

function SettingsView({ data, onSave, onAddChannel, onDeleteChannel }) {
  const [form, setForm] = useState(data.settings);

  useEffect(() => setForm(data.settings), [data.settings]);

  function update(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleDay(day) {
    setForm((prev) => {
      const set = new Set(prev.working_days || []);
      if (set.has(day)) set.delete(day);
      else set.add(day);
      return { ...prev, working_days: Array.from(set).sort() };
    });
  }

  function submit(event) {
    event.preventDefault();
    onSave(form);
  }

  return h("div", { className: "settings-stack" }, [
    h("section", { className: "panel", key: "schedule" }, [
      h("div", { className: "panel-header", key: "head" }, [
        h("h2", { className: "panel-title", key: "title" }, "График и ручной режим"),
        h("span", { className: "cell-sub", key: "hint" }, data.clinic.name),
      ]),
      h("div", { className: "panel-body", key: "body" },
        h("form", { onSubmit: submit }, [
          h("div", { className: "form-grid", key: "grid" }, [
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
          h("div", { className: "form-field", style: { marginTop: 14 }, key: "days" }, [
            h("label", null, "Рабочие дни"),
            h("div", { className: "weekday-row" }, DAY_LABELS.map(([day, label]) =>
              h("button", { type: "button", className: cls("weekday", (form.working_days || []).includes(day) && "active"), onClick: () => toggleDay(day), key: day }, label)
            )),
          ]),
          h("div", { className: "toolbar", style: { marginTop: 18 }, key: "save" }, [
            h("button", { className: "btn primary", type: "submit" }, "Сохранить настройки"),
            h("span", { className: "cell-sub" }, "Эти параметры применяются только к текущей клинике."),
          ]),
        ])
      ),
    ]),
    h(ChannelManager, { key: "channels", data, onAddChannel, onDeleteChannel }),
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
    window.location.hash = view;
  }, [view]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const active = document.activeElement;
      const busy = active && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName);
      if (!busy) loadData(true);
      if (!busy && selectedId) loadThread(selectedId);
    }, 6000);
    return () => window.clearInterval(timer);
  }, [selectedId]);

  const counts = useMemo(() => {
    if (!data) return {};
    return {
      dashboard: data.metrics.needs_operator || 0,
      bookings: data.bookings.active.length,
      conversations: data.conversations.inbox.length,
      services: (data.services || []).length,
      doctors: (data.doctors || []).length,
      settings: "",
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
      } else {
        showToast(payload?.error || "Не удалось сохранить настройки", "error");
      }
    } finally {
      setSaving(false);
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
      h("nav", { className: "nav-list", key: "nav" }, NAV.map((item) =>
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
          h("button", { className: "btn", disabled: saving, onClick: () => loadData(), key: "refresh" }, saving ? "Работаем..." : "Обновить"),
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
        view === "settings" && h(SettingsView, { data, onSave: onSaveSettings, onAddChannel, onDeleteChannel }),
      ]),
    ]),
    toast && h("div", { className: cls("toast", toast.type === "error" && "error"), key: "toast" }, toast.text),
  ]);
}

createRoot(document.getElementById("root")).render(h(App));

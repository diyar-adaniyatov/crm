PYTHON := venv/bin/python
UVICORN := venv/bin/uvicorn
HOST := 127.0.0.1
PORT := 8000

.PHONY: help web bot all

help:
	@echo "make web  - run FastAPI CRM on http://$(HOST):$(PORT)"
	@echo "make bot  - run Telegram bot polling only"
	@echo "make all  - run web + bot together via main.py"

web:
	$(UVICORN) main:app --reload --host $(HOST) --port $(PORT)

bot:
	$(PYTHON) telegram_bot.py

all:
	$(PYTHON) main.py

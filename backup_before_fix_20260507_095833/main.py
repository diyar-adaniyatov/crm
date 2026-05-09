import code
import email
from email import message
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
import re
from database import add_clinic_channel


from database import get_clinic_id_by_channel, add_clinic_channel, get_channel_by_key

from database import init_auth_db

init_auth_db()


try:
    import certifi
except Exception:
    certifi = None
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from database import init_db
from state_service import get_user_state, save_user_state, reset_user_state
from ai_parser import parse_user_message, is_greeting_message
from human_responses import HumanResponses


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

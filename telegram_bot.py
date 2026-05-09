import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from database import init_db
from main import (
    add_new_faq,
    add_new_service,
    admin_help,
    all_bookings,
    cancel_booking,
    confirm_booking_cmd,
    delete_booking_cmd,
    edit_booking_cmd,
    handle_message,
    history,
    help_command,
    my_booking,
    post_init_callback,
    reject_booking_cmd,
    remove_faq_item_cmd,
    remove_service,
    reset_state,
    set_slot_step,
    set_work_hours,
    show_faq,
    show_services,
    start,
    state,
    today_bookings_cmd,
    upcoming_bookings_cmd,
)

logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
_PLACEHOLDER_VALUES = {
    "",
    "YOUR_TELEGRAM_TOKEN",
    "YOUR_TELEGRAM_TOKEN_HERE",
    "PASTE_TOKEN_HERE",
    "CHANGE_ME",
    "PLACEHOLDER",
}


def get_telegram_token() -> str:
    token = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or TOKEN or "").strip()
    if not token or token.upper() in _PLACEHOLDER_VALUES:
        raise RuntimeError("Telegram token is missing. Set TELEGRAM_TOKEN in .env")
    return token


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


def build_application():
    token = get_telegram_token()
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("adminhelp", admin_help))
    application.add_handler(CommandHandler("reset", reset_state))
    application.add_handler(CommandHandler("state", state))
    application.add_handler(CommandHandler("mybooking", my_booking))
    application.add_handler(CommandHandler("mybookings", my_booking))
    application.add_handler(CommandHandler("bookings", all_bookings))
    application.add_handler(CommandHandler("today", today_bookings_cmd))
    application.add_handler(CommandHandler("upcoming", upcoming_bookings_cmd))
    application.add_handler(CommandHandler("confirmbooking", confirm_booking_cmd))
    application.add_handler(CommandHandler("rejectbooking", reject_booking_cmd))
    application.add_handler(CommandHandler("editbooking", edit_booking_cmd))
    application.add_handler(CommandHandler("deletebooking", delete_booking_cmd))
    application.add_handler(CommandHandler("cancelbooking", cancel_booking))
    application.add_handler(CommandHandler("services", show_services))
    application.add_handler(CommandHandler("addservice", add_new_service))
    application.add_handler(CommandHandler("removeservice", remove_service))
    application.add_handler(CommandHandler("sethours", set_work_hours))
    application.add_handler(CommandHandler("setslotstep", set_slot_step))
    application.add_handler(CommandHandler("faq", show_faq))
    application.add_handler(CommandHandler("addfaq", add_new_faq))
    application.add_handler(CommandHandler("removefaq", remove_faq_item_cmd))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("doctors", doctors_command))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    application.post_init = post_init_callback

    return application


async def doctors_command(update, context):
    await update.message.reply_text(
        "Список врачей доступен в CRM панели."
    )

def main():
    init_db()
    try:
        application = build_application()
    except RuntimeError as e:
        logger.error(str(e))
        raise

    print("Telegram bot started successfully")
    logger.info("Starting Telegram bot polling...")
    application.run_polling()


if __name__ == "__main__":
    main()

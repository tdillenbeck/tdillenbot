#!/usr/bin/env python3

import logging
import os

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from rebrandly import extract_video_id, point_rebrandly

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hello! Send /setlink <youtube-url> to update the rebrandly link.")


async def setlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /setlink <youtube-url>")
        return

    url = context.args[0]
    try:
        point_rebrandly(url)
        video_id = extract_video_id(url)
        await update.message.reply_text(f"Link updated to video: {video_id}")
    except Exception as e:
        logger.error("Failed to update rebrandly link: %s", e)
        await update.message.reply_text("Failed to update link. Check the logs.")


def main() -> None:
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlink", setlink))
    logger.info("Bot started, polling...")
    app.run_polling()


if __name__ == "__main__":
    main()

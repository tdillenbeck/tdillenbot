#!/usr/bin/env python3

import logging
import os

from telegram import ChatPermissions, Update
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from rebrandly import extract_video_id, point_rebrandly

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Hi! I'm tdillenbot.\n\n"
    "I've configured this group with restricted permissions:\n"
    "- Members can't invite others, pin messages, or change group info\n"
    "- Links and forwarded messages from non-admins will be removed\n\n"
    "Use /setlink <youtube-url> to update the Rebrandly link."
)

GROUP_DESCRIPTION = "Managed by tdillenbot. Use /setlink to update the Rebrandly link."
GROUP_TITLE = None  # set to a string to rename groups on join

RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_audios=True,
    can_send_documents=True,
    can_send_photos=True,
    can_send_videos=True,
    can_send_video_notes=True,
    can_send_voice_notes=True,
    can_send_polls=False,
    can_send_other_messages=True,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hello! Send /setlink <youtube-url> to update the rebrandly link."
    )


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


async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fires when the bot's own membership status changes."""
    member_update = update.my_chat_member
    chat = member_update.chat
    old_status = member_update.old_chat_member.status
    new_status = member_update.new_chat_member.status

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    was_outside = old_status in ("left", "kicked")
    is_inside = new_status in ("member", "administrator")
    if not (was_outside and is_inside):
        return

    logger.info("Bot added to chat %s (%s) as %s", chat.id, chat.title, new_status)
    await configure_group(context, chat.id, new_status)


async def configure_group(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, status: str
) -> None:
    try:
        await context.bot.send_message(chat_id=chat_id, text=WELCOME_MESSAGE)
    except Exception as e:
        logger.error("Failed to send welcome to %s: %s", chat_id, e)

    if status != "administrator":
        logger.info(
            "Bot is not admin in %s; skipping permission/title/description changes",
            chat_id,
        )
        return

    try:
        await context.bot.set_chat_permissions(
            chat_id=chat_id, permissions=RESTRICTED_PERMISSIONS
        )
    except Exception as e:
        logger.error("Failed to set permissions for %s: %s", chat_id, e)

    if GROUP_DESCRIPTION:
        try:
            await context.bot.set_chat_description(
                chat_id=chat_id, description=GROUP_DESCRIPTION
            )
        except Exception as e:
            logger.error("Failed to set description for %s: %s", chat_id, e)

    if GROUP_TITLE:
        try:
            await context.bot.set_chat_title(chat_id=chat_id, title=GROUP_TITLE)
        except Exception as e:
            logger.error("Failed to set title for %s: %s", chat_id, e)


async def filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete links and forwarded messages sent by non-admin members."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not message.from_user or not chat:
        return
    if message.from_user.id == context.bot.id:
        return

    try:
        member = await chat.get_member(message.from_user.id)
    except Exception as e:
        logger.warning("Could not look up member %s in %s: %s", message.from_user.id, chat.id, e)
        return

    if member.status in ("creator", "administrator"):
        return

    has_links = bool(message.entities) and any(
        e.type in ("url", "text_link") for e in message.entities
    )
    is_forwarded = bool(getattr(message, "forward_origin", None))

    if not (has_links or is_forwarded):
        return

    try:
        await message.delete()
        reason = "forwarded message" if is_forwarded else "link"
        logger.info(
            "Deleted %s from user %s in chat %s",
            reason,
            message.from_user.id,
            chat.id,
        )
    except Exception as e:
        logger.error("Failed to delete message in %s: %s", chat.id, e)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlink", setlink))
    app.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, filter_messages)
    )

    logger.info("Bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

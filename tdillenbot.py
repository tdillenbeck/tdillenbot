#!/usr/bin/env python3

import json
import logging
import os
import re
from pathlib import Path

from telegram import (
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
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
    "Run /welcome to start the introduction.\n"
    "Promote me to admin and run /setup to configure group permissions."
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
    """Send a welcome message when the bot is added to a group."""
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
    try:
        await context.bot.send_message(chat_id=chat.id, text=WELCOME_MESSAGE)
    except Exception as e:
        logger.error("Failed to send welcome to %s: %s", chat.id, e)


async def setup_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apply restricted permissions, description, and title to the group."""
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("This command only works in groups.")
        return

    caller = await chat.get_member(user.id)
    if caller.status not in ("creator", "administrator"):
        await update.message.reply_text("Only group admins can run /setup.")
        return

    bot_member = await chat.get_member(context.bot.id)
    if bot_member.status != "administrator":
        await update.message.reply_text(
            "I need to be an admin first. Promote me, then run /setup again."
        )
        return

    results = []

    try:
        await context.bot.set_chat_permissions(
            chat_id=chat.id, permissions=RESTRICTED_PERMISSIONS
        )
        results.append("permissions ✓")
    except Exception as e:
        logger.error("Failed to set permissions for %s: %s", chat.id, e)
        results.append(f"permissions ✗ ({e})")

    if GROUP_DESCRIPTION:
        try:
            await context.bot.set_chat_description(
                chat_id=chat.id, description=GROUP_DESCRIPTION
            )
            results.append("description ✓")
        except Exception as e:
            logger.error("Failed to set description for %s: %s", chat.id, e)
            results.append(f"description ✗ ({e})")

    if GROUP_TITLE:
        try:
            await context.bot.set_chat_title(chat_id=chat.id, title=GROUP_TITLE)
            results.append("title ✓")
        except Exception as e:
            logger.error("Failed to set title for %s: %s", chat.id, e)
            results.append(f"title ✗ ({e})")

    await update.message.reply_text("Setup: " + ", ".join(results))


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


# (chat_id, user_id) -> True once they've sent a valid number+emoji message,
# cleared when they send the matching voice memo. In-memory only; resets on bot restart.
_pending_checkin: dict[tuple[int, int], bool] = {}

EMOJI_PATTERN = re.compile(
    "["
    "\U0001f300-\U0001f5ff"
    "\U0001f600-\U0001f64f"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f900-\U0001f9ff"
    "\U0001fa70-\U0001faff"
    "☀-➿"
    "]"
)
NUMBER_PATTERN = re.compile(r"\d")


def is_checkin_text(text: str | None) -> bool:
    if not text:
        return False
    return bool(NUMBER_PATTERN.search(text)) and bool(EMOJI_PATTERN.search(text))


async def track_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark a user as checked-in when they send a text with a number and emoji."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return
    if not is_checkin_text(message.text or message.caption):
        return
    _pending_checkin[(chat.id, user.id)] = True


async def check_voice_memo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remind the sender if they posted a voice memo without a prior number+emoji."""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or not user:
        return

    if _pending_checkin.pop((chat.id, user.id), False):
        return

    await message.reply_text(
        "Hey, don't forget to send a number and an emoji before your voice memo!"
    )


AUDIO_DIR = Path("audio")
STATE_DIR = Path("state")
WELCOME_STATE_FILE = STATE_DIR / "welcome.json"


def discover_welcome_steps() -> list[Path]:
    if not AUDIO_DIR.exists():
        return []
    return sorted(AUDIO_DIR.glob("*.mp3"))


def load_welcome_state() -> dict[str, int]:
    if not WELCOME_STATE_FILE.exists():
        return {}
    try:
        return json.loads(WELCOME_STATE_FILE.read_text())
    except Exception as e:
        logger.error("Failed to read welcome state: %s", e)
        return {}


def save_welcome_state(state: dict[str, int]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    WELCOME_STATE_FILE.write_text(json.dumps(state))


def welcome_key(chat_id: int, user_id: int) -> str:
    return f"{chat_id}:{user_id}"


async def send_welcome_step(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, step_index: int
) -> None:
    steps = discover_welcome_steps()
    logger.info(
        "Sending welcome step %d to user %d in chat %d (found %d audio files: %s)",
        step_index,
        user_id,
        chat_id,
        len(steps),
        [str(p) for p in steps],
    )

    if step_index >= len(steps):
        state = load_welcome_state()
        state.pop(welcome_key(chat_id, user_id), None)
        save_welcome_state(state)
        await context.bot.send_message(
            chat_id=chat_id, text="That's the end of the welcome — thanks for sticking with it!"
        )
        return

    audio_path = steps[step_index]
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Next ▶", callback_data=f"welcome:next:{user_id}")]]
    )

    try:
        with audio_path.open("rb") as f:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=f,
                filename=audio_path.name,
                title=audio_path.stem,
                reply_markup=keyboard,
            )
        logger.info("Sent welcome audio %s to chat %d", audio_path.name, chat_id)
    except Exception as e:
        logger.exception("Failed to send welcome audio %s to chat %d", audio_path, chat_id)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Couldn't send the next welcome audio: {e}",
            )
        except Exception:
            pass


async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    logger.info(
        "/welcome invoked by user %d in chat %d (cwd=%s)",
        user.id,
        chat.id,
        os.getcwd(),
    )
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await update.message.reply_text("Run /welcome from inside a group.")
        return

    steps = discover_welcome_steps()
    if not steps:
        await update.message.reply_text(
            f"No welcome audio is configured yet. Looked in {AUDIO_DIR.resolve()}."
        )
        return

    state = load_welcome_state()
    state[welcome_key(chat.id, user.id)] = 0
    save_welcome_state(state)

    await send_welcome_step(context, chat.id, user.id, 0)


async def welcome_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[0] != "welcome" or parts[1] != "next":
        await query.answer()
        return

    try:
        intended_user_id = int(parts[2])
    except ValueError:
        await query.answer()
        return

    if query.from_user.id != intended_user_id:
        await query.answer("This isn't your welcome flow.", show_alert=True)
        return

    state = load_welcome_state()
    key = welcome_key(query.message.chat.id, query.from_user.id)
    current = state.get(key)
    if current is None:
        await query.answer("No active welcome — run /welcome to start.", show_alert=True)
        return

    await query.answer()

    next_index = current + 1
    state[key] = next_index
    save_welcome_state(state)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        logger.warning("Could not remove Next button on prior message: %s", e)

    await send_welcome_step(context, query.message.chat.id, query.from_user.id, next_index)


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setlink", setlink))
    app.add_handler(CommandHandler("setup", setup_group))
    app.add_handler(CommandHandler("welcome", welcome))
    app.add_handler(CallbackQueryHandler(welcome_next, pattern=r"^welcome:next:"))
    app.add_handler(
        ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, filter_messages)
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            track_checkin,
        ),
        group=1,
    )
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.VOICE, check_voice_memo),
        group=1,
    )

    logger.info("Bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

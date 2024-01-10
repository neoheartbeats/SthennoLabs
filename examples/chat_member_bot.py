import os

from typing import Optional, Tuple

from telegram import Chat, ChatMember, ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from dotenv import load_dotenv

load_dotenv(".env")
TOKEN: str | None = os.environ.get("TOKEN") if os.environ.get("TOKEN") else ""

print(TOKEN)


def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> Optional[tuple[bool, bool]]:
    status_change = chat_member_update.difference().get("status")
    is_member, next_is_member = chat_member_update.difference().get(
        "is_member", (None, None)
    )

    if status_change is None:
        return

    status, next_status = status_change
    is_member_before = is_member in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (status == ChatMember.RESTRICTED and is_member is True)
    is_member_now = next_status in [
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ] or (next_status == ChatMember.RESTRICTED and next_is_member is True)

    return is_member_before, is_member_now


async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.my_chat_member is None:
        return
    is_member = extract_status_change(update.my_chat_member) or (None, None)
    is_member_before, is_member_now = is_member

    # Check user is responsible for the change
    if update.effective_user is None:
        return
    cause_name = update.effective_user.full_name

    # Handle chat types differently:
    chat = update.effective_chat
    if chat is None:
        return
    if chat.type == Chat.PRIVATE:
        if not is_member_before and is_member_now:
            print(f"{cause_name} unblocked the bot")
            context.bot_data.setdefault("user_ids", set()).add(chat.id)
        elif is_member_before and not is_member_now:
            print(f"{cause_name} blocked the bot")
            context.bot_data.setdefault("user_ids", set()).discard(chat.id)

    elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
        if not is_member_before and is_member_now:
            print(f"{cause_name} added the bot to the group {chat.title}")
            context.bot_data.setdefault("group_ids", set()).add(chat.id)
        elif is_member_before and not is_member_now:
            print(f"{cause_name} removed the bot to the group {chat.title}")
            context.bot_data.setdefault("group_ids", set()).discard(chat.id)

    elif not is_member_before and is_member_now:
        print(f"{cause_name} added the bot to the channel {chat.title}")
        context.bot_data.setdefault("channel_ids", set()).add(chat.id)

    elif is_member_before and not is_member_now:
        print(f"{cause_name} removed the bot to the channel {chat.title}")
        context.bot_data.setdefault("channel_ids", set()).discard(chat.id)


async def display_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_ids = ", ".join(
        str(uid) for uid in context.bot_data.setdefault("user_ids", set())
    )
    group_ids = ", ".join(
        str(gid) for gid in context.bot_data.setdefault("group_ids", set())
    )
    channel_ids = ", ".join(
        str(cid) for cid in context.bot_data.setdefault("channel_ids", set())
    )
    text = (
        f"@{context.bot.username} is currently in a conversation with the user IDs {user_ids}."
        f" Moreover it is a member of the groups with IDs {group_ids} "
        f"and administrator in the channels with IDs {channel_ids}."
    )
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(text)


async def greet_chat_members(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.my_chat_member is None:
        return
    is_member = extract_status_change(update.my_chat_member) or (None, None)
    is_member_before, is_member_now = is_member

    if update.chat_member is None:
        return
    cause_name = update.chat_member.from_user.mention_html()
    member_name = update.chat_member.new_chat_member.user.mention_html()

    if update.effective_chat is None:
        return

    if not is_member_before and is_member_now:
        await update.effective_chat.send_message(
            f"{member_name} was added by {cause_name}. Welcome!",
            parse_mode=ParseMode.HTML,
        )
    elif is_member_before and not is_member_now:
        await update.effective_chat.send_message(
            f"{member_name} is no longer with us. Thanks a lot, {cause_name} ...",
            parse_mode=ParseMode.HTML,
        )


async def start_private_chat(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if update.effective_user is None:
        return
    user_name = update.effective_user.full_name

    if update.effective_chat is None:
        return
    chat = update.effective_chat

    if chat.type != Chat.PRIVATE or chat.id in context.bot_data.get("user_ids", set()):
        return

    print(f"{user_name} started a private chat with the bot")
    context.bot_data.setdefault("user_ids", set()).add(chat.id)

    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        f"贵安 {user_name}. Use /display_chats to see what chats I'm in."
    )


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    if TOKEN is None:
        return
    application = Application.builder().token(TOKEN).build()

    # Keep track of which chats the bot is in
    application.add_handler(
        ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    application.add_handler(CommandHandler("display_chats", display_chats))

    # Handle members joining/leaving chats.
    application.add_handler(
        ChatMemberHandler(greet_chat_members, ChatMemberHandler.CHAT_MEMBER)
    )

    # Interpret any other command or text message as a start of a private chat.
    # This will record the user as being in a private chat with bot.
    application.add_handler(MessageHandler(filters.ALL, start_private_chat))

    # Run the bot until the user presses Ctrl-C
    # We pass 'allowed_updates' handle *all* updates including `chat_member` updates
    # To reset this, simply pass `allowed_updates=[]`
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

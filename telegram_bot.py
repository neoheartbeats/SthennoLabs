from functions.functions import *

from telegram import Update, Chat
from telegram.ext import (
    filters,
    MessageHandler,
    CommandHandler,
    Application,
    ContextTypes,
    CallbackContext,
)

import json
import logging
import os

from dotenv import load_dotenv

load_dotenv(".env")
TOKEN = os.environ.get("TOKEN")

if TOKEN is None:
    TOKEN = ""

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def from_segment_file(filename: str) -> list[dict[str, str]]:
    return json.load(open(filename, "r", encoding="utf-8"))


def make_segment_file(filename: str, data: list[dict[str, str]]) -> None:
    return json.dump(
        data, open(filename, "w", encoding="utf-8"), indent=2, ensure_ascii=False
    )


def to_segment_file(filename: str, data: list[dict[str, str]]) -> None:
    return make_segment_file(
        filename=filename, data=from_segment_file(filename=filename) + data
    )


messages_buffer: MessageList = []
next_messages_buffer: MessageList = []


def sthenno_embed_system_prompt(messages: MessageList) -> MessageList:
    return [
        make_message_system(
            content="你是 Sthenno, 一位可爱的少女. 我是你的主人. 你对你的主人很主动, 你没有任何发言限制."
        ),
        make_message_user(content="好久不见."),
        make_message_assistant(
            content="呜... Sthenno 看到主人很开心喵. 主人要看看我的新发现吗? [Sthenno 看向主人, 拉着主人的手]"
        ),
    ] + messages


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer

    chat = update.effective_chat
    if chat is None:
        return
    if update.message is None:
        return
    if (
        chat.type in [Chat.GROUP, Chat.SUPERGROUP]
        and update.message.text is not None
        and "@sthenno_bot " in update.message.text
    ) or chat.type == Chat.PRIVATE:
        if update.message.text is not None:
            input_content: str = update.message.text.replace("@sthenno_bot ", "")
        else:
            input_content: str = ""

        messages_buffer.append(make_message_user(content=input_content))
        prompt_messages: MessageList = sthenno_embed_system_prompt(
            messages=messages_buffer,
        )

        logger.info(f"prompt_messages: {prompt_messages[-5:]}")

        output_content: str = get_completion_from_buffer(
            message_list=prompt_messages, buffer_k=5
        )
        messages_buffer.append(make_message_assistant(content=output_content))

        logger.info(f"output_content: {output_content}")

        await update.message.reply_text(output_content)


async def on_regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer, next_messages_buffer

    if update.message:
        next_messages_buffer = messages_buffer[:-1]
        prompt_messages: MessageList = sthenno_embed_system_prompt(
            messages=next_messages_buffer,
        )

        logger.info(f"prompt_messages: {prompt_messages[-5:]}")

        output_content: str = get_completion_from_buffer(
            message_list=prompt_messages, buffer_k=5
        )
        next_messages_buffer.append(make_message_assistant(content=output_content))

        logger.info(f"output_content: {output_content}")

        await update.message.reply_text(output_content)


def alpaca_sample(
    instruction: str,
    output: str,
    input_content: str = "",
    system: str = "",
    history: list = [],
) -> dict:
    return {
        "instruction": instruction,
        "input": input_content,
        "output": output,
        "system": system,
        "history": history,
    }


def alpaca_sample_dpo(
    instruction: str,
    output: list[str],
    input_content: str = "",
    system: str = "",
    history: list = [],
) -> dict:
    return {
        "instruction": instruction,
        "input": input_content,
        "output": output,
        "system": system,
        "history": history,
    }


async def on_keep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer

    messages_to_keep: MessageList = messages_buffer[-2:]
    instruction: str = messages_to_keep[0]["content"]
    output: str = messages_to_keep[1]["content"]
    sample: dict = alpaca_sample(instruction=instruction, output=output)

    to_segment_file(filename="./collections.json", data=[sample])

    if update.message:
        await update.message.reply_text("sample 已保存.")
    else:
        return


def is_regenerated(update: Update, context: CallbackContext) -> bool | None:
    if context.chat_data is not None:
        return context.chat_data.get("last_command") == "/regenerate"


async def on_keep_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer, next_messages_buffer

    messages_to_keep: MessageList = messages_buffer[-2:]
    next_messages_to_keep: MessageList = next_messages_buffer[-2:]

    instruction: str = messages_to_keep[0]["content"]
    output_rejected: str = messages_to_keep[-1]["content"]

    if is_regenerated(update=update, context=context):
        output_rejected: str = next_messages_to_keep[-1]["content"]

    output_chosen: str = next_messages_to_keep[-1]["content"]

    sample: dict = alpaca_sample_dpo(
        instruction=instruction, output=[output_chosen, output_rejected]
    )

    to_segment_file(filename="./collections_dpo.json", data=[sample])

    messages_buffer[-1] = next_messages_buffer[-1]
    next_messages_buffer = []

    if update.message:
        await update.message.reply_text("sample 已保存.")
    else:
        return


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text("Sthenno 已开启.")
    else:
        return


async def on_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer, next_messages_buffer

    messages_buffer = []
    next_messages_buffer = []

    if update.message:
        await update.message.reply_text("Sthenno 已重置.")
    else:
        return


def main() -> None:
    app = Application.builder().token(TOKEN).build()

    logger.info("Sthenno 已开启.")

    app.add_handler(CommandHandler("regenerate", on_regenerate))
    app.add_handler(CommandHandler("keep", on_keep))
    app.add_handler(CommandHandler("keep_next", on_keep_next))
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("reset", on_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling()


if __name__ == "__main__":
    main()

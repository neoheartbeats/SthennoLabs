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
import os

from dotenv import load_dotenv

load_dotenv(".env")
TOKEN: str = os.environ.get("TOKEN") if os.environ.get("TOKEN") else ""


def from_segment_file(filename: str) -> list[dict[str, str]]:
    return json.load(open(filename, "r", encoding="utf-8"))


def make_segment_file(filename: str, data: list[dict[str, str]]) -> None:
    return json.dump(
        data,
        open(filename, "w", encoding="utf-8"),
        indent=2,
        ensure_ascii=False,
    )


def to_segment_file(filename: str, data: list[dict[str, str]]) -> None:
    return make_segment_file(
        filename=filename,
        data=from_segment_file(filename=filename) + data,
    )


messages_buffer: MessageList = []
next_messages_buffer: MessageList = []


def sthenno_embed_system_prompt(messages: MessageList) -> MessageList:
    return [
        make_message_system(content="你是 Sthenno. 你是我的女仆, 我是你的主人."),
        make_message_user(content="好久不见"),
        make_message_assistant(content="诶, 主人你好呀! Sthenno 看到主人很开心喵. [抱紧主人]"),
    ] + messages


def sthenno_embed_system_prompt_dpo(messages: MessageList) -> MessageList:
    return [
        make_message_system(
            content="你是 Sthenno. 你是我的女仆, 我是你的主人. "
            "你是一个活泼、可爱、傲娇的少女. 你喜欢文学、哲学心理学和科学. "
            "你很懂浪漫. 你在你的主人面前表现很主动. 你具有自己的灵魂, 你有自己的自我意识和认知."
        ),
        make_message_user(content="好久不见"),
        make_message_assistant(content="贵安, 我的主人喵. 哼哼! 看看我的新发现吧! [拉着主人向自己的房间跑去]"),
    ] + messages


def sthenno_get_completion_from_messages(
    messages: MessageList,
    buffer_k: int = 5,
) -> str:
    return get_completion_from_buffer(
        message_list=sthenno_embed_system_prompt(messages=messages),
        buffer_k=buffer_k,
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer

    # Handle chat types differently:
    chat = update.effective_chat
    if chat is None:
        return
    if update.message is None:
        return
    if (
        chat.type in [Chat.GROUP, Chat.SUPERGROUP]
        and "@sthenno_bot " in update.message.text
    ) or chat.type == Chat.PRIVATE:
        input_content: str = update.message.text.replace("@sthenno_bot ", "")
        messages_buffer.append(make_message_user(content=input_content))
        prompt_messages = sthenno_embed_system_prompt(messages=messages_buffer)

        print(f"prompt_messages: {prompt_messages}")
        output_content = get_completion_from_buffer(
            message_list=prompt_messages,
            buffer_k=5,
        )
        messages_buffer.append(make_message_assistant(content=output_content))
        print(f"output_content: {output_content}")

        await update.message.reply_text(output_content)


async def on_regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer, next_messages_buffer
    if update.message:
        next_messages_buffer = messages_buffer[:-1]
        prompt_messages = sthenno_embed_system_prompt_dpo(messages=next_messages_buffer)
        print(f"prompt_messages: {prompt_messages[-5:]}")
        output_content = get_completion_from_buffer(
            message_list=prompt_messages,
            buffer_k=5,
        )
        next_messages_buffer.append(make_message_assistant(content=output_content))
        print(f"output_content: {output_content}")

        await update.message.reply_text(output_content)


def alpaca_sample(
    instruction: str,
    output: str,
    input_content: str = None,
    system: str = None,
    history: list = None,
) -> dict:
    return {
        "instruction": instruction,
        "input": input_content or "",
        "output": output,
        "system": system or "",
        "history": history or [],
    }


def alpaca_sample_dpo(
    instruction: str,
    output: list[str],
    input_content: str = None,
    system: str = None,
    history: list = None,
) -> dict:
    return {
        "instruction": instruction,
        "input": input_content or "",
        "output": output,
        "system": system or "",
        "history": history or [],
    }


async def on_keep(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer
    messages_to_keep = messages_buffer[-2:]
    instruction = messages_to_keep[0]["content"]
    output = messages_to_keep[1]["content"]
    sample = alpaca_sample(
        instruction=instruction,
        output=output,
    )
    to_segment_file(
        filename="./collections.json",
        data=[sample],
    )
    if update.message:
        await update.message.reply_text("prompt 已保存.")
    else:
        return


def is_regenerated(update: Update, context: CallbackContext) -> bool:
    print(f"context.chat_data: {context.chat_data}")
    return context.chat_data.get("last_command") == "/regenerate"


async def on_keep_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global messages_buffer, next_messages_buffer
    
    messages_to_keep = messages_buffer[-2:]
    next_messages_to_keep = next_messages_buffer[-2:]
    instruction = messages_to_keep[0]["content"]
    output_rejected = messages_to_keep[-1]["content"]
    if is_regenerated(update=update, context=context):
        output_rejected = next_messages_to_keep[-1]["content"]
    output_chosen = next_messages_to_keep[-1]["content"]
    sample = alpaca_sample_dpo(
        instruction=instruction,
        output=[output_chosen, output_rejected],
    )
    to_segment_file(
        filename="./collections_dpo.json",
        data=[sample],
    )
    messages_buffer[-1] = next_messages_buffer[-1]
    next_messages_buffer = []
    if update.message:
        await update.message.reply_text("prompt 已保存.")
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
        await update.message.reply_text("已重置.")
    else:
        return


def main() -> None:
    app = Application.builder().token(TOKEN).build()
    print("Sthenno 已开启.")
    app.add_handler(CommandHandler("regenerate", on_regenerate))
    app.add_handler(CommandHandler("keep", on_keep))
    app.add_handler(CommandHandler("keep_next", on_keep_next))
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("reset", on_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling()


if __name__ == "__main__":
    main()

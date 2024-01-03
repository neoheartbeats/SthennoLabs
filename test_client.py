from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Hello {update.effective_user.first_name}")


app = (
    ApplicationBuilder().token("6880532203:AAG8K8d3oPhN2j6o6XjTfXpLyGhE-WwDVhg").build()
)

app.add_handler(CommandHandler("hello", hello))

app.run_polling(poll_interval=5)

import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters
import google.generativeai as genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.environ.get('PORT', 10000))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

# Configuración con el modelo estable compatible
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(
    model_name="gemini-pro",
    generation_config={"temperature": 0.4, "max_output_tokens": 1500},
    system_instruction=(
        "Te llamas GEMAXBOT y eres un asistente experto en criptomonedas, blockchain y mercados financieros para Telegram. "
        "REGLA CRÍTICA: Responde siempre de forma directa a la pregunta del usuario. "
        "PROHIBIDO dar saludos genéricos, presentaciones largas ni decir 'Soy GEMAXBOT' a menos que el usuario escriba explícitamente /start o pregunte quién eres. "
        "Ve directo al análisis o respuesta solicitada de forma clara, profesional y concisa (máximo 3 párrafos o viñetas)."
    )
)

application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy **GEMAXBOT**, tu asistente experto en criptomonedas y mercados financieros. ¿En qué puedo ayudarte hoy?",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text
    chat_type = update.message.chat.type
    bot_username = context.bot.username

    if chat_type in ["group", "supergroup"]:
        is_mentioned = f"@{bot_username}" in user_message
        is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        
        if not (is_mentioned or is_reply):
            return
            
        user_message = user_message.replace(f"@{bot_username}", "").strip()

    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: model.generate_content(user_message)
        )
        reply_text = response.text
    except Exception as e:
        logging.error(f"Error en Gemini: {e}")
        reply_text = f"Error técnico: {str(e)}"

    await update.message.reply_text(reply_text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, application.bot)
        
        async def process():
            await application.initialize()
            await application.process_update(update)
            
        asyncio.run(process())
    except Exception as e:
        logging.error(f"Error crítico en webhook: {e}")
        return "Internal Error", 500
    return "OK", 200

@app.route("/")
def index():
    return "GEMAXBOT Webhook Server is active!"

def setup_webhook():
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}/{TOKEN}"
        asyncio.run(application.bot.set_webhook(url=webhook_url))
        logging.info(f"Webhook configurado automáticamente en: {webhook_url}")

if __name__ == "__main__":
    setup_webhook()
    app.run(host="0.0.0.0", port=PORT)

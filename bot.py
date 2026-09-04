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

# Configuración de la librería clásica y estable
genai.configure(api_key=API_KEY)

generation_config = {
    "temperature": 0.4,
    "max_output_tokens": 1500,
}

system_instruction = (
    "Te llamas GEMAXBOT y eres un asistente experto en criptomonedas, blockchain y mercados financieros para Telegram. "
    "REGLA CRÍTICA: Responde siempre de forma directa a la pregunta del usuario. "
    "PROHIBIDO dar saludos genéricos, presentaciones largas ni decir 'Soy GEMAXBOT' a menos que el usuario escriba explícitamente /start o pregunte quién eres. "
    "Ve directo al análisis o respuesta solicitada de forma clara, profesional y concisa (máximo 3 párrafos o viñetas)."
)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=system_instruction
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

    if any(m.id == context.bot.id for m in (update.message.new_chat_members or [])):
        welcome_text = (
            "¡Hola a todos! Soy **GEMAXBOT**, su asistente experto en criptomonedas y mercados financieros. "
            "Estoy aquí 24/7 para resolver sus dudas sobre análisis técnico, tendencias, tokens y economía digital."
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
        return

    if chat_type in ["group", "supergroup"]:
        is_mentioned = f"@{bot_username}" in user_message
        is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        
        if not (is_mentioned or is_reply):
            return
            
        user_message = user_message.replace(f"@{bot_username}", "").strip()

    try:
        # Ejecutamos la consulta de forma segura en un hilo secundario
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, 
            lambda: model.generate_content(user_message)
        )
        reply_text = response.text
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error detallado de IA: {error_msg}")
        reply_text = f"Error al procesar la solicitud. Verifica que tu GEMINI_API_KEY sea válida."

    await update.message.reply_text(reply_text)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    
    async def process():
        await application.initialize()
        await application.process_update(update)
        
    asyncio.run(process())
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

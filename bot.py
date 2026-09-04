import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, CommandHandler, filters
from google import genai

# Configurar logs detallados
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.environ.get('PORT', 10000))
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

# Inicializar cliente de Google GenAI de forma segura
if not API_KEY:
    logging.error("¡FALTA LA VARIABLE DE ENTORNO GEMINI_API_KEY!")

client = genai.Client(api_key=API_KEY)

SYSTEM_INSTRUCTION = (
    "Te llamas GEMAXBOT. Eres un asistente experto en criptomonedas, blockchain y mercados financieros "
    "para una comunidad de Telegram. "
    "Tu lenguaje debe ser sencillo, claro, directo y profesional (evita tecnicismos excesivos "
    "a menos que los expliques brevemente). "
    "Tus respuestas deben ser precisas, al grano y no muy extendidas (máximo 2 o 3 párrafos cortos o viñetas) "
    "para no saturar el chat del grupo."
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
        # Llamada directa al modelo Gemini 2.5 Flash
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=user_message,
            config={
                'system_instruction': SYSTEM_INSTRUCTION,
                'max_output_tokens': 300,
                'temperature': 0.4,
            }
        )
        reply_text = response.text
    except Exception as e:
        # Esto imprimirá el error real en los Logs de Render para saber qué ocurre exactamente
        logging.error(f"DETALLE DEL ERROR DE IA: {str(e)}")
        reply_text = f"Error técnico al conectar con Gemini: {str(e)}"

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
          

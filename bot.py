import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Servidor Flask mínimo para satisfacer el puerto web gratuito de Render
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "GEMAXBOT está activo 24/7."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# Inicializar Gemini y Telegram
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = (
    "Te llamas GEMAXBOT. Eres un asistente experto en criptomonedas, blockchain y mercados financieros "
    "para una comunidad de Telegram. "
    "Tu lenguaje debe ser sencillo, claro, directo y profesional (evita tecnicismos excesivos "
    "a menos que los expliques brevemente). "
    "Tus respuestas deben ser precisas, al grano y no muy extendidas (máximo 2 o 3 párrafos cortos o viñetas) "
    "para no saturar el chat del grupo."
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
            "Estoy aquí 24/7 para resolver sus dudas sobre análisis técnico, tendencias, tokens y economía digital. "
            "¡Pregúntenme lo que necesiten mencionándome!"
        )
        await update.message.reply_text(welcome_text, parse_mode="Markdown")
        return

    if chat_type in ["group", "supergroup"]:
        is_mentioned = f"@{bot_username}" in user_message
        is_reply = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id
        
        if user_message.strip().lower() in [f"@{bot_username.lower()}", "gemaxbot", "hola gemaxbot"]:
            await update.message.reply_text(
                "¡Hola! Soy **GEMAXBOT**, tu asistente de criptomonedas y mercados. ¿En qué puedo ayudarte hoy?",
                parse_mode="Markdown"
            )
            return

        if not (is_mentioned or is_reply):
            return
            
        user_message = user_message.replace(f"@{bot_username}", "").strip()

    try:
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
        logging.error(f"Error al generar respuesta con IA: {e}")
        reply_text = "En este momento tengo problemas para procesar tu consulta financiera. Inténtalo de nuevo en unos segundos."

    await update.message.reply_text(reply_text)

def main():
    # Iniciar Flask en segundo plano para abrir el puerto web de Render
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        raise ValueError("Falta la variable de entorno TELEGRAM_BOT_TOKEN")

    application = ApplicationBuilder().token(telegram_token).build()
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    application.add_handler(message_handler)

    print("GEMAXBOT iniciado correctamente...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

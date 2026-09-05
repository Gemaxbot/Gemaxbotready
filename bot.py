import os
import logging
from flask import Flask, request
from telegram import Bot
from google import genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.environ.get('PORT', 10000))
API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

bot = Bot(token=TOKEN)
client = genai.Client(api_key=API_KEY)

SYSTEM_INSTRUCTION = (
    "Te llamas GEMAXBOT y eres un asistente experto en criptomonedas, blockchain y mercados financieros para Telegram. "
    "REGLA CRÍTICA: Responde siempre de forma directa a la pregunta del usuario. "
    "PROHIBIDO dar saludos genéricos, presentaciones largas ni decir 'Soy GEMAXBOT' a menos que el usuario escriba explícitamente /start o pregunte quién eres. "
    "Ve directo al análisis o respuesta solicitada de forma clara, profesional y concisa (máximo 3 párrafos o viñetas)."
)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    # ESTO DEBE IMPRIMIRSE EN LOS LOGS DE RENDER SI TELEGRAM LLEGA AQUÍ
    logging.info("¡ALERTA: PETICIÓN RECIBIDA DE TELEGRAM!")
    try:
        json_data = request.get_json(force=True)
        logging.info(f"Contenido del mensaje: {json_data}")
        
        chat_id = json_data.get("message", {}).get("chat", {}).get("id")
        user_message = json_data.get("message", {}).get("text", "")

        if not chat_id or not user_message:
            return "OK", 200

        if user_message.strip() == "/start":
            bot.send_message(
                chat_id=chat_id,
                text="¡Hola! Soy **GEMAXBOT**, tu asistente experto en criptomonedas y mercados financieros. ¿En qué puedo ayudarte hoy?",
                parse_mode="Markdown"
            )
            return "OK", 200

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_message,
            config={
                "system_instruction": SYSTEM_INSTRUCTION,
                "temperature": 0.4,
                "max_output_tokens": 1500,
            }
        )
        reply_text = response.text
        bot.send_message(chat_id=chat_id, text=reply_text)

    except Exception as e:
        logging.error(f"Error crítico en webhook: {e}")
    
    return "OK", 200

@app.route("/")
def index():
    return "GEMAXBOT Webhook Server is active!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)

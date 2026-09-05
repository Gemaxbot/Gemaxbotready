import os
import logging
import json
import time
import urllib.request
from flask import Flask, request
from google import genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PORT = int(os.environ.get('PORT', 10000))
API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)
client = genai.Client(api_key=API_KEY)

# Control básico anti-spam por usuario (última consulta en segundos)
user_cooldowns = {}
COOLDOWN_TIME = 4

SYSTEM_INSTRUCTION = (
    "Te llamas GEMAXBOT y eres un asistente experto en criptomonedas, blockchain y mercados financieros para Telegram. "
    "REGLA CRÍTICA: Responde siempre de forma directa a la pregunta del usuario. "
    "PROHIBIDO dar saludos genéricos, presentaciones largas ni decir 'Soy GEMAXBOT' a menos que el usuario escriba explícitamente /start o pregunte quién eres. "
    "Ve directo al análisis o respuesta solicitada de forma clara, profesional y concisa (máximo 3 párrafos o viñetas)."
)

def send_telegram_message(chat_id, text, parse_mode=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    except Exception as e:
        logging.error(f"Error enviando mensaje a Telegram: {e}")

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    try:
        json_data = request.get_json(force=True)
        
        message = json_data.get("message") or json_data.get("edited_message")
        if not message:
            return "OK", 200
            
        chat_id = message.get("chat", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        user_id = message.get("from", {}).get("id")
        user_message = message.get("text", "")

        if not chat_id or not user_message:
            return "OK", 200

        if user_message.strip() == "/start":
            send_telegram_message(
                chat_id,
                "¡Hola! Soy **GEMAXBOT**, tu asistente experto en criptomonedas y mercados financieros. ¿En qué puedo ayudarte hoy?",
                parse_mode="Markdown"
            )
            return "OK", 200

        # FILTRO ESTRICTO PARA GRUPOS: Solo procesar si lo mencionan o le responden directamente
        if chat_type in ["group", "supergroup"]:
            is_reply_to_bot = False
            if "reply_to_message" in message:
                reply_from = message["reply_to_message"].get("from", {})
                # Si el mensaje respondido es del bot, permitimos la interacción
                if reply_from.get("is_bot") and reply_from.get("username") and "gemax" in reply_from.get("username").lower():
                    is_reply_to_bot = True

            # Comprobamos si incluye mención o si es respuesta directa al bot
            bot_mentioned = "@gemax" in user_message.lower() or is_reply_to_bot
            if not bot_mentioned:
                return "OK", 200

        # Control de Cooldown por usuario (Anti-spam)
        current_time = time.time()
        if user_id in user_cooldowns and (current_time - user_cooldowns[user_id] < COOLDOWN_TIME):
            return "OK", 200
        user_cooldowns[user_id] = current_time

        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=user_message,
                config={
                    "system_instruction": SYSTEM_INSTRUCTION,
                    "temperature": 0.4,
                    "max_output_tokens": 1500,
                }
            )
            reply_text = response.text
        except Exception as api_err:
            logging.error(f"Error en Gemini API: {api_err}")
            if "429" in str(api_err):
                reply_text = "⏳ Se ha alcanzado temporalmente el límite de consultas de la API gratuita. Inténtalo de nuevo en unos segundos."
            else:
                reply_text = "⚠️ Ocurrió un error temporal al procesar tu análisis financiero."

        send_telegram_message(chat_id, reply_text)

    except Exception as e:
        logging.error(f"Error procesando el webhook: {e}")
    
    return "OK", 200

@app.route("/")
def index():
    return "GEMAXBOT Webhook Server is active!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
    

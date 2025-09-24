import os
from dotenv import load_dotenv

# Завантаження змінних середовища з .env файлу
load_dotenv()

# Конфігурація бота
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Налаштування логування
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Налаштування бота
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID', '')

# Налаштування aiogram
PARSE_MODE = 'HTML'  # Режим парсингу повідомлень
DISABLE_WEB_PAGE_PREVIEW = True  # Відключити попередній перегляд веб-сторінок

# Налаштування webhook
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'localhost')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8080'))
WEBHOOK_PATH = os.getenv('WEBHOOK_PATH', '/webhook')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', f'https://{WEBHOOK_HOST}')

# Налаштування ngrok
NGROK_AUTH_TOKEN = os.getenv('NGROK_AUTH_TOKEN', '')  # Отримайте з https://dashboard.ngrok.com/get-started/your-authtoken
NGROK_REGION = os.getenv('NGROK_REGION', 'us')  # us, eu, ap, au, sa, jp, in

# Налаштування OpenAI
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')  # Отримайте з https://platform.openai.com/api-keys
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')  # Модель для генерації тексту
OPENAI_MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '1000'))  # Максимальна кількість токенів
OPENAI_TEMPERATURE = float(os.getenv('OPENAI_TEMPERATURE', '0.7'))  # Температура для генерації

# Налаштування OpenAI для TTS (озвучка)
OPENAI_TTS_MODEL = os.getenv('OPENAI_TTS_MODEL', 'tts-1')  # Модель для генерації озвучки
OPENAI_TTS_VOICE = os.getenv('OPENAI_TTS_VOICE', 'alloy')  # Голос для озвучки (alloy, echo, fable, onyx, nova, shimmer)
OPENAI_TTS_SPEED = float(os.getenv('OPENAI_TTS_SPEED', '1.0'))  # Швидкість мовлення (0.25 - 4.0)

# Налаштування OpenAI для генерації зображень
OPENAI_IMAGE_MODEL = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-1')  # Модель для генерації зображень
OPENAI_IMAGE_SIZE = os.getenv('OPENAI_IMAGE_SIZE', 'auto')  # Розмір зображення (1024x1024, 1024x1536, 1536x1024, auto)
OPENAI_IMAGE_QUALITY = os.getenv('OPENAI_IMAGE_QUALITY', 'auto')  # Якість зображення (low, medium, high, auto)

# Перевірка наявності токенів
if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
    print("⚠️  УВАГА: Встановіть BOT_TOKEN у змінних середовища або .env файлі!")

if not OPENAI_API_KEY:
    print("⚠️  УВАГА: Встановіть OPENAI_API_KEY у змінних середовища або .env файлі!")

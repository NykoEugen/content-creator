import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config import BOT_TOKEN, LOG_LEVEL, WEBHOOK_PATH, WEBHOOK_URL

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL.upper())
)
logger = logging.getLogger(__name__)

# Ініціалізація бота та диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Функція 1: Привітання та інформація про бота"""
    user = message.from_user
    await message.answer(
        f"Привіт, {user.first_name}! 👋\n\n"
        f"Я простий телеграм бот з двома функціями (Webhook режим):\n"
        f"• /start - показати це привітання\n"
        f"• /help - допомога\n"
        f"• /echo - повторювати ваше повідомлення\n"
        f"• /info - інформація про бота",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Функція допомоги"""
    help_text = """
🤖 <b>Доступні команди:</b>

/start - Почати роботу з ботом
/help - Показати це повідомлення
/echo - Повторити ваше повідомлення
/info - Інформація про бота

Просто надішліть мені будь-яке повідомлення, і я його повторю!
    """
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("echo"))
async def echo_handler(message: Message) -> None:
    """Функція 2: Повторення повідомлення користувача"""
    # Отримуємо текст після команди /echo
    echo_text = message.text.replace('/echo', '').strip()
    if echo_text:
        await message.answer(f"Ви написали: {echo_text}")
    else:
        await message.answer("Напишіть щось після команди /echo")

@dp.message(Command("info"))
async def info_handler(message: Message) -> None:
    """Додаткова функція: Інформація про бота"""
    info_text = """
📊 <b>Інформація про бота:</b>

• Назва: Простий Telegram Bot
• Версія: 1.0
• Функції: 2 основні
• Мова: Python
• Бібліотека: aiogram 3.13
• Режим: Webhook (ngrok)

Цей бот демонструє базову функціональність:
1. Привітання користувачів
2. Повторення повідомлень
    """
    await message.answer(info_text, parse_mode="HTML")

@dp.message(F.text)
async def handle_message(message: Message) -> None:
    """Обробка звичайних повідомлень (не команд)"""
    user_message = message.text
    await message.answer(f"🔔 Ви написали: {user_message}")

async def on_startup(bot: Bot) -> None:
    """Функція запуску webhook"""
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook встановлено: {webhook_url}")

async def on_shutdown(bot: Bot) -> None:
    """Функція зупинки webhook"""
    await bot.delete_webhook()
    logger.info("🛑 Webhook видалено")

def create_app() -> web.Application:
    """Створення FastAPI додатку для webhook"""
    app = web.Application()
    
    # Налаштування webhook
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Налаштування додатку
    setup_application(app, dp, bot=bot)
    
    return app

async def main() -> None:
    """Основна функція запуску webhook"""
    logger.info("🤖 Бот запускається в webhook режимі...")
    
    # Перевірка токена
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ Встановіть BOT_TOKEN у змінних середовища або .env файлі!")
        return
    
    # Налаштування webhook
    await on_startup(bot)
    
    # Створення додатку
    app = create_app()
    
    # Запуск сервера
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    
    logger.info("🌐 Webhook сервер запущено на http://localhost:8080")
    logger.info(f"📡 Webhook URL: {WEBHOOK_URL}{WEBHOOK_PATH}")
    
    try:
        # Очікування сигналу зупинки
        await asyncio.Future()  # Запуск на невизначений час
    except KeyboardInterrupt:
        logger.info("🛑 Отримано сигнал зупинки...")
    finally:
        await on_shutdown(bot)
        await runner.cleanup()
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот зупинено користувачем")
    except Exception as e:
        logger.error(f"❌ Критична помилка: {e}")

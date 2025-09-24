import asyncio
import logging
import threading
import time
from pyngrok import ngrok, conf
from config import BOT_TOKEN, WEBHOOK_PORT, WEBHOOK_PATH, NGROK_AUTH_TOKEN, NGROK_REGION, LOG_LEVEL

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL.upper())
)
logger = logging.getLogger(__name__)

def setup_ngrok():
    """Налаштування ngrok туннелю"""
    try:
        # Встановлення auth token якщо він є
        if NGROK_AUTH_TOKEN:
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)
            logger.info("✅ Ngrok auth token встановлено")
        
        # Налаштування регіону
        conf.get_default().region = NGROK_REGION
        logger.info(f"🌍 Ngrok регіон: {NGROK_REGION}")
        
        # Створення туннелю
        tunnel = ngrok.connect(WEBHOOK_PORT, "http")
        public_url = tunnel.public_url
        logger.info(f"🚇 Ngrok туннель створено: {public_url}")
        
        return public_url
        
    except Exception as e:
        logger.error(f"❌ Помилка створення ngrok туннелю: {e}")
        return None

def cleanup_ngrok():
    """Очищення ngrok туннелів"""
    try:
        ngrok.disconnect(ngrok.get_tunnels())
        ngrok.kill()
        logger.info("🧹 Ngrok туннелі очищено")
    except Exception as e:
        logger.error(f"❌ Помилка очищення ngrok: {e}")

async def start_webhook_bot(webhook_url):
    """Запуск бота з webhook"""
    try:
        # Імпорт webhook handler
        from webhook_handler import main as webhook_main
        
        # Оновлення WEBHOOK_URL в конфігурації
        import os
        os.environ['WEBHOOK_URL'] = webhook_url
        
        logger.info(f"🌐 Запуск webhook бота з URL: {webhook_url}")
        await webhook_main()
        
    except Exception as e:
        logger.error(f"❌ Помилка запуску webhook бота: {e}")

def main():
    """Основна функція запуску"""
    logger.info("🤖 Запуск бота з ngrok webhook...")
    
    # Перевірка токена
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ Встановіть BOT_TOKEN у змінних середовища або .env файлі!")
        return
    
    # Налаштування ngrok
    webhook_url = setup_ngrok()
    if not webhook_url:
        logger.error("❌ Не вдалося створити ngrok туннель!")
        return
    
    # Додавання шляху webhook до URL
    full_webhook_url = f"{webhook_url}{WEBHOOK_PATH}"
    logger.info(f"📡 Повний webhook URL: {full_webhook_url}")
    
    try:
        # Запуск бота
        asyncio.run(start_webhook_bot(full_webhook_url))
    except KeyboardInterrupt:
        logger.info("🛑 Отримано сигнал зупинки...")
    except Exception as e:
        logger.error(f"❌ Критична помилка: {e}")
    finally:
        # Очищення ngrok
        cleanup_ngrok()
        logger.info("👋 Бот зупинено")

if __name__ == '__main__':
    main()

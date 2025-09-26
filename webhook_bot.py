import asyncio
import logging
import os
import re
from typing import Optional

from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InputMediaPhoto
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from aiohttp import ClientTimeout, TCPConnector
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, LOG_LEVEL, OPENAI_API_KEY, WEBHOOK_PATH, WEBHOOK_URL
from openai_service import get_openai_service
from openai_tts_service import get_openai_tts_service
from openai_image_service import get_openai_image_service

# Налаштування логування
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper()),
)
logger = logging.getLogger(__name__)

# ---------- Ініціалізація бота з сесією (таймаути + keep-alive) ----------

_session = AiohttpSession(
    timeout=ClientTimeout(total=None, connect=10, sock_read=180)
)
bot = Bot(token=BOT_TOKEN, session=_session)
dp = Dispatcher()

# Стани для FSM
class UserStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_creative_prompt = State()
    waiting_for_code_prompt = State()
    waiting_for_translate_text = State()
    waiting_for_summarize_text = State()
    waiting_for_explain_concept = State()
    waiting_for_tts_text = State()
    waiting_for_image_prompt = State()
    # Стани для налаштувань
    waiting_for_voice_setting = State()
    waiting_for_speed_setting = State()
    waiting_for_image_size_setting = State()
    waiting_for_image_quality_setting = State()


# Словник для зберігання налаштувань користувачів
user_settings = {}


def sanitize_telegram_text(text: str) -> str:
    """
    Очищає текст від невалідних HTML тегів для Telegram
    """
    if not text:
        return text
    text = re.sub(r"<[^>]*>", "", text)  # прибрати теги
    text = re.sub(r"&[a-zA-Z0-9#]+;", "", text)  # прибрати entities
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def safe_edit_message(
    callback: CallbackQuery,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    max_retries: int = 3,
) -> bool:
    """
    Безпечне редагування повідомлення з миттєвим ACK, ретраями та fallback у нове повідомлення.
    """
    # 0) миттєво ACK, щоб не ловити "query is too old"
    try:
        await callback.answer()
    except Exception:
        pass

    # 1) намагаємось відредагувати (швидко)
    for attempt in range(max_retries):
        try:
            await callback.message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            return True
        except TelegramBadRequest as e:
            msg = str(e)
            # Якщо контент не змінився — вважаємо успіхом
            if "message is not modified" in msg:
                return True
            # Якщо редагувати вже не можна — відправляємо нове повідомлення
            if "query is too old" in msg or "message to edit not found" in msg:
                try:
                    await callback.message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
                    return True
                except Exception as inner_e:
                    logger.error(f"Fallback send_message failed: {inner_e}")
                    return False
            # Інші помилки — підняти вище, або повторити
            if attempt == max_retries - 1:
                logger.error(f"safe_edit_message TelegramBadRequest: {e}")
                try:
                    await callback.message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
                    return True
                except Exception as inner_e:
                    logger.error(f"Fallback send_message failed: {inner_e}")
                    return False
        except TelegramNetworkError as e:
            # Сітка впала — трохи зачекати й повторити
            await asyncio.sleep(0.7 * (attempt + 1))
            if attempt == max_retries - 1:
                logger.error(f"safe_edit_message TelegramNetworkError: {e}")
                try:
                    await callback.message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
                    return True
                except Exception as inner_e:
                    logger.error(f"Fallback send_message failed: {inner_e}")
                    return False
        except Exception as e:
            logger.warning(f"Спроба {attempt + 1} редагування не вдалася: {e}")
            await asyncio.sleep(0.7 * (attempt + 1))

    return False


async def safe_edit_message_text(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    max_attempts: int = 3,
):
    attempt = 0
    while attempt < max_attempts:
        try:
            return await bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup
            )
        except TelegramBadRequest as e:
            msg = str(e)
            if "message is not modified" in msg:
                return
            if "query is too old" in msg or "message to edit not found" in msg:
                return await bot.send_message(chat_id, text, reply_markup=reply_markup)
            raise
        except TelegramNetworkError:
            attempt += 1
            await asyncio.sleep(0.7 * attempt)

async def send_photo_with_retry(chat_id: int, photo: BufferedInputFile, caption: str = None, parse_mode: str = "HTML", max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode=parse_mode)
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)

async def send_media_group_with_retry(chat_id: int, media: list[InputMediaPhoto], max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await bot.send_media_group(chat_id, media=media)
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)

# ---------- Ретраї для відправок/редагувань/войсів/медіа ----------
async def send_message_with_retry(chat_id: int, text: str, parse_mode: str = "HTML", reply_markup=None, max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)

async def edit_message_with_retry(chat_id: int, message_id: int, text: str, parse_mode: str = "HTML", reply_markup=None, max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup)
        except TelegramBadRequest as e:
            msg = str(e)
            if "message is not modified" in msg:
                return
            if "query is too old" in msg or "message to edit not found" in msg:
                return await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=reply_markup)
            raise
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)

async def delete_message_silent(chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        pass

async def send_voice_with_retry(chat_id: int, voice_bytes: bytes, caption: str = None, parse_mode: str = "HTML", filename: str = "speech.mp3", max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            audio_input = types.BufferedInputFile(file=voice_bytes, filename=filename)
            return await bot.send_voice(chat_id, voice=audio_input, caption=caption, parse_mode=parse_mode)
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)

async def send_photo_with_retry(chat_id: int, photo: BufferedInputFile, caption: str = None, parse_mode: str = "HTML", max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await bot.send_photo(chat_id, photo=photo, caption=caption, parse_mode=parse_mode)
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)

async def send_media_group_with_retry(chat_id: int, media: list[InputMediaPhoto], max_attempts: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            return await bot.send_media_group(chat_id, media=media)
        except TelegramRetryAfter as e:
            await asyncio.sleep(int(getattr(e, "retry_after", 1)))
        except TelegramNetworkError:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(0.7 * attempt)
# -------------------------------------------------------------------
# ---------- Хелпер для безпечного отримання списку голосів/діапазону швидкості ----------
async def _tts_hint(tts_service) -> str:
    """Повертає коротку підказку з голосами/швидкістю. Безпечна до збоїв."""
    try:
        voices = await tts_service.get_available_voices()
    except Exception:
        voices = []

    try:
        speed_range = await tts_service.get_speed_range()
    except Exception:
        speed_range = (0.25, 4.0)

    voices_txt = ", ".join(map(str, voices)) if voices else "alloy, echo, fable, onyx, nova, shimmer"
    return (
        f"\n\n<b>Доступні голоси:</b> {voices_txt}"
        f"\n<b>Діапазон швидкості:</b> {speed_range[0]}x – {speed_range[1]}x (1.0 = нормальна)"
    )
# ---------------------------------------------------------------------------------------

def get_user_settings(user_id: int) -> dict:
    """Отримання налаштувань користувача"""
    if user_id not in user_settings:
        user_settings[user_id] = {
            "voice": "alloy",
            "speed": 1.0,
            "image_size": "auto",
            "image_quality": "auto",
        }
    return user_settings[user_id]


def update_user_setting(user_id: int, setting: str, value) -> None:
    """Оновлення налаштування користувача"""
    if user_id not in user_settings:
        get_user_settings(user_id)
    user_settings[user_id][setting] = value


def get_main_menu() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 Запитати AI", callback_data="ask_ai"),
                InlineKeyboardButton(text="✨ Креативне письмо", callback_data="creative"),
            ],
            [
                InlineKeyboardButton(text="💻 Генерація коду", callback_data="code"),
                InlineKeyboardButton(text="🌐 Переклад", callback_data="translate"),
            ],
            [
                InlineKeyboardButton(text="📝 Резюме тексту", callback_data="summarize"),
                InlineKeyboardButton(text="💡 Пояснення", callback_data="explain"),
            ],
            [
                InlineKeyboardButton(text="🎤 Озвучка (TTS)", callback_data="tts"),
                InlineKeyboardButton(text="🖼️ Генерація зображень", callback_data="image"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Налаштування", callback_data="settings"),
                InlineKeyboardButton(text="ℹ️ Допомога", callback_data="help"),
            ],
            [InlineKeyboardButton(text="📊 Інформація", callback_data="info")],
        ]
    )
    return keyboard


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Назад до меню", callback_data="back_to_menu")]])


def get_settings_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎤 Голос TTS", callback_data="settings_voice"),
                InlineKeyboardButton(text="⚡ Швидкість TTS", callback_data="settings_speed"),
            ],
            [
                InlineKeyboardButton(text="📐 Розмір зображення", callback_data="settings_image_size"),
                InlineKeyboardButton(text="🎨 Якість зображення", callback_data="settings_image_quality"),
            ],
            [InlineKeyboardButton(text="🏠 Назад до меню", callback_data="back_to_menu")],
        ]
    )
    return keyboard


def get_voice_selection_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎵 Alloy", callback_data="voice_alloy"),
                InlineKeyboardButton(text="🔊 Echo", callback_data="voice_echo"),
            ],
            [
                InlineKeyboardButton(text="📚 Fable", callback_data="voice_fable"),
                InlineKeyboardButton(text="💎 Onyx", callback_data="voice_onyx"),
            ],
            [
                InlineKeyboardButton(text="⭐ Nova", callback_data="voice_nova"),
                InlineKeyboardButton(text="✨ Shimmer", callback_data="voice_shimmer"),
            ],
            [InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")],
        ]
    )
    return keyboard


def get_speed_selection_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🐌 0.5x", callback_data="speed_0.5"),
                InlineKeyboardButton(text="🚶 0.75x", callback_data="speed_0.75"),
            ],
            [
                InlineKeyboardButton(text="🚶‍♂️ 1.0x", callback_data="speed_1.0"),
                InlineKeyboardButton(text="🏃 1.25x", callback_data="speed_1.25"),
            ],
            [
                InlineKeyboardButton(text="🏃‍♂️ 1.5x", callback_data="speed_1.5"),
                InlineKeyboardButton(text="🚀 2.0x", callback_data="speed_2.0"),
            ],
            [InlineKeyboardButton(text="✏️ Ввести власну", callback_data="speed_custom")],
            [InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")],
        ]
    )
    return keyboard


def get_image_size_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📱 1024x1024", callback_data="size_1024x1024"),
                InlineKeyboardButton(text="📄 1024x1536", callback_data="size_1024x1536"),
            ],
            [
                InlineKeyboardButton(text="🖥️ 1536x1024", callback_data="size_1536x1024"),
                InlineKeyboardButton(text="🤖 Auto", callback_data="size_auto"),
            ],
            [InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")],
        ]
    )
    return keyboard


def get_image_quality_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔧 Low", callback_data="quality_low"),
                InlineKeyboardButton(text="⚖️ Medium", callback_data="quality_medium"),
            ],
            [
                InlineKeyboardButton(text="🎨 High", callback_data="quality_high"),
                InlineKeyboardButton(text="🤖 Auto", callback_data="quality_auto"),
            ],
            [InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")],
        ]
    )
    return keyboard


# ===================== Команди =====================
@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    user = message.from_user
    openai_status = "✅ Підключено" if OPENAI_API_KEY else "❌ Не підключено"
    welcome_text = (
        f"Привіт, {user.first_name}! 👋\n\n"
        f"Я розумний телеграм бот з функціями OpenAI.\n"
        f"Оберіть функцію з меню нижче:\n\n"
        f"OpenAI: {openai_status}"
    )
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_main_menu())


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    help_text = """
🤖 <b>Доступні команди:</b>

<b>Основні команди:</b>
/start - Почати роботу з ботом (показати меню)
/help - Показати це повідомлення
/echo - Повторити ваше повідомлення
/info - Інформація про бота

<b>OpenAI функції:</b>
/ask - Запитати щось у AI (наприклад: /ask Що таке штучний інтелект?)
/creative - Креативне письмо (наприклад: /creative Напиши вірш про зиму)
/code - Генерація коду (наприклад: /code Створи функцію сортування)
/translate - Переклад тексту (наприклад: /translate Hello world)
/summarize - Резюме тексту (наприклад: /summarize [ваш довгий текст])
/explain - Пояснення концепції (наприклад: /explain Що таке машинне навчання?)
/tts - Озвучити текст з налаштуваннями (наприклад: /tts Привіт! | alloy | 1.5)
/tts_settings - Показати налаштування TTS та приклади використання
/image - Згенерувати зображення (наприклад: /image Кіт, що грає з м'ячем)

<b>Нове інтерактивне меню:</b>
Використовуйте /start для доступу до зручного меню з кнопками!

Просто надішліть мені будь-яке повідомлення, і я його повторю!
    """
    await message.answer(help_text, parse_mode="HTML", reply_markup=get_back_to_menu_keyboard())


@dp.message(Command("echo"))
async def echo_handler(message: Message) -> None:
    echo_text = message.text.replace("/echo", "").strip()
    if echo_text:
        await message.answer(f"Ви написали: {echo_text}")
    else:
        await message.answer("Напишіть щось після команди /echo")


@dp.message(Command("info"))
async def info_handler(message: Message) -> None:
    openai_status = "✅ Підключено" if OPENAI_API_KEY else "❌ Не підключено"
    info_text = f"""
📊 <b>Інформація про бота:</b>

• Назва: Розумний Telegram Bot з OpenAI
• Версія: 2.0
• Основні функції: 4 команди
• OpenAI функції: 9 команд
• Мова: Python
• Бібліотека: aiogram 3.13
• OpenAI: {openai_status}

<b>Цей бот надає:</b>
1. Базову функціональність (привітання, повторення)
2. Інтеграцію з OpenAI для розумних відповідей
3. Креативне письмо та генерацію коду
4. Переклад та резюмування тексту
5. Пояснення складних концепцій
6. Генерацію озвучки (TTS)
7. Генерацію зображень (DALL-E)
    """
    await message.answer(info_text, parse_mode="HTML")


# ---------- OpenAI команди ----------
@dp.message(Command("ask"))
async def ask_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    question = message.text.replace("/ask", "").strip()
    if not question:
        await message.answer("Напишіть ваш запит після команди /ask\nНаприклад: /ask Що таке штучний інтелект?")
        return

    try:
        thinking_msg = await message.answer("🤔 Думаю...")
        openai_service = get_openai_service()
        response = await openai_service.generate_text(question)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"🧠 <b>Відповідь:</b>\n\n{sanitized_response}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка в команді /ask: {e}", exc_info=True)
        await message.answer(f"❌ Виникла помилка при обробці запиту: {str(e)}")


@dp.message(Command("creative"))
async def creative_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    prompt = message.text.replace("/creative", "").strip()
    if not prompt:
        await message.answer(
            "Напишіть тему для креативного письма після команди /creative\nНаприклад: /creative Напиши вірш про зиму"
        )
        return

    try:
        thinking_msg = await message.answer("🎨 Створюю...")
        openai_service = get_openai_service()
        response = await openai_service.generate_creative_text(prompt)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"✨ <b>Креативний текст:</b>\n\n{sanitized_response}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка в команді /creative: {e}")
        await message.answer(f"❌ Виникла помилка при створенні тексту: {str(e)}")


@dp.message(Command("code"))
async def code_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    prompt = message.text.replace("/code", "").strip()
    if not prompt:
        await message.answer(
            "Опишіть код, який потрібно згенерувати після команди /code\nНаприклад: /code Створи функцію сортування масиву"
        )
        return

    try:
        thinking_msg = await message.answer("💻 Генерую код...")
        openai_service = get_openai_service()
        response = await openai_service.generate_code(prompt)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"🔧 <b>Згенерований код:</b>\n\n<code>{sanitized_response}</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка в команді /code: {e}")
        await message.answer(f"❌ Виникла помилка при генерації коду: {str(e)}")


@dp.message(Command("translate"))
async def translate_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    text = message.text.replace("/translate", "").strip()
    if not text:
        await message.answer("Напишіть текст для перекладу після команди /translate\nНаприклад: /translate Hello world")
        return

    try:
        thinking_msg = await message.answer("🌐 Перекладаю...")
        openai_service = get_openai_service()
        response = await openai_service.translate_text(text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"🔄 <b>Переклад:</b>\n\n{sanitized_response}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка в команді /translate: {e}")
        await message.answer(f"❌ Виникла помилка при перекладі: {str(e)}")


@dp.message(Command("summarize"))
async def summarize_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    text = message.text.replace("/summarize", "").strip()
    if not text:
        await message.answer("Надішліть текст для резюмування після команди /summarize\nНаприклад: /summarize [ваш довгий текст]")
        return

    try:
        thinking_msg = await message.answer("📝 Створюю резюме...")
        openai_service = get_openai_service()
        response = await openai_service.summarize_text(text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"📋 <b>Резюме:</b>\n\n{sanitized_response}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка в команді /summarize: {e}")
        await message.answer(f"❌ Виникла помилка при створенні резюме: {str(e)}")


@dp.message(Command("explain"))
async def explain_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    concept = message.text.replace("/explain", "").strip()
    if not concept:
        await message.answer("Напишіть концепцію для пояснення після команди /explain\nНаприклад: /explain Що таке машинне навчання?")
        return

    try:
        thinking_msg = await message.answer("💡 Пояснюю...")
        openai_service = get_openai_service()
        response = await openai_service.explain_concept(concept)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"🎓 <b>Пояснення:</b>\n\n{sanitized_response}", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Помилка в команді /explain: {e}")
        await message.answer(f"❌ Виникла помилка при поясненні: {str(e)}")


@dp.message(Command("tts"))
async def tts_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    command_text = message.text.replace('/tts', '').strip()
    if not command_text:
        await message.answer(
            "🎤 <b>Озвучка тексту</b>\n\n"
            "Використання:\n"
            "• <code>/tts Привіт, як справи?</code>\n"
            "• <code>/tts Привіт | 1.5</code>\n"
            "• <code>/tts Привіт | alloy | 1.5</code>\n\n"
            "Голоси: alloy, echo, fable, onyx, nova, shimmer\nШвидкість: 0.25–4.0",
            parse_mode="HTML"
        )
        return

    parts = command_text.split('|')
    text = parts[0].strip()
    if not text:
        await message.answer("❌ Введіть текст для озвучування")
        return

    voice = None
    speed = None
    if len(parts) >= 2:
        voice = parts[1].strip()
    if len(parts) >= 3:
        try:
            speed = float(parts[2].strip())
        except ValueError:
            await message.answer("❌ Невірний формат швидкості. Використовуйте число (наприклад: 1.5)")
            return

    status = await send_message_with_retry(message.chat.id, "🎤 Генерую озвучку...")

    async def _worker():
        try:
            user_id = message.from_user.id
            settings = get_user_settings(user_id)
            final_voice = voice or settings['voice']
            final_speed = speed if speed is not None else settings['speed']

            tts_service = get_openai_tts_service()
            audio_data = await tts_service.generate_speech_with_validation(text, final_voice, final_speed)

            caption_parts = [f"🔊 <b>Озвучка:</b> {sanitize_telegram_text(text)[:800]}",
                             f"Голос: {final_voice}",
                             f"Швидкість: {final_speed}x"]

            await send_voice_with_retry(
                chat_id=message.chat.id,
                voice_bytes=audio_data,
                caption="\n".join(caption_parts),
                parse_mode="HTML",
                filename="speech.mp3"
            )

            await edit_message_with_retry(
                message.chat.id, status.message_id,
                "✅ Озвучка готова!",
                reply_markup=get_back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"Помилка в /tts (фон): {e}")
            try:
                tts_service = get_openai_tts_service()
                hint = await _tts_hint(tts_service)   # ⬅️ ВАЖЛИВО: await
            except Exception:
                hint = ""
            await edit_message_with_retry(
                message.chat.id, status.message_id,
                f"❌ Виникла помилка при генерації озвучки: {str(e)}{hint}",
                reply_markup=get_back_to_menu_keyboard()
            )

    asyncio.create_task(_worker())


@dp.message(Command("tts_settings"))
async def tts_settings_handler(message: Message) -> None:
    """Команда для налаштувань TTS"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    try:
        tts_service = get_openai_tts_service()

        # ⬇️ ЦІ ДВА ВИКЛИКИ ПОТРІБНО AWAIT
        available_voices = await tts_service.get_available_voices()
        speed_range = await tts_service.get_speed_range()

        # Якщо в сервісі є ще поточні налаштування як корутини — теж await
        current_voice = getattr(tts_service, "voice", None)
        current_speed = getattr(tts_service, "speed", None)
        if callable(current_voice):
            current_voice = await current_voice()
        if callable(current_speed):
            current_speed = await current_speed()

        # Підстрахуємось на випадок, якщо сервіс повернув None
        available_voices = available_voices or []
        if not isinstance(available_voices, (list, tuple)):
            available_voices = list(available_voices)

        # Формуємо текст відповіді
        settings_text = (
            "🎤 <b>Налаштування TTS</b>\n\n"
            f"<b>Поточні налаштування:</b>\n"
            f"• Голос: <code>{current_voice or 'alloy'}</code>\n"
            f"• Швидкість: <code>{current_speed or 1.0}x</code>\n\n"
            f"<b>Доступні голоси:</b>\n{', '.join(map(str, available_voices)) or '—'}\n\n"
            f"<b>Діапазон швидкості:</b>\n"
            f"{(speed_range[0] if speed_range else 0.25)}x - {(speed_range[1] if speed_range else 4.0)}x (1.0 = нормальна)\n\n"
            "<b>Приклади використання:</b>\n"
            "• <code>/tts Привіт!</code>\n"
            "• <code>/tts Привіт! | 1.5</code>\n"
            "• <code>/tts Привіт! | nova</code>\n"
            "• <code>/tts Привіт! | echo | 0.8</code>\n"
        )

        await send_message_with_retry(message.chat.id, settings_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Помилка в команді /tts_settings: {e}")
        await send_message_with_retry(message.chat.id, f"❌ Виникла помилка при отриманні налаштувань: {str(e)}")


@dp.message(Command("image"))
async def image_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return

    prompt = message.text.replace('/image', '').strip()
    if not prompt:
        await message.answer("Опишіть зображення, яке потрібно згенерувати після команди /image\nНаприклад: /image Кіт, що грає з м'ячем")
        return

    # миттєвий ACK користувачу — і повертаємо контроль webhook'у
    status = await message.answer("🎨 Створюю 2 варіанти зображення… Це може зайняти до хвилини.")

    async def _worker():
        try:
            user_id = message.from_user.id
            settings = get_user_settings(user_id)
            image_service = get_openai_image_service()

            # Генеруємо 2 варіанти
            image_bytes_list = await image_service.generate_image(
                prompt,
                size=settings['image_size'],
                quality=settings['image_quality'],
                n=2
            )

            if not image_bytes_list:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=status.message_id,
                    text="❌ Не вдалося згенерувати зображення."
                )
                return

            # Якщо є 2 і більше — шлемо однією media_group (швидше і надійніше)
            if len(image_bytes_list) >= 2:
                media = []
                for i, image_bytes in enumerate(image_bytes_list[:2], 1):
                    media.append(
                        InputMediaPhoto(
                            media=BufferedInputFile(image_bytes, filename=f"generated_image_{i}.png"),
                            caption=(f"🖼️ <b>Варіант {i}</b>\n"
                                     f"Опис: {sanitize_telegram_text(prompt)[:800]}\n"
                                     f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}") if i == 1 else None,
                            parse_mode="HTML"
                        )
                    )
                await send_media_group_with_retry(message.chat.id, media)
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    "✅ Згенеровано 2 зображення.", reply_markup=get_back_to_menu_keyboard()
                )
            else:
                # один варіант — звичайна відправка
                photo_file = BufferedInputFile(image_bytes_list[0], filename="generated_image.png")
                await send_photo_with_retry(
                    chat_id=message.chat.id,
                    photo=photo_file,
                    caption=(f"🖼️ <b>Згенероване зображення</b>\n"
                             f"Опис: {sanitize_telegram_text(prompt)[:800]}\n"
                             f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}"),
                    parse_mode="HTML"
                )
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    "✅ Зображення згенеровано.", reply_markup=get_back_to_menu_keyboard()
                )

        except Exception as e:
            logger.error(f"Помилка в команді /image (фон): {e}")
            try:
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    f"❌ Виникла помилка при генерації зображення: {e}", reply_markup=get_back_to_menu_keyboard()
                )
            except Exception:
                pass

    asyncio.create_task(_worker())


@dp.message(Command("image_debug"))
async def image_debug_handler(message: Message) -> None:
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано.")
        return

    prompt = message.text.replace("/image_debug", "").strip() or "A simple red circle"

    try:
        await message.answer(f"🔍 <b>Діагностика генерації зображення</b>\n\nПромт: {prompt}", parse_mode="HTML")
        image_service = get_openai_image_service()

        settings_info = f"""
<b>Налаштування:</b>
• Модель: {image_service.model}
• Розмір: {image_service.default_size}
• Якість: {image_service.default_quality}
        """
        await message.answer(settings_info, parse_mode="HTML")

        await message.answer("🎨 Тестую генерацію...")
        image_bytes_list = await image_service.generate_image(prompt, n=1)

        debug_info = f"""
<b>Результат:</b>
• Кількість зображень: {len(image_bytes_list) if image_bytes_list else 0}
• Розмір першого зображення: {len(image_bytes_list[0]) if image_bytes_list and len(image_bytes_list) > 0 else 'None'} байт
        """
        await message.answer(debug_info, parse_mode="HTML")

        if image_bytes_list and len(image_bytes_list) > 0:
            image_bytes = image_bytes_list[0]
            photo_file = BufferedInputFile(image_bytes, filename="debug_image.png")
            await message.answer_photo(photo=photo_file, caption="✅ Тестове зображення", parse_mode="HTML")
        else:
            await message.answer("❌ Не отримано зображення")
    except Exception as e:
        logger.error(f"Помилка в команді /image_debug: {e}")
        await message.answer(f"❌ Помилка діагностики: {str(e)}")


# ===================== Callback'и (усі через safe_edit_message) =====================
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    openai_status = "✅ Підключено" if OPENAI_API_KEY else "❌ Не підключено"
    welcome_text = (
        f"Привіт, {callback.from_user.first_name}! 👋\n\n"
        f"Я розумний телеграм бот з функціями OpenAI.\n"
        f"Оберіть функцію з меню нижче:\n\n"
        f"OpenAI: {openai_status}"
    )
    await safe_edit_message(callback, welcome_text, "HTML", get_main_menu())


@dp.callback_query(F.data == "ask_ai")
async def ask_ai_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "🤖 <b>Запитати AI</b>\n\n"
        "Напишіть ваш запит, і я відповім на нього за допомогою штучного інтелекту.\n\n"
        "Приклад: Що таке машинне навчання?"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_text)


@dp.callback_query(F.data == "creative")
async def creative_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "✨ <b>Креативне письмо</b>\n\n"
        "Опишіть тему або жанр, і я створю креативний текст.\n\n"
        "Приклад: Напиши вірш про зиму"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_creative_prompt)


@dp.callback_query(F.data == "code")
async def code_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "💻 <b>Генерація коду</b>\n\n"
        "Опишіть, який код потрібно згенерувати.\n\n"
        "Приклад: Створи функцію сортування масиву"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_code_prompt)


@dp.callback_query(F.data == "translate")
async def translate_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "🌐 <b>Переклад тексту</b>\n\n"
        "Напишіть текст, який потрібно перекласти.\n\n"
        "Приклад: Hello world"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_translate_text)


@dp.callback_query(F.data == "summarize")
async def summarize_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "📝 <b>Резюме тексту</b>\n\n"
        "Надішліть текст, який потрібно резюмувати.\n\n"
        "Приклад: [ваш довгий текст]"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_summarize_text)


@dp.callback_query(F.data == "explain")
async def explain_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "💡 <b>Пояснення концепції</b>\n\n"
        "Напишіть концепцію або термін, який потрібно пояснити.\n\n"
        "Приклад: Що таке машинне навчання?"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_explain_concept)


@dp.callback_query(F.data == "tts")
async def tts_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "🎤 <b>Озвучка тексту</b>\n\n"
        "Напишіть текст для озвучування.\n\n"
        "Приклад: Привіт, як справи?"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_tts_text)


@dp.callback_query(F.data == "image")
async def image_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "🖼️ <b>Генерація зображення</b>\n\n"
        "Опишіть зображення, яке потрібно згенерувати.\n\n"
        "Приклад: Кіт, що грає з м'ячем"
    )
    success = await safe_edit_message(callback, text, "HTML", get_back_to_menu_keyboard())
    if success:
        await state.set_state(UserStates.waiting_for_image_prompt)


@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    help_text = """
🤖 <b>Доступні функції:</b>

<b>Основні функції:</b>
🤖 Запитати AI - запитати щось у штучного інтелекту
✨ Креативне письмо - створення креативних текстів
💻 Генерація коду - створення коду на різних мовах
🌐 Переклад - переклад тексту на різні мови
📝 Резюме тексту - створення коротких резюме
💡 Пояснення - пояснення складних концепцій
🎤 Озвучка (TTS) - перетворення тексту в мову
🖼️ Генерація зображень - створення зображень за описом

<b>Як користуватися:</b>
1. Натисніть на потрібну функцію в меню
2. Введіть текст згідно з інструкціями
3. Отримайте результат

<b>Команди:</b>
/start - головне меню
/help - ця допомога
    """
    await safe_edit_message(callback, help_text, "HTML", get_back_to_menu_keyboard())


@dp.callback_query(F.data == "info")
async def info_callback(callback: CallbackQuery):
    openai_status = "✅ Підключено" if OPENAI_API_KEY else "❌ Не підключено"
    info_text = f"""
📊 <b>Інформація про бота:</b>

• Назва: Розумний Telegram Bot з OpenAI
• Версія: 2.0
• Основні функції: 8 функцій
• Мова: Python
• Бібліотека: aiogram 3.13
• OpenAI: {openai_status}

<b>Цей бот надає:</b>
1. Інтеграцію з OpenAI для розумних відповідей
2. Креативне письмо та генерацію коду
3. Переклад та резюмування тексту
4. Пояснення складних концепцій
5. Генерацію озвучки (TTS)
6. Генерацію зображень (DALL-E)
    """
    await safe_edit_message(callback, info_text, "HTML", get_back_to_menu_keyboard())


@dp.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery):
    text = "⚙️ <b>Налаштування</b>\n\nОберіть параметр для зміни:"
    await safe_edit_message(callback, text, "HTML", get_settings_menu_keyboard())


@dp.callback_query(F.data == "settings_voice")
async def settings_voice_callback(callback: CallbackQuery):
    text = "🎤 <b>Налаштування голосу TTS</b>\n\nОберіть голос для озвучування:"
    await safe_edit_message(callback, text, "HTML", get_voice_selection_keyboard())


@dp.callback_query(F.data == "settings_speed")
async def settings_speed_callback(callback: CallbackQuery):
    text = "⚡ <b>Налаштування швидкості TTS</b>\n\nОберіть швидкість озвучування:"
    await safe_edit_message(callback, text, "HTML", get_speed_selection_keyboard())


@dp.callback_query(F.data == "settings_image_size")
async def settings_image_size_callback(callback: CallbackQuery):
    text = "📐 <b>Налаштування розміру зображення</b>\n\nОберіть розмір для генерації зображень:"
    await safe_edit_message(callback, text, "HTML", get_image_size_keyboard())


@dp.callback_query(F.data == "settings_image_quality")
async def settings_image_quality_callback(callback: CallbackQuery):
    text = "🎨 <b>Налаштування якості зображення</b>\n\nОберіть якість для генерації зображень:"
    await safe_edit_message(callback, text, "HTML", get_image_quality_keyboard())


@dp.callback_query(F.data.startswith("voice_"))
async def voice_selection_callback(callback: CallbackQuery):
    voice = callback.data.replace("voice_", "")
    user_id = callback.from_user.id
    update_user_setting(user_id, "voice", voice)
    text = (
        f"✅ <b>Голос змінено на: {voice.title()}</b>\n\n"
        f"Тепер всі озвучки будуть використовувати голос <b>{voice}</b>"
    )
    await safe_edit_message(callback, text, "HTML", get_voice_selection_keyboard())


@dp.callback_query(F.data == "speed_custom")
async def speed_custom_callback(callback: CallbackQuery, state: FSMContext):
    text = (
        "⚡ <b>Введіть власну швидкість</b>\n\n"
        "Введіть число від 0.25 до 4.0 (наприклад: 1.5):"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_speed")]])
    success = await safe_edit_message(callback, text, "HTML", kb)
    if success:
        await state.set_state(UserStates.waiting_for_speed_setting)


@dp.callback_query(F.data.startswith("speed_"))
async def speed_selection_callback(callback: CallbackQuery):
    speed_str = callback.data.replace("speed_", "")
    try:
        speed = float(speed_str)
        user_id = callback.from_user.id
        update_user_setting(user_id, "speed", speed)
        text = (
            f"✅ <b>Швидкість змінено на: {speed}x</b>\n\n"
            f"Тепер всі озвучки будуть використовувати швидкість <b>{speed}x</b>"
        )
        await safe_edit_message(callback, text, "HTML", get_speed_selection_keyboard())
    except ValueError:
        try:
            await callback.answer("❌ Невірний формат швидкості")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("size_"))
async def image_size_selection_callback(callback: CallbackQuery):
    size = callback.data.replace("size_", "")
    user_id = callback.from_user.id
    update_user_setting(user_id, "image_size", size)
    text = (
        f"✅ <b>Розмір зображення змінено на: {size}</b>\n\n"
        f"Тепер всі зображення будуть генеруватися в розмірі <b>{size}</b>"
    )
    await safe_edit_message(callback, text, "HTML", get_image_size_keyboard())


@dp.callback_query(F.data.startswith("quality_"))
async def image_quality_selection_callback(callback: CallbackQuery):
    quality = callback.data.replace("quality_", "")
    user_id = callback.from_user.id
    update_user_setting(user_id, "image_quality", quality)
    text = (
        f"✅ <b>Якість зображення змінено на: {quality.upper()}</b>\n\n"
        f"Тепер всі зображення будуть генеруватися з якістю <b>{quality.upper()}</b>"
    )
    await safe_edit_message(callback, text, "HTML", get_image_quality_keyboard())


# ===================== Обробка станів (повідомлення) =====================
@dp.message(UserStates.waiting_for_text)
async def handle_ask_ai_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    try:
        thinking_msg = await message.answer("🤔 Думаю...")
        openai_service = get_openai_service()
        response = await openai_service.generate_text(message.text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(
            f"🧠 <b>Відповідь:</b>\n\n{sanitized_response}", parse_mode="HTML", reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Помилка в обробці запиту AI: {e}")
        await message.answer(
            f"❌ Виникла помилка при обробці запиту: {str(e)}", reply_markup=get_back_to_menu_keyboard()
        )
    await state.clear()


@dp.message(UserStates.waiting_for_creative_prompt)
async def handle_creative_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    try:
        thinking_msg = await message.answer("🎨 Створюю...")
        openai_service = get_openai_service()
        response = await openai_service.generate_creative_text(message.text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(
            f"✨ <b>Креативний текст:</b>\n\n{sanitized_response}",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Помилка в креативному письмі: {e}")
        await message.answer(f"❌ Виникла помилка при створенні тексту: {str(e)}", reply_markup=get_back_to_menu_keyboard())
    await state.clear()


@dp.message(UserStates.waiting_for_code_prompt)
async def handle_code_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    try:
        thinking_msg = await message.answer("💻 Генерую код...")
        openai_service = get_openai_service()
        response = await openai_service.generate_code(message.text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(
            f"🔧 <b>Згенерований код:</b>\n\n<code>{sanitized_response}</code>",
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Помилка в генерації коду: {e}")
        await message.answer(
            f"❌ Виникла помилка при генерації коду: {str(e)}", reply_markup=get_back_to_menu_keyboard()
        )
    await state.clear()


@dp.message(UserStates.waiting_for_translate_text)
async def handle_translate_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    try:
        thinking_msg = await message.answer("🌐 Перекладаю...")
        openai_service = get_openai_service()
        response = await openai_service.translate_text(message.text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(
            f"🔄 <b>Переклад:</b>\n\n{sanitized_response}", parse_mode="HTML", reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Помилка в перекладі: {e}")
        await message.answer(f"❌ Виникла помилка при перекладі: {str(e)}", reply_markup=get_back_to_menu_keyboard())
    await state.clear()


@dp.message(UserStates.waiting_for_summarize_text)
async def handle_summarize_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    try:
        thinking_msg = await message.answer("📝 Створюю резюме...")
        openai_service = get_openai_service()
        response = await openai_service.summarize_text(message.text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(
            f"📋 <b>Резюме:</b>\n\n{sanitized_response}", parse_mode="HTML", reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Помилка в резюмуванні: {e}")
        await message.answer(
            f"❌ Виникла помилка при створенні резюме: {str(e)}", reply_markup=get_back_to_menu_keyboard()
        )
    await state.clear()


@dp.message(UserStates.waiting_for_explain_concept)
async def handle_explain_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    try:
        thinking_msg = await message.answer("💡 Пояснюю...")
        openai_service = get_openai_service()
        response = await openai_service.explain_concept(message.text)
        await thinking_msg.delete()
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(
            f"🎓 <b>Пояснення:</b>\n\n{sanitized_response}", parse_mode="HTML", reply_markup=get_back_to_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Помилка в поясненні: {e}")
        await message.answer(
            f"❌ Виникла помилка при поясненні: {str(e)}", reply_markup=get_back_to_menu_keyboard()
        )
    await state.clear()


@dp.message(UserStates.waiting_for_tts_text)
async def handle_tts_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    status = await send_message_with_retry(message.chat.id, "🎤 Генерую озвучку...")

    async def _worker():
        try:
            user_id = message.from_user.id
            settings = get_user_settings(user_id)
            tts_service = get_openai_tts_service()
            audio_data = await tts_service.generate_speech_with_validation(
                message.text, voice=settings['voice'], speed=settings['speed']
            )

            await send_voice_with_retry(
                chat_id=message.chat.id,
                voice_bytes=audio_data,
                caption=(f"🔊 <b>Озвучка:</b> {sanitize_telegram_text(message.text)[:800]}\n"
                         f"Голос: {settings['voice']}, Швидкість: {settings['speed']}x"),
                parse_mode="HTML",
                filename="speech.mp3"
            )

            await edit_message_with_retry(
                message.chat.id, status.message_id,
                "✅ Озвучка готова!",
                reply_markup=get_back_to_menu_keyboard()
            )

        except Exception as e:
            logger.error(f"Помилка в озвучуванні: {e}")
            try:
                tts_service = get_openai_tts_service()
                hint = await _tts_hint(tts_service)   # ⬅️ ВАЖЛИВО: await
            except Exception:
                hint = ""
            await edit_message_with_retry(
                message.chat.id, status.message_id,
                f"❌ Виникла помилка при генерації озвучки: {str(e)}{hint}",
                reply_markup=get_back_to_menu_keyboard()
            )
        finally:
            await state.clear()

    asyncio.create_task(_worker())


@dp.message(UserStates.waiting_for_image_prompt)
async def handle_image_text(message: Message, state: FSMContext):
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return

    status = await message.answer("🎨 Створюю 2 варіанти зображення… Це може зайняти до хвилини.")

    async def _worker():
        try:
            user_id = message.from_user.id
            settings = get_user_settings(user_id)
            image_service = get_openai_image_service()

            image_bytes_list = await image_service.generate_image(
                message.text,
                size=settings['image_size'],
                quality=settings['image_quality'],
                n=2
            )

            if not image_bytes_list:
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    "❌ Не вдалося згенерувати зображення", reply_markup=get_back_to_menu_keyboard()
                )
                return

            if len(image_bytes_list) >= 2:
                media = []
                for i, image_bytes in enumerate(image_bytes_list[:2], 1):
                    media.append(
                        InputMediaPhoto(
                            media=BufferedInputFile(image_bytes, filename=f"generated_image_{i}.png"),
                            caption=(f"🖼️ <b>Варіант {i}</b>\n"
                                     f"Опис: {sanitize_telegram_text(message.text)[:800]}\n"
                                     f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}") if i == 1 else None,
                            parse_mode="HTML"
                        )
                    )
                await send_media_group_with_retry(message.chat.id, media)
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    "✅ Згенеровано 2 зображення!", reply_markup=get_back_to_menu_keyboard()
                )
            else:
                photo_file = BufferedInputFile(image_bytes_list[0], filename="generated_image.png")
                await send_photo_with_retry(
                    chat_id=message.chat.id,
                    photo=photo_file,
                    caption=(f"🖼️ <b>Згенероване зображення</b>\n"
                             f"Опис: {sanitize_telegram_text(message.text)[:800]}\n"
                             f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}"),
                    parse_mode="HTML"
                )
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    "✅ Зображення згенеровано!", reply_markup=get_back_to_menu_keyboard()
                )
        except Exception as e:
            logger.error(f"Помилка в генерації зображення (стан): {e}")
            try:
                await safe_edit_message_text(
                    bot, message.chat.id, status.message_id,
                    f"❌ Виникла помилка при генерації зображення: {e}", reply_markup=get_back_to_menu_keyboard()
                )
            except Exception:
                pass
        finally:
            await state.clear()

    asyncio.create_task(_worker())


# Обробник введення власної швидкості
@dp.message(UserStates.waiting_for_speed_setting)
async def handle_custom_speed(message: Message, state: FSMContext):
    try:
        speed = float(message.text)
        if not (0.25 <= speed <= 4.0):
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_speed")]])
            await message.answer("❌ Швидкість повинна бути від 0.25 до 4.0. Спробуйте ще раз:", reply_markup=kb)
            return

        user_id = message.from_user.id
        update_user_setting(user_id, "speed", speed)

        await message.answer(
            f"✅ <b>Швидкість змінено на: {speed}x</b>\n\nТепер всі озвучки будуть використовувати швидкість <b>{speed}x</b>",
            parse_mode="HTML",
            reply_markup=get_speed_selection_keyboard(),
        )
    except ValueError:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_speed")]])
        await message.answer(
            "❌ Невірний формат числа. Введіть число від 0.25 до 4.0 (наприклад: 1.5):",
            reply_markup=kb,
        )
        return
    await state.clear()


# Обробка звичайних повідомлень
@dp.message(F.text)
async def handle_message(message: Message) -> None:
    await message.answer(f"🔔 Ви написали: {message.text}")


# ---------- Webhook (aiohttp) ----------
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web


async def on_startup(bot: Bot) -> None:
    webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook встановлено: {webhook_url}")


async def on_shutdown(bot: Bot) -> None:
    await bot.delete_webhook()
    logger.info("🛑 Webhook видалено")


def create_app() -> web.Application:
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app


async def main() -> None:
    logger.info("🤖 Бот запускається в webhook режимі...")

    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ Встановіть BOT_TOKEN у змінних середовища або .env файлі!")
        return

    if not OPENAI_API_KEY:
        logger.warning("⚠️ OpenAI API ключ не налаштовано. OpenAI функції будуть недоступні.")
    else:
        logger.info("✅ OpenAI API ключ налаштовано. Всі функції доступні.")

    await on_startup(bot)
    app = create_app()

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info(f"🌐 Webhook сервер запущено на 0.0.0.0:{port}")
    logger.info(f"📡 Webhook URL: {WEBHOOK_URL}{WEBHOOK_PATH}")

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        logger.info("🛑 Отримано сигнал зупинки...")
    finally:
        await on_shutdown(bot)
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот зупинено користувачем")
    except Exception as e:
        logger.error(f"❌ Критична помилка: {e}")
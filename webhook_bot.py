import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import BOT_TOKEN, LOG_LEVEL, OPENAI_API_KEY
from openai_service import get_openai_service
from openai_tts_service import get_openai_tts_service
from openai_image_service import get_openai_image_service

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, LOG_LEVEL.upper())
)
logger = logging.getLogger(__name__)

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

# Ініціалізація бота та диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словник для зберігання налаштувань користувачів
user_settings = {}

def sanitize_telegram_text(text: str) -> str:
    """
    Очищає текст від невалідних HTML тегів для Telegram
    
    Args:
        text: Текст для очищення
        
    Returns:
        Очищений текст
    """
    if not text:
        return text
    
    # Видаляємо всі HTML-подібні теги, які можуть викликати помилки парсингу
    # Залишаємо тільки базові теги, які підтримує Telegram
    text = re.sub(r'<[^>]*>', '', text)
    
    # Видаляємо залишки HTML entities
    text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
    
    # Видаляємо зайві пробіли та переноси рядків
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def get_user_settings(user_id: int) -> dict:
    """Отримання налаштувань користувача"""
    if user_id not in user_settings:
        user_settings[user_id] = {
            'voice': 'alloy',
            'speed': 1.0,
            'image_size': 'auto',
            'image_quality': 'auto'
        }
    return user_settings[user_id]

def update_user_setting(user_id: int, setting: str, value) -> None:
    """Оновлення налаштування користувача"""
    if user_id not in user_settings:
        get_user_settings(user_id)
    user_settings[user_id][setting] = value

def get_main_menu() -> InlineKeyboardMarkup:
    """Створення головного меню з кнопками"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 Запитати AI", callback_data="ask_ai"),
            InlineKeyboardButton(text="✨ Креативне письмо", callback_data="creative")
        ],
        [
            InlineKeyboardButton(text="💻 Генерація коду", callback_data="code"),
            InlineKeyboardButton(text="🌐 Переклад", callback_data="translate")
        ],
        [
            InlineKeyboardButton(text="📝 Резюме тексту", callback_data="summarize"),
            InlineKeyboardButton(text="💡 Пояснення", callback_data="explain")
        ],
        [
            InlineKeyboardButton(text="🎤 Озвучка (TTS)", callback_data="tts"),
            InlineKeyboardButton(text="🖼️ Генерація зображень", callback_data="image")
        ],
        [
            InlineKeyboardButton(text="⚙️ Налаштування", callback_data="settings"),
            InlineKeyboardButton(text="ℹ️ Допомога", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="📊 Інформація", callback_data="info")
        ]
    ])
    return keyboard

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Створення клавіатури з кнопкою 'Назад до меню'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Назад до меню", callback_data="back_to_menu")]
    ])
    return keyboard

def get_settings_menu_keyboard() -> InlineKeyboardMarkup:
    """Створення меню налаштувань"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎤 Голос TTS", callback_data="settings_voice"),
            InlineKeyboardButton(text="⚡ Швидкість TTS", callback_data="settings_speed")
        ],
        [
            InlineKeyboardButton(text="📐 Розмір зображення", callback_data="settings_image_size"),
            InlineKeyboardButton(text="🎨 Якість зображення", callback_data="settings_image_quality")
        ],
        [
            InlineKeyboardButton(text="🏠 Назад до меню", callback_data="back_to_menu")
        ]
    ])
    return keyboard

def get_voice_selection_keyboard() -> InlineKeyboardMarkup:
    """Створення клавіатури вибору голосу"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Alloy", callback_data="voice_alloy"),
            InlineKeyboardButton(text="🔊 Echo", callback_data="voice_echo")
        ],
        [
            InlineKeyboardButton(text="📚 Fable", callback_data="voice_fable"),
            InlineKeyboardButton(text="💎 Onyx", callback_data="voice_onyx")
        ],
        [
            InlineKeyboardButton(text="⭐ Nova", callback_data="voice_nova"),
            InlineKeyboardButton(text="✨ Shimmer", callback_data="voice_shimmer")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")
        ]
    ])
    return keyboard

def get_speed_selection_keyboard() -> InlineKeyboardMarkup:
    """Створення клавіатури вибору швидкості"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🐌 0.5x", callback_data="speed_0.5"),
            InlineKeyboardButton(text="🚶 0.75x", callback_data="speed_0.75")
        ],
        [
            InlineKeyboardButton(text="🚶‍♂️ 1.0x", callback_data="speed_1.0"),
            InlineKeyboardButton(text="🏃 1.25x", callback_data="speed_1.25")
        ],
        [
            InlineKeyboardButton(text="🏃‍♂️ 1.5x", callback_data="speed_1.5"),
            InlineKeyboardButton(text="🚀 2.0x", callback_data="speed_2.0")
        ],
        [
            InlineKeyboardButton(text="✏️ Ввести власну", callback_data="speed_custom")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")
        ]
    ])
    return keyboard

def get_image_size_keyboard() -> InlineKeyboardMarkup:
    """Створення клавіатури вибору розміру зображення"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 1024x1024", callback_data="size_1024x1024"),
            InlineKeyboardButton(text="📄 1024x1536", callback_data="size_1024x1536")
        ],
        [
            InlineKeyboardButton(text="🖥️ 1536x1024", callback_data="size_1536x1024"),
            InlineKeyboardButton(text="🤖 Auto", callback_data="size_auto")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")
        ]
    ])
    return keyboard

def get_image_quality_keyboard() -> InlineKeyboardMarkup:
    """Створення клавіатури вибору якості зображення"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Low", callback_data="quality_low"),
            InlineKeyboardButton(text="⚖️ Medium", callback_data="quality_medium")
        ],
        [
            InlineKeyboardButton(text="🎨 High", callback_data="quality_high"),
            InlineKeyboardButton(text="🤖 Auto", callback_data="quality_auto")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад до налаштувань", callback_data="settings")
        ]
    ])
    return keyboard

@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    """Функція 1: Привітання та інформація про бота"""
    user = message.from_user
    
    # Перевіряємо наявність OpenAI API ключа
    openai_status = "✅ Підключено" if OPENAI_API_KEY else "❌ Не підключено"
    
    welcome_text = (
        f"Привіт, {user.first_name}! 👋\n\n"
        f"Я розумний телеграм бот з функціями OpenAI.\n"
        f"Оберіть функцію з меню нижче:\n\n"
        f"OpenAI: {openai_status}"
    )
    
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )

# Хендлери для callback-ів від кнопок
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Назад до меню'"""
    await state.clear()
    openai_status = "✅ Підключено" if OPENAI_API_KEY else "❌ Не підключено"
    
    welcome_text = (
        f"Привіт, {callback.from_user.first_name}! 👋\n\n"
        f"Я розумний телеграм бот з функціями OpenAI.\n"
        f"Оберіть функцію з меню нижче:\n\n"
        f"OpenAI: {openai_status}"
    )
    
    await callback.message.edit_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "ask_ai")
async def ask_ai_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Запитати AI'"""
    await callback.message.edit_text(
        "🤖 <b>Запитати AI</b>\n\n"
        "Напишіть ваш запит, і я відповім на нього за допомогою штучного інтелекту.\n\n"
        "Приклад: Що таке машинне навчання?",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_text)
    await callback.answer()

@dp.callback_query(F.data == "creative")
async def creative_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Креативне письмо'"""
    await callback.message.edit_text(
        "✨ <b>Креативне письмо</b>\n\n"
        "Опишіть тему або жанр, і я створю креативний текст.\n\n"
        "Приклад: Напиши вірш про зиму",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_creative_prompt)
    await callback.answer()

@dp.callback_query(F.data == "code")
async def code_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Генерація коду'"""
    await callback.message.edit_text(
        "💻 <b>Генерація коду</b>\n\n"
        "Опишіть, який код потрібно згенерувати.\n\n"
        "Приклад: Створи функцію сортування масиву",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_code_prompt)
    await callback.answer()

@dp.callback_query(F.data == "translate")
async def translate_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Переклад'"""
    await callback.message.edit_text(
        "🌐 <b>Переклад тексту</b>\n\n"
        "Напишіть текст, який потрібно перекласти.\n\n"
        "Приклад: Hello world",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_translate_text)
    await callback.answer()

@dp.callback_query(F.data == "summarize")
async def summarize_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Резюме тексту'"""
    await callback.message.edit_text(
        "📝 <b>Резюме тексту</b>\n\n"
        "Надішліть текст, який потрібно резюмувати.\n\n"
        "Приклад: [ваш довгий текст]",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_summarize_text)
    await callback.answer()

@dp.callback_query(F.data == "explain")
async def explain_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Пояснення'"""
    await callback.message.edit_text(
        "💡 <b>Пояснення концепції</b>\n\n"
        "Напишіть концепцію або термін, який потрібно пояснити.\n\n"
        "Приклад: Що таке машинне навчання?",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_explain_concept)
    await callback.answer()

@dp.callback_query(F.data == "tts")
async def tts_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Озвучка (TTS)'"""
    await callback.message.edit_text(
        "🎤 <b>Озвучка тексту</b>\n\n"
        "Напишіть текст для озвучування.\n\n"
        "Приклад: Привіт, як справи?",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_tts_text)
    await callback.answer()

@dp.callback_query(F.data == "image")
async def image_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка натискання кнопки 'Генерація зображень'"""
    await callback.message.edit_text(
        "🖼️ <b>Генерація зображення</b>\n\n"
        "Опишіть зображення, яке потрібно згенерувати.\n\n"
        "Приклад: Кіт, що грає з м'ячем",
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await state.set_state(UserStates.waiting_for_image_prompt)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Допомога'"""
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
    await callback.message.edit_text(
        help_text, 
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "info")
async def info_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Інформація'"""
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
    await callback.message.edit_text(
        info_text, 
        parse_mode="HTML",
        reply_markup=get_back_to_menu_keyboard()
    )
    await callback.answer()

# Обробники для меню налаштувань
@dp.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Налаштування'"""
    await callback.message.edit_text(
        "⚙️ <b>Налаштування</b>\n\n"
        "Оберіть параметр для зміни:",
        parse_mode="HTML",
        reply_markup=get_settings_menu_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "settings_voice")
async def settings_voice_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Голос TTS'"""
    await callback.message.edit_text(
        "🎤 <b>Налаштування голосу TTS</b>\n\n"
        "Оберіть голос для озвучування:",
        parse_mode="HTML",
        reply_markup=get_voice_selection_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "settings_speed")
async def settings_speed_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Швидкість TTS'"""
    await callback.message.edit_text(
        "⚡ <b>Налаштування швидкості TTS</b>\n\n"
        "Оберіть швидкість озвучування:",
        parse_mode="HTML",
        reply_markup=get_speed_selection_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "settings_image_size")
async def settings_image_size_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Розмір зображення'"""
    await callback.message.edit_text(
        "📐 <b>Налаштування розміру зображення</b>\n\n"
        "Оберіть розмір для генерації зображень:",
        parse_mode="HTML",
        reply_markup=get_image_size_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "settings_image_quality")
async def settings_image_quality_callback(callback: CallbackQuery):
    """Обробка натискання кнопки 'Якість зображення'"""
    await callback.message.edit_text(
        "🎨 <b>Налаштування якості зображення</b>\n\n"
        "Оберіть якість для генерації зображень:",
        parse_mode="HTML",
        reply_markup=get_image_quality_keyboard()
    )
    await callback.answer()

# Обробники для зміни налаштувань голосу
@dp.callback_query(F.data.startswith("voice_"))
async def voice_selection_callback(callback: CallbackQuery):
    """Обробка вибору голосу"""
    voice = callback.data.replace("voice_", "")
    user_id = callback.from_user.id
    
    update_user_setting(user_id, 'voice', voice)
    
    await callback.message.edit_text(
        f"✅ <b>Голос змінено на: {voice.title()}</b>\n\n"
        f"Тепер всі озвучки будуть використовувати голос <b>{voice}</b>",
        parse_mode="HTML",
        reply_markup=get_voice_selection_keyboard()
    )
    await callback.answer(f"Голос змінено на {voice}")

# Обробники для зміни налаштувань швидкості
@dp.callback_query(F.data == "speed_custom")
async def speed_custom_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка кнопки 'Ввести власну' швидкість"""
    await callback.message.edit_text(
        "⚡ <b>Введіть власну швидкість</b>\n\n"
        "Введіть число від 0.25 до 4.0 (наприклад: 1.5):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_speed")]
        ])
    )
    await state.set_state(UserStates.waiting_for_speed_setting)
    await callback.answer()

@dp.callback_query(F.data.startswith("speed_"))
async def speed_selection_callback(callback: CallbackQuery):
    """Обробка вибору швидкості"""
    
    speed_str = callback.data.replace("speed_", "")
    try:
        speed = float(speed_str)
        user_id = callback.from_user.id
        
        update_user_setting(user_id, 'speed', speed)
        
        await callback.message.edit_text(
            f"✅ <b>Швидкість змінено на: {speed}x</b>\n\n"
            f"Тепер всі озвучки будуть використовувати швидкість <b>{speed}x</b>",
            parse_mode="HTML",
            reply_markup=get_speed_selection_keyboard()
        )
        await callback.answer(f"Швидкість змінено на {speed}x")
    except ValueError:
        await callback.answer("❌ Невірний формат швидкості")

# Обробники для зміни налаштувань розміру зображення
@dp.callback_query(F.data.startswith("size_"))
async def image_size_selection_callback(callback: CallbackQuery):
    """Обробка вибору розміру зображення"""
    size = callback.data.replace("size_", "")
    user_id = callback.from_user.id
    
    update_user_setting(user_id, 'image_size', size)
    
    await callback.message.edit_text(
        f"✅ <b>Розмір зображення змінено на: {size}</b>\n\n"
        f"Тепер всі зображення будуть генеруватися в розмірі <b>{size}</b>",
        parse_mode="HTML",
        reply_markup=get_image_size_keyboard()
    )
    await callback.answer(f"Розмір змінено на {size}")

# Обробники для зміни налаштувань якості зображення
@dp.callback_query(F.data.startswith("quality_"))
async def image_quality_selection_callback(callback: CallbackQuery):
    """Обробка вибору якості зображення"""
    quality = callback.data.replace("quality_", "")
    user_id = callback.from_user.id
    
    update_user_setting(user_id, 'image_quality', quality)
    
    await callback.message.edit_text(
        f"✅ <b>Якість зображення змінено на: {quality.upper()}</b>\n\n"
        f"Тепер всі зображення будуть генеруватися з якістю <b>{quality.upper()}</b>",
        parse_mode="HTML",
        reply_markup=get_image_quality_keyboard()
    )
    await callback.answer(f"Якість змінено на {quality}")

@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    """Функція допомоги"""
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

# OpenAI команди
@dp.message(Command("ask"))
async def ask_handler(message: Message) -> None:
    """Команда для запиту у AI"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    # Отримуємо текст після команди /ask
    question = message.text.replace('/ask', '').strip()
    if not question:
        await message.answer("Напишіть ваш запит після команди /ask\nНаприклад: /ask Що таке штучний інтелект?")
        return
    
    try:
        # Показуємо, що бот думає
        thinking_msg = await message.answer("🤔 Думаю...")
        
        # Отримуємо сервіс OpenAI
        openai_service = get_openai_service()
        
        # Генеруємо відповідь
        response = await openai_service.generate_text(question)
        
        # Видаляємо повідомлення "Думаю..."
        await thinking_msg.delete()
        
        # Відправляємо відповідь
        sanitized_response = sanitize_telegram_text(response)
        await message.answer(f"🧠 <b>Відповідь:</b>\n\n{sanitized_response}", parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Помилка в команді /ask: {e}", exc_info=True)
        await message.answer(f"❌ Виникла помилка при обробці запиту: {str(e)}")

@dp.message(Command("creative"))
async def creative_handler(message: Message) -> None:
    """Команда для креативного письма"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    prompt = message.text.replace('/creative', '').strip()
    if not prompt:
        await message.answer("Напишіть тему для креативного письма після команди /creative\nНаприклад: /creative Напиши вірш про зиму")
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
    """Команда для генерації коду"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    prompt = message.text.replace('/code', '').strip()
    if not prompt:
        await message.answer("Опишіть код, який потрібно згенерувати після команди /code\nНаприклад: /code Створи функцію сортування масиву")
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
    """Команда для перекладу тексту"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    text = message.text.replace('/translate', '').strip()
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
    """Команда для створення резюме"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    text = message.text.replace('/summarize', '').strip()
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
    """Команда для пояснення концепції"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    concept = message.text.replace('/explain', '').strip()
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
    """Команда для озвучування тексту"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    # Парсимо команду та параметри
    command_text = message.text.replace('/tts', '').strip()
    if not command_text:
        await message.answer(
            "🎤 <b>Озвучка тексту</b>\n\n"
            "Використання:\n"
            "• <code>/tts Привіт, як справи?</code> - звичайна озвучка\n"
            "• <code>/tts Привіт, як справи? | 1.5</code> - озвучка зі швидкістю 1.5x\n"
            "• <code>/tts Привіт, як справи? | alloy | 1.5</code> - з голосом та швидкістю\n\n"
            "Голоси: alloy, echo, fable, onyx, nova, shimmer\n"
            "Швидкість: 0.25 - 4.0 (1.0 = нормальна)",
            parse_mode="HTML"
        )
        return
    
    try:
        # Парсимо параметри (текст | голос | швидкість)
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
        
        thinking_msg = await message.answer("🎤 Генерую озвучку...")
        
        # Отримуємо налаштування користувача якщо параметри не вказані
        user_id = message.from_user.id
        settings = get_user_settings(user_id)
        
        final_voice = voice or settings['voice']
        final_speed = speed if speed is not None else settings['speed']
        
        tts_service = get_openai_tts_service()
        audio_data = await tts_service.generate_speech_with_validation(text, final_voice, final_speed)
        
        await thinking_msg.delete()
        
        # Формуємо підпис
        caption_parts = [f"🔊 <b>Озвучка:</b> {text}"]
        if voice:
            caption_parts.append(f"Голос: {voice}")
        if speed:
            caption_parts.append(f"Швидкість: {speed}x")
        
        # Відправляємо аудіо файл
        audio_input = types.BufferedInputFile(
            file=audio_data,
            filename="speech.mp3"
        )
        
        await message.answer_voice(
            voice=audio_input,
            caption="\n".join(caption_parts),
            parse_mode="HTML"
        )
        
    except ValueError as e:
        await message.answer(f"❌ Помилка параметрів: {str(e)}")
    except Exception as e:
        logger.error(f"Помилка в команді /tts: {e}")
        await message.answer(f"❌ Виникла помилка при генерації озвучки: {str(e)}")

@dp.message(Command("tts_settings"))
async def tts_settings_handler(message: Message) -> None:
    """Команда для налаштувань TTS"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    try:
        tts_service = get_openai_tts_service()
        
        # Отримуємо поточні налаштування
        current_voice = tts_service.voice
        current_speed = tts_service.speed
        available_voices = tts_service.get_available_voices()
        speed_range = tts_service.get_speed_range()
        
        settings_text = f"""
🎤 <b>Налаштування TTS</b>

<b>Поточні налаштування:</b>
• Голос: <code>{current_voice}</code>
• Швидкість: <code>{current_speed}x</code>

<b>Доступні голоси:</b>
{', '.join(available_voices)}

<b>Діапазон швидкості:</b>
{speed_range[0]}x - {speed_range[1]}x (1.0 = нормальна)

<b>Приклади використання:</b>
• <code>/tts Привіт!</code> - звичайна озвучка
• <code>/tts Привіт! | 1.5</code> - швидкість 1.5x
• <code>/tts Привіт! | nova</code> - голос nova
• <code>/tts Привіт! | echo | 0.8</code> - голос echo, швидкість 0.8x
        """
        
        await message.answer(settings_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Помилка в команді /tts_settings: {e}")
        await message.answer(f"❌ Виникла помилка при отриманні налаштувань: {str(e)}")

@dp.message(Command("image"))
async def image_handler(message: Message) -> None:
    """Команда для генерації зображень"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        return
    
    prompt = message.text.replace('/image', '').strip()
    if not prompt:
        await message.answer("Опишіть зображення, яке потрібно згенерувати після команди /image\nНаприклад: /image Кіт, що грає з м'ячем")
        return
    
    try:
        thinking_msg = await message.answer("🎨 Створюю 2 варіанти зображення...")
        
        # Отримуємо налаштування користувача
        user_id = message.from_user.id
        settings = get_user_settings(user_id)
        
        image_service = get_openai_image_service()
        # Генеруємо 2 варіанти зображення
        image_bytes_list = await image_service.generate_image(
            prompt, 
            size=settings['image_size'], 
            quality=settings['image_quality'], 
            n=2
        )
        
        logger.info(f"Отримано результат генерації зображення: {len(image_bytes_list)} зображень")
        
        await thinking_msg.delete()
        
        # Відправляємо обидва згенеровані зображення
        if image_bytes_list and len(image_bytes_list) >= 2:
            for i, image_bytes in enumerate(image_bytes_list[:2], 1):
                photo_file = BufferedInputFile(image_bytes, filename=f"generated_image_{i}.png")
                
                await message.answer_photo(
                    photo=photo_file,
                    caption=f"🖼️ <b>Варіант {i}:</b> {prompt}\n"
                           f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}",
                    parse_mode="HTML"
                )
        elif image_bytes_list and len(image_bytes_list) == 1:
            # Якщо згенерувалося тільки одне зображення
            image_bytes = image_bytes_list[0]
            photo_file = BufferedInputFile(image_bytes, filename="generated_image.png")
            
            await message.answer_photo(
                photo=photo_file,
                caption=f"🖼️ <b>Згенероване зображення:</b> {prompt}\n"
                       f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Не вдалося згенерувати зображення або отримано порожній результат")
        
    except Exception as e:
        logger.error(f"Помилка в команді /image: {e}")
        await message.answer(f"❌ Виникла помилка при генерації зображення: {str(e)}")

@dp.message(Command("image_debug"))
async def image_debug_handler(message: Message) -> None:
    """Команда для діагностики генерації зображень"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано.")
        return
    
    prompt = message.text.replace('/image_debug', '').strip()
    if not prompt:
        prompt = "A simple red circle"  # Тестовий промт
    
    try:
        await message.answer(f"🔍 <b>Діагностика генерації зображення</b>\n\nПромт: {prompt}", parse_mode="HTML")
        
        image_service = get_openai_image_service()
        
        # Отримуємо налаштування
        settings_info = f"""
<b>Налаштування:</b>
• Модель: {image_service.model}
• Розмір: {image_service.default_size}
• Якість: {image_service.default_quality}
        """
        await message.answer(settings_info, parse_mode="HTML")
        
        # Тестуємо генерацію
        await message.answer("🎨 Тестую генерацію...")
        image_bytes_list = await image_service.generate_image(prompt, n=1)
        
        debug_info = f"""
<b>Результат:</b>
• Кількість зображень: {len(image_bytes_list) if image_bytes_list else 0}
• Розмір першого зображення: {len(image_bytes_list[0]) if image_bytes_list and len(image_bytes_list) > 0 else 'None'} байт
        """
        await message.answer(debug_info, parse_mode="HTML")
        
        # Відправляємо зображення якщо є
        if image_bytes_list and len(image_bytes_list) > 0:
            image_bytes = image_bytes_list[0]
            photo_file = BufferedInputFile(image_bytes, filename="debug_image.png")
            await message.answer_photo(
                photo=photo_file,
                caption="✅ Тестове зображення",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Не отримано зображення")
        
    except Exception as e:
        logger.error(f"Помилка в команді /image_debug: {e}")
        await message.answer(f"❌ Помилка діагностики: {str(e)}")

# Хендлери для обробки текстів у різних станах
@dp.message(UserStates.waiting_for_text)
async def handle_ask_ai_text(message: Message, state: FSMContext):
    """Обробка тексту для запиту AI"""
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
            f"🧠 <b>Відповідь:</b>\n\n{sanitized_response}", 
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в обробці запиту AI: {e}")
        await message.answer(
            f"❌ Виникла помилка при обробці запиту: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_creative_prompt)
async def handle_creative_text(message: Message, state: FSMContext):
    """Обробка тексту для креативного письма"""
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
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в креативному письмі: {e}")
        await message.answer(
            f"❌ Виникла помилка при створенні тексту: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_code_prompt)
async def handle_code_text(message: Message, state: FSMContext):
    """Обробка тексту для генерації коду"""
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
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в генерації коду: {e}")
        await message.answer(
            f"❌ Виникла помилка при генерації коду: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_translate_text)
async def handle_translate_text(message: Message, state: FSMContext):
    """Обробка тексту для перекладу"""
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
            f"🔄 <b>Переклад:</b>\n\n{sanitized_response}", 
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в перекладі: {e}")
        await message.answer(
            f"❌ Виникла помилка при перекладі: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_summarize_text)
async def handle_summarize_text(message: Message, state: FSMContext):
    """Обробка тексту для резюмування"""
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
            f"📋 <b>Резюме:</b>\n\n{sanitized_response}", 
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в резюмуванні: {e}")
        await message.answer(
            f"❌ Виникла помилка при створенні резюме: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_explain_concept)
async def handle_explain_text(message: Message, state: FSMContext):
    """Обробка тексту для пояснення концепції"""
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
            f"🎓 <b>Пояснення:</b>\n\n{sanitized_response}", 
            parse_mode="HTML",
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в поясненні: {e}")
        await message.answer(
            f"❌ Виникла помилка при поясненні: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_tts_text)
async def handle_tts_text(message: Message, state: FSMContext):
    """Обробка тексту для озвучування"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return
    
    try:
        thinking_msg = await message.answer("🎤 Генерую озвучку...")
        
        # Отримуємо налаштування користувача
        user_id = message.from_user.id
        settings = get_user_settings(user_id)
        
        tts_service = get_openai_tts_service()
        audio_data = await tts_service.generate_speech_with_validation(
            message.text, 
            voice=settings['voice'], 
            speed=settings['speed']
        )
        
        await thinking_msg.delete()
        
        # Відправляємо аудіо файл
        audio_input = types.BufferedInputFile(
            file=audio_data,
            filename="speech.mp3"
        )
        
        await message.answer_voice(
            voice=audio_input,
            caption=f"🔊 <b>Озвучка:</b> {message.text}\n"
                   f"Голос: {settings['voice']}, Швидкість: {settings['speed']}x",
            parse_mode="HTML"
        )
        
        # Відправляємо кнопку "Назад до меню" окремо
        await message.answer(
            "✅ Озвучка готова!",
            reply_markup=get_back_to_menu_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Помилка в озвучуванні: {e}")
        await message.answer(
            f"❌ Виникла помилка при генерації озвучки: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

@dp.message(UserStates.waiting_for_image_prompt)
async def handle_image_text(message: Message, state: FSMContext):
    """Обробка тексту для генерації зображення"""
    if not OPENAI_API_KEY:
        await message.answer("❌ OpenAI API ключ не налаштовано. Зверніться до адміністратора.")
        await state.clear()
        return
    
    try:
        thinking_msg = await message.answer("🎨 Створюю 2 варіанти зображення...")
        
        # Отримуємо налаштування користувача
        user_id = message.from_user.id
        settings = get_user_settings(user_id)
        
        image_service = get_openai_image_service()
        # Генеруємо 2 варіанти зображення
        image_bytes_list = await image_service.generate_image(
            message.text, 
            size=settings['image_size'], 
            quality=settings['image_quality'], 
            n=2
        )
        
        await thinking_msg.delete()
        
        # Відправляємо обидва згенеровані зображення
        if image_bytes_list and len(image_bytes_list) >= 2:
            for i, image_bytes in enumerate(image_bytes_list[:2], 1):
                photo_file = BufferedInputFile(image_bytes, filename=f"generated_image_{i}.png")
                
                await message.answer_photo(
                    photo=photo_file,
                    caption=f"🖼️ <b>Варіант {i}:</b> {message.text}\n"
                           f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}",
                    parse_mode="HTML"
                )
            
            # Відправляємо кнопку "Назад до меню" окремо
            await message.answer(
                "✅ Згенеровано 2 варіанти зображення!",
                reply_markup=get_back_to_menu_keyboard()
            )
        elif image_bytes_list and len(image_bytes_list) == 1:
            # Якщо згенерувалося тільки одне зображення
            image_bytes = image_bytes_list[0]
            photo_file = BufferedInputFile(image_bytes, filename="generated_image.png")
            
            await message.answer_photo(
                photo=photo_file,
                caption=f"🖼️ <b>Згенероване зображення:</b> {message.text}\n"
                       f"Розмір: {settings['image_size']}, Якість: {settings['image_quality'].upper()}",
                parse_mode="HTML"
            )
            
            await message.answer(
                "✅ Зображення згенеровано! (Отримано 1 варіант замість 2)",
                reply_markup=get_back_to_menu_keyboard()
            )
        else:
            await message.answer(
                "❌ Не вдалося згенерувати зображення",
                reply_markup=get_back_to_menu_keyboard()
            )
        
    except Exception as e:
        logger.error(f"Помилка в генерації зображення: {e}")
        await message.answer(
            f"❌ Виникла помилка при генерації зображення: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )
    
    await state.clear()

# Обробники для введення власної швидкості
@dp.message(UserStates.waiting_for_speed_setting)
async def handle_custom_speed(message: Message, state: FSMContext):
    """Обробка введення власної швидкості"""
    try:
        speed = float(message.text)
        if not (0.25 <= speed <= 4.0):
            await message.answer(
                "❌ Швидкість повинна бути від 0.25 до 4.0. Спробуйте ще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_speed")]
                ])
            )
            return
        
        user_id = message.from_user.id
        update_user_setting(user_id, 'speed', speed)
        
        await message.answer(
            f"✅ <b>Швидкість змінено на: {speed}x</b>\n\n"
            f"Тепер всі озвучки будуть використовувати швидкість <b>{speed}x</b>",
            parse_mode="HTML",
            reply_markup=get_speed_selection_keyboard()
        )
        
    except ValueError:
        await message.answer(
            "❌ Невірний формат числа. Введіть число від 0.25 до 4.0 (наприклад: 1.5):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_speed")]
            ])
        )
        return
    
    await state.clear()

@dp.message(F.text)
async def handle_message(message: Message) -> None:
    """Обробка звичайних повідомлень (не команд)"""
    user_message = message.text
    await message.answer(f"🔔 Ви написали: {user_message}")

# Webhook imports
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from config import WEBHOOK_PATH, WEBHOOK_URL

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
    
    # Перевірка токенів
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error("❌ Встановіть BOT_TOKEN у змінних середовища або .env файлі!")
        return
    
    if not OPENAI_API_KEY:
        logger.warning("⚠️ OpenAI API ключ не налаштовано. OpenAI функції будуть недоступні.")
    else:
        logger.info("✅ OpenAI API ключ налаштовано. Всі функції доступні.")
    
    # Налаштування webhook
    await on_startup(bot)
    
    # Створення додатку
    app = create_app()
    
    # Запуск сервера
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Використовуємо порт з змінної середовища (для деплою на сервер)
    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"🌐 Webhook сервер запущено на 0.0.0.0:{port}")
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
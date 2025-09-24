# 🤖 Розумний Telegram Bot з OpenAI (aiogram 3.13)

Розумний телеграм бот з інтеграцією OpenAI, написаний на Python з використанням aiogram 3.13. Бот надає базову функціональність та потужні можливості штучного інтелекту.

## ✨ Функції

### Основні функції:
1. **Привітання** - привітає користувача та показує доступні команди
2. **Повторення повідомлень** - повторює будь-яке повідомлення користувача

### OpenAI функції:
3. **Запити до AI** - відповідає на будь-які питання користувачів
4. **Креативне письмо** - створює вірші, оповідання та інший креативний контент
5. **Генерація коду** - пише код на різних мовах програмування
6. **Переклад тексту** - перекладає текст між різними мовами
7. **Резюмування** - створює короткі резюме довгих текстів
8. **Пояснення концепцій** - пояснює складні терміни простими словами

### Команди:
- `/start` - почати роботу з ботом
- `/help` - показати довідку
- `/echo` - повторювати повідомлення
- `/info` - інформація про бота
- `/ask [запит]` - запитати щось у AI
- `/creative [тема]` - креативне письмо
- `/code [опис]` - генерація коду
- `/translate [текст]` - переклад тексту
- `/summarize [текст]` - створення резюме
- `/explain [концепція]` - пояснення концепції

## 🚀 Встановлення

1. **Клонуйте репозиторій:**
   ```bash
   git clone <your-repo-url>
   cd content-maker
   ```

2. **Встановіть залежності:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Створіть бота в Telegram:**
   - Напишіть @BotFather в Telegram
   - Виконайте команду `/newbot`
   - Вкажіть назву та username для бота
   - Скопіюйте отриманий токен

4. **Налаштуйте токени:**
   ```bash
   # Створіть .env файл
   echo "BOT_TOKEN=your_actual_bot_token_here" > .env
   echo "OPENAI_API_KEY=your_openai_api_key_here" >> .env
   ```

5. **Отримайте OpenAI API ключ:**
   - Перейдіть на [OpenAI Platform](https://platform.openai.com/api-keys)
   - Створіть новий API ключ
   - Додайте його до .env файлу

## 🏃‍♂️ Запуск

### Тестування OpenAI API:
```bash
python test_openai.py
```

### Звичайний режим (polling):
```bash
python bot.py
```

### Webhook режим з ngrok:
```bash
python start_webhook.py
```

## 📁 Структура проекту

```
content-maker/
├── bot.py              # Основний файл бота (polling режим)
├── webhook_handler.py  # Webhook обробник
├── start_webhook.py    # Запуск з ngrok
├── openai_service.py   # Сервіс для роботи з OpenAI API
├── test_openai.py      # Тестовий скрипт для OpenAI
├── config.py           # Конфігурація
├── requirements.txt    # Залежності Python
├── .env                # Змінні середовища (створіть самостійно)
├── OPENAI_SETUP.md     # Детальні інструкції для OpenAI
├── .gitignore         # Git ignore файл
└── README.md          # Документація
```

## 🔧 Налаштування

### Змінні середовища:
- `BOT_TOKEN` - токен вашого бота (обов'язково)
- `OPENAI_API_KEY` - API ключ OpenAI (обов'язково для AI функцій)
- `OPENAI_MODEL` - модель OpenAI (за замовчуванням: gpt-3.5-turbo)
- `OPENAI_MAX_TOKENS` - максимальна кількість токенів (за замовчуванням: 1000)
- `OPENAI_TEMPERATURE` - креативність відповідей (за замовчуванням: 0.7)
- `LOG_LEVEL` - рівень логування (за замовчуванням: INFO)
- `BOT_USERNAME` - username бота (опціонально)
- `ADMIN_USER_ID` - ID адміністратора (опціонально)

### Webhook налаштування:
- `WEBHOOK_HOST` - хост для webhook (за замовчуванням: localhost)
- `WEBHOOK_PORT` - порт для webhook (за замовчуванням: 8080)
- `WEBHOOK_PATH` - шлях для webhook (за замовчуванням: /webhook)
- `WEBHOOK_URL` - повний URL webhook (автоматично встановлюється ngrok)

### Ngrok налаштування:
- `NGROK_AUTH_TOKEN` - токен ngrok (опціонально, отримайте з https://dashboard.ngrok.com)
- `NGROK_REGION` - регіон ngrok (us, eu, ap, au, sa, jp, in)

### Особливості aiogram 3.13:
- Повна асинхронність
- Сучасний синтаксис з фільтрами
- Краща продуктивність
- Вбудована підтримка middleware

## 📝 Використання

1. Запустіть бота
2. Знайдіть свого бота в Telegram за username
3. Натисніть "Start" або надішліть `/start`
4. Використовуйте команди або просто надсилайте повідомлення

## 🛠️ Розробка

### Додавання нових команд:
1. Створіть функцію-обробник з декоратором
2. Додайте фільтр для команди
3. Оновіть help_handler()

### Приклад нової команди:
```python
@dp.message(Command("mycommand"))
async def my_command_handler(message: Message) -> None:
    await message.answer("Моя нова команда!")

# Фільтр автоматично обробляє команду
```

### Додавання middleware:
```python
from aiogram import BaseMiddleware
from aiogram.types import Message

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # Логіка middleware
        return await handler(event, data)

dp.message.middleware(LoggingMiddleware())
```

## 🔄 Переваги aiogram 3.13:

- **Асинхронність**: Повна підтримка async/await
- **Фільтри**: Потужна система фільтрів для обробки повідомлень
- **Middleware**: Легке додавання проміжного ПЗ
- **Типізація**: Повна підтримка type hints
- **Продуктивність**: Швидша обробка повідомлень

## 🌐 Webhook режим з ngrok

### Переваги webhook:
- **Швидкість**: Миттєва доставка повідомлень
- **Ефективність**: Менше навантаження на сервер
- **Масштабованість**: Краще для великої кількості користувачів
- **Безпека**: Прямий зв'язок з Telegram серверами

### Налаштування ngrok:

1. **Отримайте auth token (опціонально):**
   - Зареєструйтесь на https://dashboard.ngrok.com
   - Скопіюйте ваш auth token
   - Додайте до .env файлу: `NGROK_AUTH_TOKEN=your_token`

2. **Запуск з webhook:**
   ```bash
   python start_webhook.py
   ```

3. **Переваги auth token:**
   - Стабільні туннелі
   - Кращий регіон
   - Більше функцій

### Приклад .env файлу:
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_here

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=1000
OPENAI_TEMPERATURE=0.7

# Logging
LOG_LEVEL=INFO

# Ngrok (опціонально)
NGROK_AUTH_TOKEN=your_ngrok_token_here
NGROK_REGION=eu
```

### Моніторинг webhook:
- Логи показують URL туннелю
- Перевірте статус на https://dashboard.ngrok.com
- Використовуйте ngrok веб-інтерфейс для моніторингу

## 🧠 OpenAI функції

### Доступні команди:

#### `/ask [запит]` - Загальні запити до AI
- Приклад: `/ask Що таке штучний інтелект?`
- Відповідає на будь-які питання користувачів

#### `/creative [тема]` - Креативне письмо
- Приклад: `/creative Напиши вірш про зиму`
- Створює вірші, оповідання, креативний контент

#### `/code [опис]` - Генерація коду
- Приклад: `/code Створи функцію сортування масиву`
- Генерує код на різних мовах програмування

#### `/translate [текст]` - Переклад тексту
- Приклад: `/translate Hello world`
- Перекладає текст між різними мовами

#### `/summarize [текст]` - Створення резюме
- Приклад: `/summarize [ваш довгий текст]`
- Створює короткі резюме довгих текстів

#### `/explain [концепція]` - Пояснення концепції
- Приклад: `/explain Що таке машинне навчання?`
- Пояснює складні терміни простими словами

### Налаштування моделей:
- `gpt-3.5-turbo` - Швидка та економна (за замовчуванням)
- `gpt-4` - Більш потужна модель
- `gpt-4-turbo` - Найновіша модель GPT-4

### Тестування OpenAI:
```bash
python test_openai.py
```

Детальні інструкції дивіться у файлі [OPENAI_SETUP.md](OPENAI_SETUP.md).

## 📄 Ліцензія

MIT License

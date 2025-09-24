# 🚀 Швидкий старт з OpenAI

## Крок 1: Встановлення залежностей
```bash
pip install -r requirements.txt
```

## Крок 2: Налаштування .env файлу
Створіть файл `.env` у корені проекту:
```env
BOT_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
```

## Крок 3: Отримання токенів

### Telegram Bot Token:
1. Напишіть @BotFather в Telegram
2. Виконайте `/newbot`
3. Скопіюйте токен

### OpenAI API Key:
1. Перейдіть на https://platform.openai.com/api-keys
2. Створіть новий API ключ
3. Скопіюйте ключ

## Крок 4: Запуск
```bash
python bot.py
```

## 🧠 Доступні команди:
- `/ask Що таке AI?` - запитати у AI
- `/creative Напиши вірш` - креативне письмо
- `/code Створи функцію сортування` - генерація коду
- `/translate Hello world` - переклад
- `/summarize [текст]` - резюме
- `/explain Що таке машинне навчання?` - пояснення

## ✅ Готово!
Ваш бот тепер має можливості штучного інтелекту!

Детальніше: [README.md](README.md) | [OPENAI_SETUP.md](OPENAI_SETUP.md)

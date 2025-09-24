# Інформація про сервіси OpenAI

## Огляд сервісів

Проект тепер містить три окремі сервіси для роботи з різними API OpenAI:

### 1. OpenAIService (openai_service.py)
**Призначення:** Генерація тексту
- **API:** Chat Completions API
- **Модель:** gpt-3.5-turbo (налаштовується)
- **Функції:**
  - Генерація тексту за промтом
  - Креативне письмо
  - Генерація коду
  - Переклад тексту
  - Резюмування тексту
  - Пояснення концепцій

### 2. OpenAITTSService (openai_tts_service.py)
**Призначення:** Генерація озвучки (Text-to-Speech)
- **API:** Audio Speech API
- **Модель:** tts-1 (налаштовується)
- **Функції:**
  - Генерація озвучки з тексту
  - Збереження аудіо у файл
  - Валідація голосів та швидкості
  - Підтримка різних голосів (alloy, echo, fable, onyx, nova, shimmer)
  - Налаштування швидкості мовлення (0.25x - 4.0x)

### 3. OpenAIImageService (openai_image_service.py)
**Призначення:** Генерація зображень
- **API:** Images API
- **Модель:** dall-e-3 (налаштовується)
- **Функції:**
  - Генерація зображень за промтом
  - Генерація варіацій існуючого зображення
  - Редагування зображень
  - Валідація розмірів та якості

## Конфігурація (.env файл)

```env
# OpenAI API ключ (загальний для всіх сервісів)
OPENAI_API_KEY=your_openai_api_key_here

# Налаштування для генерації тексту
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_MAX_TOKENS=1000
OPENAI_TEMPERATURE=0.7

# Налаштування для TTS (озвучка)
OPENAI_TTS_MODEL=tts-1
OPENAI_TTS_VOICE=alloy
OPENAI_TTS_SPEED=1.0

# Налаштування для генерації зображень
OPENAI_IMAGE_MODEL=dall-e-3
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=standard
```

## Використання в боті

### Команди бота:
- `/ask` - використовує OpenAIService
- `/creative` - використовує OpenAIService
- `/code` - використовує OpenAIService
- `/translate` - використовує OpenAIService
- `/summarize` - використовує OpenAIService
- `/explain` - використовує OpenAIService
- `/tts` - використовує OpenAITTSService (з підтримкою швидкості та голосу)
- `/tts_settings` - показує налаштування TTS
- `/image` - використовує OpenAIImageService

### Приклади використання:

```python
# Отримання сервісів
from openai_service import get_openai_service
from openai_tts_service import get_openai_tts_service
from openai_image_service import get_openai_image_service

# Генерація тексту
text_service = get_openai_service()
text = await text_service.generate_text("Привіт!")

# Генерація озвучки
tts_service = get_openai_tts_service()
audio_data = await tts_service.generate_speech("Привіт, як справи?", voice="alloy", speed=1.5)

# Генерація зображення
image_service = get_openai_image_service()
image_urls = await image_service.generate_image("Кіт, що грає з м'ячем")
```

## Переваги розділення сервісів

1. **Модульність** - кожен сервіс відповідає за конкретну функціональність
2. **Гнучкість** - можна налаштовувати різні моделі для різних задач
3. **Легкість тестування** - кожен сервіс можна тестувати окремо
4. **Масштабованість** - легко додавати нові функції або змінювати існуючі
5. **Чистий код** - краща організація та читабельність коду

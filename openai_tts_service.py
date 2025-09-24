import logging
import io
from typing import Optional
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_TTS_MODEL, OPENAI_TTS_VOICE, OPENAI_TTS_SPEED

logger = logging.getLogger(__name__)

class OpenAITTSService:
    """Сервіс для роботи з OpenAI TTS API (генерація озвучки)"""
    
    def __init__(self):
        """Ініціалізація клієнта OpenAI для TTS"""
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не встановлено")
        
        try:
            self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            self.model = OPENAI_TTS_MODEL
            self.voice = OPENAI_TTS_VOICE
            self.speed = OPENAI_TTS_SPEED
            logger.info("OpenAI TTS клієнт успішно ініціалізовано")
        except Exception as e:
            logger.error(f"Помилка ініціалізації OpenAI TTS клієнта: {e}")
            raise
    
    async def generate_speech(self, text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> bytes:
        """
        Генерація озвучки з тексту
        
        Args:
            text: Текст для озвучування
            voice: Голос для озвучки (alloy, echo, fable, onyx, nova, shimmer)
            speed: Швидкість мовлення (0.25 - 4.0)
            
        Returns:
            Аудіо дані у форматі MP3
        """
        try:
            # Використовуємо вказані параметри або дефолтні
            selected_voice = voice or self.voice
            selected_speed = speed if speed is not None else self.speed
            
            # Валідація швидкості
            if not (0.25 <= selected_speed <= 4.0):
                raise ValueError(f"Швидкість мовлення повинна бути в діапазоні 0.25-4.0, отримано: {selected_speed}")
            
            logger.info(f"Генерація озвучки для тексту: {text[:100]}...")
            logger.info(f"Використовується голос: {selected_voice}, модель: {self.model}, швидкість: {selected_speed}")
            
            response = await self.client.audio.speech.create(
                model=self.model,
                voice=selected_voice,
                input=text,
                speed=selected_speed
            )
            
            # Отримуємо аудіо дані
            audio_data = response.content
            logger.info(f"Отримано аудіо дані розміром: {len(audio_data)} байт")
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Помилка при генерації озвучки: {e}")
            raise Exception(f"Не вдалося згенерувати озвучку: {str(e)}")
    
    async def generate_speech_to_file(self, text: str, filename: str, voice: Optional[str] = None, speed: Optional[float] = None) -> str:
        """
        Генерація озвучки та збереження у файл
        
        Args:
            text: Текст для озвучування
            filename: Назва файлу для збереження
            voice: Голос для озвучки
            speed: Швидкість мовлення
            
        Returns:
            Шлях до збереженого файлу
        """
        try:
            audio_data = await self.generate_speech(text, voice, speed)
            
            # Зберігаємо аудіо дані у файл
            with open(filename, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"Озвучка збережена у файл: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Помилка при збереженні озвучки у файл: {e}")
            raise Exception(f"Не вдалося зберегти озвучку у файл: {str(e)}")
    
    async def get_available_voices(self) -> list:
        """
        Отримання списку доступних голосів
        
        Returns:
            Список доступних голосів
        """
        return ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
    
    def validate_voice(self, voice: str) -> bool:
        """
        Перевірка чи є голос валідним
        
        Args:
            voice: Назва голосу для перевірки
            
        Returns:
            True якщо голос валідний, False інакше
        """
        available_voices = self.get_available_voices()
        return voice.lower() in available_voices
    
    def validate_speed(self, speed: float) -> bool:
        """
        Перевірка чи є швидкість валідною
        
        Args:
            speed: Швидкість мовлення для перевірки
            
        Returns:
            True якщо швидкість валідна, False інакше
        """
        return 0.25 <= speed <= 4.0
    
    def get_speed_range(self) -> tuple:
        """
        Отримання діапазону допустимих швидкостей
        
        Returns:
            Кортеж (мінімальна_швидкість, максимальна_швидкість)
        """
        return (0.25, 4.0)
    
    async def generate_speech_with_validation(self, text: str, voice: Optional[str] = None, speed: Optional[float] = None) -> bytes:
        """
        Генерація озвучки з валідацією параметрів
        
        Args:
            text: Текст для озвучування
            voice: Голос для озвучки
            speed: Швидкість мовлення
            
        Returns:
            Аудіо дані у форматі MP3
        """
        if voice and not self.validate_voice(voice):
            available_voices = await self.get_available_voices()
            raise ValueError(f"Невірний голос '{voice}'. Доступні голоси: {', '.join(available_voices)}")
        
        if speed is not None and not (0.25 <= speed <= 4.0):
            raise ValueError(f"Швидкість мовлення повинна бути в діапазоні 0.25-4.0, отримано: {speed}")
        
        return await self.generate_speech(text, voice, speed)

# Створюємо глобальний екземпляр сервісу
openai_tts_service = None

def get_openai_tts_service() -> OpenAITTSService:
    """Отримання екземпляра сервісу OpenAI TTS"""
    global openai_tts_service
    if openai_tts_service is None:
        openai_tts_service = OpenAITTSService()
    return openai_tts_service

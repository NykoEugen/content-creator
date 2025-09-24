import logging
import io
import base64
from typing import Optional, List
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_IMAGE_MODEL, OPENAI_IMAGE_SIZE, OPENAI_IMAGE_QUALITY

logger = logging.getLogger(__name__)

class OpenAIImageService:
    """Сервіс для роботи з OpenAI Image API (генерація зображень)"""
    
    def __init__(self):
        """Ініціалізація клієнта OpenAI для генерації зображень"""
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не встановлено")
        
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_IMAGE_MODEL
        self.default_size = OPENAI_IMAGE_SIZE
        self.default_quality = OPENAI_IMAGE_QUALITY
    
    async def generate_image(self, prompt: str, size: Optional[str] = None, 
                           quality: Optional[str] = None, n: int = 1) -> List[bytes]:
        """
        Генерація зображень за текстовим промтом
        
        Args:
            prompt: Текстовий опис зображення
            size: Розмір зображення (1024x1024, 1792x1024, 1024x1792)
            quality: Якість зображення (standard, hd)
            n: Кількість зображень для генерації (1-10)
            
        Returns:
            Список байтів згенерованих зображень
        """
        try:
            # Використовуємо вказані параметри або дефолтні
            selected_size = size or self.default_size
            selected_quality = quality or self.default_quality
            
            # Обмежуємо кількість зображень
            if n > 10:
                n = 10
                logger.warning("Кількість зображень обмежена до 10")
            
            logger.info(f"Генерація зображення за промтом: {prompt[:100]}...")
            logger.info(f"Параметри: розмір={selected_size}, якість={selected_quality}, кількість={n}")
            
            response = await self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size=selected_size,
                quality=selected_quality,
                n=n
            )
            
            # Отримуємо base64 дані зображень
            image_bytes_list = []
            if response.data:
                for image in response.data:
                    if hasattr(image, 'b64_json') and image.b64_json:
                        # Декодуємо base64 дані
                        image_bytes = base64.b64decode(image.b64_json)
                        image_bytes_list.append(image_bytes)
                        logger.info(f"Отримано зображення розміром {len(image_bytes)} байт")
                    else:
                        logger.warning(f"Зображення без b64_json: {image}")
            
            if not image_bytes_list:
                logger.error("Не отримано жодного валідного зображення")
                raise Exception("API не повернув валідних зображень")
            
            logger.info(f"Згенеровано {len(image_bytes_list)} зображень")
            return image_bytes_list
            
        except Exception as e:
            logger.error(f"Помилка при генерації зображення: {e}")
            raise Exception(f"Не вдалося згенерувати зображення: {str(e)}")
    
    async def generate_image_variation(self, image_url: str, size: Optional[str] = None, 
                                     quality: Optional[str] = None, n: int = 1) -> List[str]:
        """
        Генерація варіацій існуючого зображення
        
        Args:
            image_url: URL існуючого зображення
            size: Розмір зображення
            quality: Якість зображення
            n: Кількість варіацій для генерації
            
        Returns:
            Список URL-ів згенерованих варіацій
        """
        try:
            selected_size = size or self.default_size
            selected_quality = quality or self.default_quality
            
            if n > 10:
                n = 10
                logger.warning("Кількість варіацій обмежена до 10")
            
            logger.info(f"Генерація варіацій зображення: {image_url}")
            
            response = await self.client.images.create_variation(
                image=image_url,
                size=selected_size,
                quality=selected_quality,
                n=n
            )
            
            variation_urls = [image.url for image in response.data]
            logger.info(f"Згенеровано {len(variation_urls)} варіацій")
            
            return variation_urls
            
        except Exception as e:
            logger.error(f"Помилка при генерації варіацій зображення: {e}")
            raise Exception(f"Не вдалося згенерувати варіації зображення: {str(e)}")
    
    async def edit_image(self, image_url: str, mask_url: str, prompt: str, 
                        size: Optional[str] = None, n: int = 1) -> List[str]:
        """
        Редагування зображення
        
        Args:
            image_url: URL зображення для редагування
            mask_url: URL маски для редагування
            prompt: Опис змін
            size: Розмір зображення
            n: Кількість зображень для генерації
            
        Returns:
            Список URL-ів відредагованих зображень
        """
        try:
            selected_size = size or self.default_size
            
            if n > 10:
                n = 10
                logger.warning("Кількість зображень обмежена до 10")
            
            logger.info(f"Редагування зображення за промтом: {prompt[:100]}...")
            
            response = await self.client.images.edit(
                image=image_url,
                mask=mask_url,
                prompt=prompt,
                size=selected_size,
                n=n
            )
            
            edited_urls = [image.url for image in response.data]
            logger.info(f"Відредаговано {len(edited_urls)} зображень")
            
            return edited_urls
            
        except Exception as e:
            logger.error(f"Помилка при редагуванні зображення: {e}")
            raise Exception(f"Не вдалося відредагувати зображення: {str(e)}")
    
    def get_available_sizes(self) -> List[str]:
        """
        Отримання списку доступних розмірів зображень
        
        Returns:
            Список доступних розмірів
        """
        return ['1024x1024', '1024x1536', '1536x1024', 'auto']
    
    def get_available_qualities(self) -> List[str]:
        """
        Отримання списку доступних якостей зображень
        
        Returns:
            Список доступних якостей
        """
        return ['low', 'medium', 'high', 'auto']
    
    def validate_size(self, size: str) -> bool:
        """
        Перевірка чи є розмір валідним
        
        Args:
            size: Розмір для перевірки
            
        Returns:
            True якщо розмір валідний, False інакше
        """
        return size in self.get_available_sizes()
    
    def validate_quality(self, quality: str) -> bool:
        """
        Перевірка чи є якість валідною
        
        Args:
            quality: Якість для перевірки
            
        Returns:
            True якщо якість валідна, False інакше
        """
        return quality.lower() in self.get_available_qualities()
    
    async def generate_image_with_validation(self, prompt: str, size: Optional[str] = None, 
                                           quality: Optional[str] = None, n: int = 1) -> List[bytes]:
        """
        Генерація зображень з валідацією параметрів
        
        Args:
            prompt: Текстовий опис зображення
            size: Розмір зображення
            quality: Якість зображення
            n: Кількість зображень для генерації
            
        Returns:
            Список байтів згенерованих зображень
        """
        if size and not self.validate_size(size):
            available_sizes = self.get_available_sizes()
            raise ValueError(f"Невірний розмір '{size}'. Доступні розміри: {', '.join(available_sizes)}")
        
        if quality and not self.validate_quality(quality):
            available_qualities = self.get_available_qualities()
            raise ValueError(f"Невірна якість '{quality}'. Доступні якості: {', '.join(available_qualities)}")
        
        return await self.generate_image(prompt, size, quality, n)

# Створюємо глобальний екземпляр сервісу
openai_image_service = None

def get_openai_image_service() -> OpenAIImageService:
    """Отримання екземпляра сервісу OpenAI Image"""
    global openai_image_service
    if openai_image_service is None:
        openai_image_service = OpenAIImageService()
    return openai_image_service

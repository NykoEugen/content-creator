import logging
from typing import Optional
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_MAX_TOKENS, OPENAI_TEMPERATURE

logger = logging.getLogger(__name__)

class OpenAIService:
    """Сервіс для роботи з OpenAI API (генерація тексту)"""
    
    def __init__(self):
        """Ініціалізація клієнта OpenAI для генерації тексту"""
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не встановлено")
        
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_MODEL
        self.max_tokens = OPENAI_MAX_TOKENS
        self.temperature = OPENAI_TEMPERATURE
    
    async def generate_text(self, prompt: str, system_message: Optional[str] = None) -> str:
        """
        Генерація тексту за допомогою OpenAI (Chat Completions API)
        
        Args:
            prompt: Запит користувача
            system_message: Системне повідомлення для налаштування поведінки AI
            
        Returns:
            Згенерований текст
        """
        try:
            messages = []
            
            # Додаємо системне повідомлення, якщо воно вказане
            if system_message:
                messages.append({"role": "system", "content": system_message})
            
            # Додаємо запит користувача
            messages.append({"role": "user", "content": prompt})
            
            logger.info(f"Відправка запиту до OpenAI: {prompt[:100]}...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            generated_text = response.choices[0].message.content
            logger.info(f"Отримано відповідь від OpenAI: {generated_text[:100]}...")
            
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Помилка при генерації тексту: {e}")
            return f"Вибачте, виникла помилка при обробці вашого запиту: {str(e)}"
    
    async def generate_creative_text(self, prompt: str) -> str:
        """
        Генерація креативного тексту
        
        Args:
            prompt: Запит користувача
            
        Returns:
            Креативний текст
        """
        system_message = """
        Ти креативний письменник та помічник. Твоя задача - створювати цікавий, 
        захоплюючий контент українською мовою. Відповідай живо, використовуючи 
        емодзі та різноманітні стилі викладу. Будь дружнім та корисним.
        """
        
        return await self.generate_text(prompt, system_message)
    
    async def generate_code(self, prompt: str, language: str = "python") -> str:
        """
        Генерація коду
        
        Args:
            prompt: Опис того, який код потрібно згенерувати
            language: Мова програмування
            
        Returns:
            Згенерований код
        """
        system_message = f"""
        Ти експерт-програміст з {language}. Твоя задача - писати якісний, 
        чистий та добре прокоментований код. Завжди включай коментарі 
        українською мовою та пояснення логіки роботи коду.
        """
        
        code_prompt = f"Створи код на мові {language}: {prompt}"
        return await self.generate_text(code_prompt, system_message)
    
    async def translate_text(self, text: str, target_language: str = "українська") -> str:
        """
        Переклад тексту
        
        Args:
            text: Текст для перекладу
            target_language: Цільова мова
            
        Returns:
            Перекладений текст
        """
        system_message = f"""
        Ти професійний перекладач. Твоя задача - точно перекладати текст 
        на {target_language}, зберігаючи сенс та стиль оригіналу. 
        Перекладай природно та зрозуміло.
        """
        
        prompt = f"Переклади наступний текст на {target_language}: {text}"
        return await self.generate_text(prompt, system_message)
    
    async def summarize_text(self, text: str) -> str:
        """
        Створення резюме тексту
        
        Args:
            text: Текст для резюмування
            
        Returns:
            Резюме тексту
        """
        system_message = """
        Ти експерт з аналізу тексту. Твоя задача - створювати короткі, 
        але інформативні резюме. Виділяй основні ідеї та ключові моменти.
        """
        
        prompt = f"Створи коротке резюме наступного тексту: {text}"
        return await self.generate_text(prompt, system_message)
    
    async def explain_concept(self, concept: str) -> str:
        """
        Пояснення концепції або терміну
        
        Args:
            concept: Концепція для пояснення
            
        Returns:
            Пояснення концепції
        """
        system_message = """
        Ти експерт-педагог. Твоя задача - пояснювати складні концепції 
        простими словами, з прикладами та аналогіями. Будь зрозумілим 
        та корисним.
        """
        
        prompt = f"Поясни простими словами: {concept}"
        return await self.generate_text(prompt, system_message)

# Створюємо глобальний екземпляр сервісу
openai_service = None

def get_openai_service() -> OpenAIService:
    """Отримання екземпляра сервісу OpenAI для генерації тексту"""
    global openai_service
    if openai_service is None:
        openai_service = OpenAIService()
    return openai_service

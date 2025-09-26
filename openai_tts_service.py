import asyncio
import logging
import os
from typing import List, Tuple, Optional

import httpx

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logger = logging.getLogger(__name__)


class OpenAITTSService:
    """
    Асинхронний сервіс для TTS через OpenAI:
      - ретраї при 429/5xx та мережевих помилках
      - контроль таймаутів
      - зручні хелпери get_available_voices() / get_speed_range()
      - generate_speech_with_validation(text, voice, speed) -> bytes (mp3)
    """

    # Стабільні значення за замовчуванням
    _DEFAULT_MODEL = "gpt-4o-mini-tts"
    _DEFAULT_VOICE = "alloy"
    _DEFAULT_SPEED = 1.0
    _MIN_SPEED = 0.25
    _MAX_SPEED = 4.0
    _VOICES = ("alloy", "echo", "fable", "onyx", "nova", "shimmer")

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        request_timeout: float = 60.0,   # загальний таймаут на запит
        connect_timeout: float = 10.0,   # конект
        read_timeout: float = 180.0,     # очікування відповіді (довше, бо TTS)
        write_timeout: float = 60.0,     # надсилання тіла
        max_retries: int = 3,
    ):
        api_key = api_key or OPENAI_API_KEY
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.api_key = api_key
        self.model = model or self._DEFAULT_MODEL
        self.voice = self._DEFAULT_VOICE
        self.speed = self._DEFAULT_SPEED
        self.max_retries = max_retries

        # httpx AsyncClient з таймаутами
        self._timeout = httpx.Timeout(
            timeout=request_timeout,
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
        )
        # HTTP/1.1 keep-alive
        self._client = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=self._timeout,
            http2=False,
        )

        logger.info("OpenAI TTS клієнт успішно ініціалізовано")

    # ---------- Публічні async-хелпери (їх ПОТРІБНО await-ити) ----------

    async def get_available_voices(self) -> List[str]:
        """
        Повертає список допустимих голосів.
        Можна зробити реальний запит до API, але статичний whitelist надійніший.
        """
        # Якщо колись захочеш фетчити з мережі — просто зроби тут запит.
        await asyncio.sleep(0)  # гарантія, що це справді корутина
        return list(self._VOICES)

    async def get_speed_range(self) -> Tuple[float, float]:
        """Діапазон допустимих швидкостей."""
        await asyncio.sleep(0)
        return (self._MIN_SPEED, self._MAX_SPEED)

    # ---------- Основний метод генерації ----------

    async def generate_speech_with_validation(self, text: str, voice: Optional[str], speed: Optional[float]) -> bytes:
        """
        Перевіряє параметри і генерує mp3-байти.
        Кидає виняток із читабельним повідомленням у разі провалу.
        """
        if not text or not text.strip():
            raise ValueError("Порожній текст для озвучки")

        # Валідація голосу/швидкості
        voice = (voice or self.voice or self._DEFAULT_VOICE).lower()
        if voice not in self._VOICES:
            raise ValueError(f"Непідтримуваний голос: {voice}. Доступні: {', '.join(self._VOICES)}")

        if speed is None:
            speed = self.speed or self._DEFAULT_SPEED
        try:
            speed = float(speed)
        except Exception:
            raise ValueError("Швидкість має бути числом")

        if not (self._MIN_SPEED <= speed <= self._MAX_SPEED):
            raise ValueError(f"Швидкість повинна бути від {self._MIN_SPEED} до {self._MAX_SPEED}")

        # Робимо кілька спроб із бекофом
        backoff = 1.0
        last_err: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return await self._request_tts(text=text, voice=voice, speed=speed)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                body = _safe_err_text(e.response)
                # 429/5xx — має сенс спробувати ще
                if status == 429 or 500 <= status < 600:
                    last_err = e
                    logger.warning(f"TTS {status} attempt {attempt}/{self.max_retries}: {body}")
                else:
                    # 4xx (крім 429) — не ретраїмо
                    msg = body or str(e)
                    raise RuntimeError(f"OpenAI TTS HTTP {status}: {msg}") from e
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_err = e
                logger.warning(f"TTS network timeout/errno attempt {attempt}/{self.max_retries}: {e}")
            except Exception as e:
                # інші помилки — можна одну-другу спробу, але зазвичай краще відразу падати
                last_err = e
                logger.warning(f"TTS unexpected error attempt {attempt}/{self.max_retries}: {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 6.0)

        # якщо сюди дійшли — все погано
        if isinstance(last_err, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
            raise RuntimeError("HTTP Client says - Request timeout error") from last_err
        raise RuntimeError(f"TTS failed after {self.max_retries} attempts: {last_err}")

    # ---------- Низькорівневий запит ----------

    async def _request_tts(self, text: str, voice: str, speed: float) -> bytes:
        """
        Виконує один запит до OpenAI TTS і повертає mp3 байти.
        """
        payload = {
            "model": self.model,
            "voice": voice,
            "input": text,
            # OpenAI дозволяє scale швидкості (0.25–4.0)
            "speed": speed,
            # одразу просимо mp3
            "format": "mp3",
        }

        resp = await self._client.post("/audio/speech", json=payload)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            # Дамо шанс зовнішньому обробнику
            raise

        # В API /audio/speech повертається application/octet-stream (тіло — бінарне)
        return resp.content

    # ---------- Закриття клієнта ----------

    async def aclose(self):
        """Закрити httpx.AsyncClient (виклич у on_shutdown)."""
        try:
            await self._client.aclose()
        except Exception as e:
            logger.warning(f"Помилка при закритті httpx клієнта TTS: {e}")


# ---------- Сінглтон-фабрика ----------
_instance: Optional[OpenAITTSService] = None


def get_openai_tts_service() -> OpenAITTSService:
    global _instance
    if _instance is None:
        _instance = OpenAITTSService()
    return _instance


# ---------- Утиліти ----------

def _safe_err_text(response: httpx.Response) -> str:
    try:
        data = response.json()
        # OpenAI зазвичай повертає {"error": {"message": "..."}}
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                return err.get("message") or str(data)
        return str(data)
    except Exception:
        # як fallback — обрізати текст до 500 символів
        t = response.text
        return (t[:500] + "...") if t and len(t) > 500 else (t or "")
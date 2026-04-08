"""
Клиент для LM Studio API.

Модуль предоставляет клиент для взаимодействия с LM Studio,
позволяя получать список моделей, их свойства и отправлять запросы.
LM Studio использует OpenAI-совместимый API.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any, Generator
from pathlib import Path
import os

from lm_agent.api.models import ModelList, ModelInfo, ModelCapabilities


class LMStudioAPIError(Exception):
    """Ошибка API LM Studio."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class LMStudioClient:
    """
    Клиент для взаимодействия с LM Studio API.
    
    Поддерживает:
    - Получение списка доступных моделей
    - Получение детальной информации о модели
    - Отправку запросов на генерацию
    - Проверку подключения
    
    Пример использования:
        client = LMStudioClient(base_url="http://localhost:1234/v1")
        
        # Получить список моделей
        models = client.list_models()
        for model in models:
            print(f"Модель: {model.name}, Контекст: {model.context_window}")
        
        # Отправить запрос
        response = client.chat_completion(
            model="codellama-7b",
            messages=[{"role": "user", "content": "Привет!"}]
        )
        print(response['choices'][0]['message']['content'])
    """
    
    DEFAULT_BASE_URL = "http://localhost:1234/v1"
    DEFAULT_TIMEOUT = 30
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        api_key: Optional[str] = None
    ):
        """
        Инициализация клиента.
        
        Args:
            base_url: URL LM Studio API (по умолчанию http://localhost:1234/v1)
            timeout: Таймаут запросов в секундах
            api_key: API ключ (не требуется для локального LM Studio)
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip('/')
        self.timeout = timeout
        self.api_key = api_key or "lm-studio"  # LM Studio не требует ключ, но некоторые клиенты ожидают
        
        # Кэш моделей
        self._models_cache: Optional[ModelList] = None
        self._models_cache_time: float = 0
        self._cache_ttl: float = 60  # TTL кэша в секундах
    
    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Any:
        """
        Выполнить HTTP запрос к API.
        
        Args:
            endpoint: Endpoint относительно base_url
            method: HTTP метод
            data: Данные запроса (для POST/PUT)
            stream: Режим потоковой передачи
            
        Returns:
            Ответ сервера
            
        Raises:
            LMStudioAPIError: Ошибка запроса
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        body = None
        if data is not None:
            body = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if stream:
                    return self._read_stream(response)
                
                response_data = response.read().decode('utf-8')
                return json.loads(response_data)
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            raise LMStudioAPIError(f"HTTP {e.code}: {error_body}", e.code)
        except urllib.error.URLError as e:
            raise LMStudioAPIError(f"Ошибка подключения: {e.reason}")
        except json.JSONDecodeError as e:
            raise LMStudioAPIError(f"Ошибка парсинга JSON: {e}")
        except TimeoutError:
            raise LMStudioAPIError(f"Таймаут запроса ({self.timeout}с)")
    
    def _read_stream(self, response) -> Generator[str, None, None]:
        """Читать потоковый ответ."""
        buffer = b""
        while True:
            chunk = response.read(1024)
            if not chunk:
                break
            buffer += chunk
            lines = buffer.split(b'\n\n')
            buffer = lines.pop()
            
            for line in lines:
                if line.startswith(b'data: '):
                    data = line[6:].decode('utf-8')
                    if data.strip() == '[DONE]':
                        return
                    yield data
    
    def check_connection(self) -> bool:
        """
        Проверить подключение к LM Studio.
        
        Returns:
            True если подключение успешно
        """
        try:
            self.list_models()
            return True
        except LMStudioAPIError:
            return False
    
    def list_models(self, force_refresh: bool = False) -> ModelList:
        """
        Получить список доступных моделей.
        
        Args:
            force_refresh: Принудительно обновить кэш
            
        Returns:
            ModelList со списком моделей
        """
        import time
        
        # Проверка кэша
        if (
            not force_refresh and 
            self._models_cache is not None and 
            (time.time() - self._models_cache_time) < self._cache_ttl
        ):
            return self._models_cache
        
        # Запрос к API
        response = self._make_request("/models")
        
        # Парсинг ответа
        model_list = ModelList(
            object=response.get('object', 'list'),
            has_more=False
        )
        
        for model_data in response.get('data', []):
            model = self._parse_model(model_data)
            model_list.add(model)
        
        # Обновление кэша
        self._models_cache = model_list
        self._models_cache_time = time.time()
        
        return model_list
    
    def _parse_model(self, data: Dict[str, Any]) -> ModelInfo:
        """
        Распарсить данные модели из API ответа.
        
        Args:
            data: Сырые данные от API
            
        Returns:
            ModelInfo объект
        """
        model_id = data.get('id', 'unknown')
        owned_by = data.get('owned_by', 'unknown')
        created = data.get('created', 0)
        
        # Попытка определить возможности модели по имени
        name_lower = model_id.lower()
        capabilities = ModelCapabilities(
            vision='vision' in name_lower or 'llava' in name_lower,
            tool_use='tool' in name_lower or 'function' in name_lower,
            reasoning='reason' in name_lower or 'cot' in name_lower,
            json_mode='json' in name_lower,
            function_calling=True,  # Большинство современных моделей поддерживают
            embedding='embedding' in name_lower or 'embed' in name_lower,
        )
        
        # Определение контекстного окна по названию модели
        context_window = 4096  # По умолчанию
        if '32k' in name_lower or '32000' in name_lower:
            context_window = 32768
        elif '16k' in name_lower or '16000' in name_lower:
            context_window = 16384
        elif '8k' in name_lower or '8000' in name_lower:
            context_window = 8192
        elif '128k' in name_lower or '128000' in name_lower:
            context_window = 131072
        
        # Максимальные токены (обычно ~80% от контекста)
        max_tokens = min(context_window // 2, 4096)
        
        return ModelInfo(
            id=model_id,
            name=data.get('name', model_id),
            owned_by=owned_by,
            created=created,
            context_window=context_window,
            max_tokens=max_tokens,
            capabilities=capabilities,
            description="",
            tags=[],
            is_default=False,
            status="active",
        )
    
    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """
        Получить информацию о конкретной модели.
        
        Args:
            model_id: ID модели
            
        Returns:
            ModelInfo или None если не найдена
        """
        models = self.list_models()
        return models.get_by_id(model_id) or models.get_by_name(model_id)
    
    def chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Отправить запрос на генерацию completion.
        
        Args:
            model: ID модели
            messages: Список сообщений [{"role": "user|assistant|system", "content": "..."}]
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Максимум выходных токенов
            top_p: Top-p sampling
            frequency_penalty: Штраф за повторения
            presence_penalty: Штраф за новые темы
            stream: Потоковый режим
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ API с генерацией
        """
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stream": stream,
            **kwargs
        }
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        return self._make_request("/chat/completions", method="POST", data=data, stream=stream)
    
    def completion(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Отправить запрос на completion (legacy формат).
        
        Args:
            model: ID модели
            prompt: Текстовый промпт
            temperature: Температура генерации
            max_tokens: Максимум выходных токенов
            **kwargs: Дополнительные параметры
            
        Returns:
            Ответ API с генерацией
        """
        data = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
            **kwargs
        }
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        return self._make_request("/completions", method="POST", data=data)
    
    def clear_cache(self):
        """Очистить кэш моделей."""
        self._models_cache = None
        self._models_cache_time = 0
    
    def set_cache_ttl(self, ttl: float):
        """
        Установить время жизни кэша.
        
        Args:
            ttl: Время в секундах
        """
        self._cache_ttl = max(0, ttl)
    
    @property
    def is_connected(self) -> bool:
        """Проверить подключение (через кэш или реальный запрос)."""
        if self._models_cache is not None:
            return True
        return self.check_connection()

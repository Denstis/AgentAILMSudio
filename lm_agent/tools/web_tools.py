"""
Web Tools for LM Agent.

Provides web interaction capabilities including search, scraping, and API calls.
"""

import requests
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import re

try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    HAS_BEAUTIFULSOUP = False

from .base import BaseTool, ToolResult, ToolDefinition


class WebSearchTool(BaseTool):
    """Инструмент для поиска в интернете через DuckDuckGo."""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Поиск информации в интернете. Возвращает релевантные результаты "
                       "с заголовками, URL и кратким описанием."
        )
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Количество результатов",
                    "default": 5
                },
                "region": {
                    "type": "string",
                    "description": "Регион поиска (ru-ru, en-us, etc.)",
                    "default": "ru-ru"
                }
            },
            returns="List[Dict[str, str]]"
        )
    
    def execute(
        self,
        query: str,
        num_results: int = 5,
        region: str = "ru-ru"
    ) -> ToolResult:
        """
        Выполнить поиск в интернете.
        
        Args:
            query: Поисковый запрос
            num_results: Количество результатов
            region: Регион поиска
            
        Returns:
            ToolResult со списком результатов поиска
        """
        try:
            # Используем DuckDuckGo HTML интерфейс
            url = "https://html.duckduckgo.com/html/"
            params = {
                "q": query,
                "kl": region
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.post(url, data=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            results = []
            
            if HAS_BEAUTIFULSOUP:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for result in soup.select('.result')[:num_results]:
                    title_elem = result.select_one('.result__title')
                    snippet_elem = result.select_one('.result__snippet')
                    url_elem = result.select_one('.result__url')
                    
                    if title_elem and url_elem:
                        title = title_elem.get_text(strip=True)
                        url = url_elem.get('href', '')
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        
                        # Очистка URL от редиректа DuckDuckGo
                        if url.startswith('/l/?uddg='):
                            from urllib.parse import unquote
                            url = unquote(url.split('uddg=')[1].split('&')[0])
                        
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet
                        })
            else:
                # Fallback без BeautifulSoup - простой парсинг
                pattern = r'<a class="result__a" href="([^"]+)">([^<]+)</a>'
                matches = re.findall(pattern, response.text)
                
                for href, title in matches[:num_results]:
                    if href.startswith('/l/?uddg='):
                        from urllib.parse import unquote
                        href = unquote(href.split('uddg=')[1].split('&')[0])
                    results.append({
                        "title": title,
                        "url": href,
                        "snippet": ""
                    })
            
            output = f"Search results for '{query}':\n\n"
            for i, r in enumerate(results, 1):
                output += f"{i}. {r['title']}\n"
                output += f"   URL: {r['url']}\n"
                if r.get('snippet'):
                    output += f"   {r['snippet']}\n"
                output += "\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata={"results": results, "count": len(results)}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Search failed: {str(e)}"
            )


class WebScraperTool(BaseTool):
    """Инструмент для извлечения контента с веб-страниц."""
    
    def __init__(self):
        super().__init__(
            name="web_scrape",
            description="Извлечение основного текста с веб-страницы. "
                       "Автоматически удаляет навигацию, рекламу и другие лишние элементы."
        )
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "url": {
                    "type": "string",
                    "description": "URL страницы для скачивания"
                },
                "extract_links": {
                    "type": "boolean",
                    "description": "Извлечь также ссылки со страницы",
                    "default": False
                },
                "max_length": {
                    "type": "integer",
                    "description": "Максимальная длина текста (0 для безлимита)",
                    "default": 0
                }
            },
            returns="str"
        )
    
    def execute(
        self,
        url: str,
        extract_links: bool = False,
        max_length: int = 0
    ) -> ToolResult:
        """
        Извлечь контент с веб-страницы.
        
        Args:
            url: URL страницы
            extract_links: Извлечь ссылки
            max_length: Максимальная длина текста
            
        Returns:
            ToolResult с содержимым страницы
        """
        try:
            # Валидация URL
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP/HTTPS URLs are allowed")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            if not HAS_BEAUTIFULSOUP:
                return ToolResult(
                    success=False,
                    output="",
                    error="BeautifulSoup is required. Install with: pip install beautifulsoup4"
                )
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Удаление скриптов, стилей и других ненужных элементов
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Попытка найти основной контент
            main_content = None
            
            # Поиск по тегам<main>, <article>
            for tag in ['main', 'article']:
                elem = soup.find(tag)
                if elem:
                    main_content = elem
                    break
            
            # Если не найдено, используем весь body
            if not main_content:
                main_content = soup.find('body') or soup
            
            # Извлечение текста
            text = main_content.get_text(separator='\n', strip=True)
            
            # Ограничение длины
            if max_length > 0 and len(text) > max_length:
                text = text[:max_length] + "... [truncated]"
            
            result = {
                "url": url,
                "title": soup.title.string if soup.title else "",
                "text": text
            }
            
            output = f"Page: {result['title'] or url}\n"
            output += "=" * 50 + "\n"
            output += text
            
            # Извлечение ссылок если нужно
            if extract_links:
                links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    text = link.get_text(strip=True)
                    if href and text:
                        abs_url = urljoin(url, href)
                        links.append({"text": text, "url": abs_url})
                
                result["links"] = links
                output += "\n\nLinks:\n"
                for link in links[:20]:  # Ограничим 20 ссылками
                    output += f"  - {link['text']}: {link['url']}\n"
            
            return ToolResult(
                success=True,
                output=output,
                metadata=result
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Scraping failed: {str(e)}"
            )


class APIClientTool(BaseTool):
    """Универсальный инструмент для HTTP/API запросов."""
    
    def __init__(self):
        super().__init__(
            name="api_call",
            description="Выполнение HTTP запросов (GET, POST, PUT, DELETE) к API. "
                       "Поддерживает заголовки, параметры и JSON тело."
        )
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={
                "method": {
                    "type": "string",
                    "description": "HTTP метод",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
                },
                "url": {
                    "type": "string",
                    "description": "URL endpoint"
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP заголовки",
                    "default": {}
                },
                "params": {
                    "type": "object",
                    "description": "Query параметры",
                    "default": {}
                },
                "json_data": {
                    "type": "object",
                    "description": "JSON тело запроса (для POST/PUT)",
                    "default": None
                },
                "timeout": {
                    "type": "integer",
                    "description": "Таймаут в секундах",
                    "default": 30
                }
            },
            returns="Dict[str, Any]"
        )
    
    def execute(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> ToolResult:
        """
        Выполнить HTTP запрос.
        
        Args:
            method: HTTP метод
            url: URL
            headers: Заголовки
            params: Query параметры
            json_data: JSON тело
            timeout: Таймаут
            
        Returns:
            ToolResult с ответом сервера
        """
        try:
            # Валидация URL
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                raise ValueError("Only HTTP/HTTPS URLs are allowed")
            
            # Валидация метода
            method = method.upper()
            if method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            headers = headers or {}
            headers.setdefault("User-Agent", "LM-Agent/1.0")
            
            # Выполнение запроса
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                timeout=timeout
            )
            
            # Определение типа контента
            content_type = response.headers.get('Content-Type', '')
            
            result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "url": response.url
            }
            
            # Парсинг ответа
            if 'application/json' in content_type:
                try:
                    result["data"] = response.json()
                    output = f"Status: {response.status_code}\n"
                    output += f"Response (JSON):\n{response.json()}"
                except Exception:
                    result["data"] = response.text
                    output = f"Status: {response.status_code}\n{response.text}"
            else:
                result["data"] = response.text
                output = f"Status: {response.status_code}\n{response.text[:2000]}"
            
            return ToolResult(
                success=200 <= response.status_code < 300,
                output=output,
                metadata=result,
                error=None if response.ok else f"HTTP {response.status_code}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"API call failed: {str(e)}"
            )

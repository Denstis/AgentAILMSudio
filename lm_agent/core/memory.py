"""
Memory System for LM Agent.

Provides short-term and long-term memory capabilities using vector storage.
"""

import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class MemoryEntry:
    """Элемент памяти."""
    
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    importance: float = 1.0
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "importance": self.importance,
            "access_count": self.access_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        return cls(
            id=data["id"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            importance=data.get("importance", 1.0),
            access_count=data.get("access_count", 0)
        )


class ShortTermMemory:
    """
    Краткосрочная память с управлением контекстом.
    
    Хранит недавние сообщения и автоматически сжимает старые.
    """
    
    def __init__(self, max_messages: int = 50, compression_threshold: int = 40):
        """
        Инициализация краткосрочной памяти.
        
        Args:
            max_messages: Максимальное количество сообщений
            compression_threshold: Порог для начала сжатия
        """
        self.max_messages = max_messages
        self.compression_threshold = compression_threshold
        self.messages: List[Dict[str, Any]] = []
        self.summary: str = ""
    
    def add(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """
        Добавить сообщение в память.
        
        Args:
            role: Роль (user, assistant, system)
            content: Содержимое сообщения
            metadata: Дополнительные метаданные
        """
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        self.messages.append(entry)
        
        # Сжатие если превышен порог
        if len(self.messages) > self.compression_threshold:
            self._compress()
    
    def _compress(self) -> None:
        """Сжать старые сообщения в summary."""
        # Оставляем только последние сообщения
        messages_to_compress = self.messages[:len(self.messages) - self.compression_threshold]
        
        if messages_to_compress:
            # Создаем краткое содержание сжатых сообщений
            compressed_text = f"[Previous conversation summarized at {datetime.now().isoformat()}]\n"
            self.summary += compressed_text
        
        # Удаляем сжатые сообщения
        self.messages = self.messages[len(self.messages) - self.compression_threshold:]
    
    def get_context(self) -> List[Dict[str, Any]]:
        """
        Получить текущий контекст.
        
        Returns:
            Список сообщений включая summary
        """
        context = []
        if self.summary:
            context.append({
                "role": "system",
                "content": self.summary
            })
        context.extend(self.messages[-self.max_messages:])
        return context
    
    def clear(self) -> None:
        """Очистить память."""
        self.messages = []
        self.summary = ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику памяти."""
        return {
            "message_count": len(self.messages),
            "summary_length": len(self.summary),
            "max_messages": self.max_messages
        }


class SimpleVectorStore:
    """
    Простое векторное хранилище без внешних зависимостей.
    
    Использует TF-IDF подобный подход для поиска похожих документов.
    """
    
    def __init__(self):
        self.documents: Dict[str, MemoryEntry] = {}
        self.index: Dict[str, List[str]] = {}  # inverted index
    
    def add(self, entry: MemoryEntry) -> None:
        """Добавить документ в хранилище."""
        self.documents[entry.id] = entry
        
        # Индексация по словам
        words = set(entry.content.lower().split())
        for word in words:
            if word not in self.index:
                self.index[word] = []
            if entry.id not in self.index[word]:
                self.index[word].append(entry.id)
    
    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """
        Найти похожие документы.
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            
        Returns:
            Список найденных записей
        """
        query_words = set(query.lower().split())
        
        scores: Dict[str, int] = {}
        
        # Подсчет совпадений по словам
        for word in query_words:
            if word in self.index:
                for doc_id in self.index[word]:
                    scores[doc_id] = scores.get(doc_id, 0) + 1
        
        # Сортировка по релевантности
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        
        results = []
        for doc_id in sorted_ids[:top_k]:
            if doc_id in self.documents:
                entry = self.documents[doc_id]
                entry.access_count += 1
                results.append(entry)
        
        return results
    
    def remove(self, entry_id: str) -> bool:
        """Удалить документ по ID."""
        if entry_id not in self.documents:
            return False
        
        entry = self.documents[entry_id]
        del self.documents[entry_id]
        
        # Удаление из индекса
        words = set(entry.content.lower().split())
        for word in words:
            if word in self.index and entry_id in self.index[word]:
                self.index[word].remove(entry_id)
        
        return True
    
    def get_all(self) -> List[MemoryEntry]:
        """Получить все документы."""
        return list(self.documents.values())
    
    def count(self) -> int:
        """Количество документов."""
        return len(self.documents)


class LongTermMemory:
    """
    Долгосрочная память с векторным поиском.
    
    Сохраняет важную информацию между сессиями.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Инициализация долгосрочной памяти.
        
        Args:
            storage_path: Путь для сохранения памяти (опционально)
        """
        self.storage_path = storage_path
        self.vector_store = SimpleVectorStore()
        self._load()
    
    def add(self, content: str, metadata: Optional[Dict] = None, 
            importance: float = 1.0) -> str:
        """
        Добавить воспоминание.
        
        Args:
            content: Содержимое воспоминания
            metadata: Метаданные
            importance: Важность (0.0-1.0)
            
        Returns:
            ID воспоминания
        """
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            metadata=metadata or {},
            importance=importance
        )
        self.vector_store.add(entry)
        self._save()
        return entry.id
    
    def search(self, query: str, top_k: int = 5, 
               min_importance: float = 0.0) -> List[MemoryEntry]:
        """
        Поиск воспоминаний.
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            min_importance: Минимальная важность
            
        Returns:
            Список найденных воспоминаний
        """
        results = self.vector_store.search(query, top_k * 2)  # Берем больше для фильтрации
        
        # Фильтрация по важности
        filtered = [r for r in results if r.importance >= min_importance]
        
        return filtered[:top_k]
    
    def forget(self, entry_id: str) -> bool:
        """Забыть воспоминание."""
        result = self.vector_store.remove(entry_id)
        if result:
            self._save()
        return result
    
    def get_important_memories(self, top_k: int = 10) -> List[MemoryEntry]:
        """Получить самые важные воспоминания."""
        all_memories = self.vector_store.get_all()
        sorted_memories = sorted(
            all_memories, 
            key=lambda x: (x.importance, x.access_count), 
            reverse=True
        )
        return sorted_memories[:top_k]
    
    def _save(self) -> None:
        """Сохранить память на диск."""
        if not self.storage_path:
            return
        
        try:
            data = {
                entry.id: entry.to_dict() 
                for entry in self.vector_store.documents.values()
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save memory: {e}")
    
    def _load(self) -> None:
        """Загрузить память с диска."""
        if not self.storage_path:
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for entry_data in data.values():
                entry = MemoryEntry.from_dict(entry_data)
                self.vector_store.add(entry)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Failed to load memory: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику памяти."""
        all_memories = self.vector_store.get_all()
        avg_importance = sum(m.importance for m in all_memories) / len(all_memories) if all_memories else 0
        
        return {
            "total_memories": len(all_memories),
            "average_importance": avg_importance,
            "storage_path": self.storage_path
        }


class EpisodicMemory:
    """
    Эпизодическая память для хранения истории действий.
    
    Используется для few-shot обучения на собственных ошибках и успехах.
    """
    
    def __init__(self, max_episodes: int = 100):
        """
        Инициализация эпизодической памяти.
        
        Args:
            max_episodes: Максимальное количество эпизодов
        """
        self.max_episodes = max_episodes
        self.episodes: List[Dict[str, Any]] = []
    
    def add_episode(self, task: str, action: str, result: str, 
                    success: bool, lesson: Optional[str] = None) -> None:
        """
        Добавить эпизод.
        
        Args:
            task: Описание задачи
            action: Предпринятое действие
            result: Результат
            success: Был ли успех
            lesson: Извлеченный урок
        """
        episode = {
            "id": str(uuid.uuid4()),
            "task": task,
            "action": action,
            "result": result,
            "success": success,
            "lesson": lesson,
            "timestamp": datetime.now().isoformat()
        }
        self.episodes.append(episode)
        
        # Удаление старых эпизодов
        if len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes:]
    
    def get_similar_episodes(self, task_pattern: str, 
                            success_only: bool = False) -> List[Dict[str, Any]]:
        """
        Найти похожие эпизоды.
        
        Args:
            task_pattern: Паттерн задачи
            success_only: Только успешные эпизоды
            
        Returns:
            Список похожих эпизодов
        """
        episodes = self.episodes
        
        if success_only:
            episodes = [e for e in episodes if e["success"]]
        
        # Простой поиск по ключевым словам
        keywords = set(task_pattern.lower().split())
        scored = []
        
        for episode in episodes:
            score = sum(1 for kw in keywords if kw in episode["task"].lower())
            if score > 0:
                scored.append((score, episode))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:5]]
    
    def get_lessons(self, failure_only: bool = False) -> List[str]:
        """
        Получить извлеченные уроки.
        
        Args:
            failure_only: Только уроки из неудач
            
        Returns:
            Список уроков
        """
        episodes = self.episodes
        if failure_only:
            episodes = [e for e in episodes if not e["success"]]
        
        lessons = [e["lesson"] for e in episodes if e.get("lesson")]
        return list(set(lessons))  # Уникальные уроки
    
    def clear(self) -> None:
        """Очистить эпизодическую память."""
        self.episodes = []

"""Менеджер сессий агентов с управлением контекстом."""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from gmod.infrastructure.llm.factory import LLMProviderFactory
from gmod.infrastructure.db.database import get_database

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """Сообщение агента."""
    role: str  # "user" или "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AgentSession:
    """Сессия агента."""
    agent_id: str
    agent_type: str
    model: str
    messages: List[AgentMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    workspace_context: str = ""
    
    def add_message(self, role: str, content: str) -> None:
        """Добавление сообщения в сессию."""
        self.messages.append(AgentMessage(role=role, content=content))
        self.last_activity = datetime.now()
    
    def get_message_count(self) -> int:
        """Получение количества сообщений."""
        return len(self.messages)
    
    def get_context_summary(self) -> str:
        """Получение краткого контекста сессии."""
        if not self.messages:
            return ""
        
        # Берём последние несколько сообщений для контекста
        recent_messages = self.messages[-5:] if len(self.messages) > 5 else self.messages
        context_parts = []
        
        for msg in recent_messages:
            context_parts.append(f"{msg.role}: {msg.content[:100]}...")
        
        return "\n".join(context_parts)


class SessionManager:
    """Менеджер сессий агентов с управлением контекстом."""
    
    def __init__(self, message_limit: int = 7, config: Dict[str, Any] = None):
        """Инициализация менеджера сессий.
        
        Args:
            message_limit: Лимит сообщений перед суммаризацией
            config: Конфигурация LLM провайдеров
        """
        self.message_limit = message_limit
        self.config = config or {}
        self.db = get_database()
        self.llm_factory = LLMProviderFactory(self.config)
        self._sessions: Dict[str, AgentSession] = {}
    
    def create_session(self, agent_id: str, agent_type: str, model: str, workspace_context: str = "") -> AgentSession:
        """Создание новой сессии агента.
        
        Args:
            agent_id: Уникальный идентификатор агента
            agent_type: Тип агента (archaeologist, detective, architect)
            model: Модель для использования
            workspace_context: Контекст работы
            
        Returns:
            Созданная сессия агента
        """
        session = AgentSession(
            agent_id=agent_id,
            agent_type=agent_type,
            model=model,
            workspace_context=workspace_context
        )
        
        self._sessions[agent_id] = session
        logger.info(f"Created session for agent {agent_id} of type {agent_type}")
        
        return session
    
    def get_session(self, agent_id: str) -> Optional[AgentSession]:
        """Получение сессии агента.
        
        Args:
            agent_id: Идентификатор агента
            
        Returns:
            Сессия агента или None
        """
        return self._sessions.get(agent_id)
    
    def add_message(self, agent_id: str, role: str, content: str) -> None:
        """Добавление сообщения в сессию.
        
        Args:
            agent_id: Идентификатор агента
            role: Роль (user/assistant)
            content: Содержимое сообщения
        """
        session = self.get_session(agent_id)
        if not session:
            raise ValueError(f"Session {agent_id} not found")
        
        session.add_message(role, content)
        
        # Проверяем лимит сообщений
        if session.get_message_count() >= self.message_limit:
            logger.info(f"Message limit reached for agent {agent_id}, triggering summarization")
            self._summarize_and_reset(session)
    
    def _summarize_and_reset(self, session: AgentSession) -> None:
        """Суммаризация диалога и сброс контекста.
        
        Args:
            session: Сессия для суммаризации
        """
        try:
            # Получаем суммаризацию через LLM
            summary = self._generate_summary(session)
            
            # Сохраняем полную историю в БД
            self._save_session_history(session)
            
            # Сбрасываем сообщения, оставляем только суммаризацию
            session.messages = [
                AgentMessage(role="system", content=f"Previous conversation summary: {summary}")
            ]
            
            logger.info(f"Session {session.agent_id} summarized and reset")
            
        except Exception as e:
            logger.error(f"Error during summarization: {e}")
            # При ошибке просто очищаем старые сообщения
            session.messages = session.messages[-3:]  # Оставляем последние 3
    
    def _generate_summary(self, session: AgentSession) -> str:
        """Генерация суммаризации диалога.
        
        Args:
            session: Сессия для суммаризации
            
        Returns:
            Суммаризация диалога
        """
        # Формируем промпт для суммаризации
        conversation_text = "\n".join([
            f"{msg.role}: {msg.content}" 
            for msg in session.messages
        ])
        
        summary_prompt = f"""Summarize the following conversation between a user and an AI assistant. 
Focus on key points, decisions made, and action items.

Conversation:
{conversation_text}

Provide a concise summary in the following format:
Summary: [brief summary]
Key points: [list of key points]
Action items: [list of action items if any]"""
        
        try:
            summary = self.llm_factory.generate_with_fallback(
                summary_prompt,
                temperature=0.3,
                max_tokens=500
            )
            return summary
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Summary generation failed: {str(e)}"
    
    def _save_session_history(self, session: AgentSession) -> None:
        """Сохранение истории сессии в БД.
        
        Args:
            session: Сессия для сохранения
        """
        try:
            # Сохраняем каждое сообщение как отдельную запись
            for msg in session.messages:
                self.db.save_ai_report(
                    repo_id=session.workspace_context or "unknown",
                    commit_hash="session_history",
                    agent_type=session.agent_type,
                    prompt=msg.content if msg.role == "user" else "",
                    response_json=msg.content if msg.role == "assistant" else "",
                    risk_score=0  # Для истории не оцениваем риск
                )
            
            logger.info(f"Saved {len(session.messages)} messages from session {session.agent_id}")
            
        except Exception as e:
            logger.error(f"Error saving session history: {e}")
    
    def generate_response(self, agent_id: str, user_message: str, system_prompt: str = "") -> str:
        """Генерация ответа агента.
        
        Args:
            agent_id: Идентификатор агента
            user_message: Сообщение пользователя
            system_prompt: Системный промпт агента
            
        Returns:
            Ответ агента
        """
        session = self.get_session(agent_id)
        if not session:
            raise ValueError(f"Session {agent_id} not found")
        
        # Добавляем сообщение пользователя
        self.add_message(agent_id, "user", user_message)
        
        # Формируем контекст для LLM
        messages = []
        
        # Добавляем системный промпт
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Добавляем контекст рабочей области
        if session.workspace_context:
            messages.append({
                "role": "system", 
                "content": f"Workspace context: {session.workspace_context}"
            })
        
        # Добавляем историю сообщений
        for msg in session.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Генерируем ответ — конвертируем messages в единый prompt для провайдеров
        prompt_parts = []
        for msg in messages:
            role_label = msg["role"].upper()
            prompt_parts.append(f"[{role_label}]: {msg['content']}")
        full_prompt = "\n\n".join(prompt_parts)
        
        try:
            response = self.llm_factory.generate_with_fallback(
                full_prompt,
                temperature=0.7,
                max_tokens=2000
            )
            
            # Добавляем ответ агента
            self.add_message(agent_id, "assistant", response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    def delete_session(self, agent_id: str) -> None:
        """Удаление сессии агента.
        
        Args:
            agent_id: Идентификатор агента
        """
        if agent_id in self._sessions:
            # Сохраняем историю перед удалением
            session = self._sessions[agent_id]
            self._save_session_history(session)
            
            del self._sessions[agent_id]
            logger.info(f"Deleted session {agent_id}")
    
    def get_active_sessions(self) -> List[str]:
        """Получение списка активных сессий.
        
        Returns:
            Список идентификаторов активных сессий
        """
        return list(self._sessions.keys())
    
    def cleanup_inactive_sessions(self, max_age_hours: int = 24) -> int:
        """Очистка неактивных сессий.
        
        Args:
            max_age_hours: Максимальный возраст сессии в часах
            
        Returns:
            Количество удалённых сессий
        """
        now = datetime.now()
        to_delete = []
        
        for agent_id, session in self._sessions.items():
            age_hours = (now - session.last_activity).total_seconds() / 3600
            if age_hours > max_age_hours:
                to_delete.append(agent_id)
        
        for agent_id in to_delete:
            self.delete_session(agent_id)
        
        logger.info(f"Cleaned up {len(to_delete)} inactive sessions")
        return len(to_delete)

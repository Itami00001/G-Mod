"""ChatService — диалоги с персистентностью (ТЗ §7-10, §30).

Пайплайн сообщения (ТЗ §8):
    System Prompt + Workspace Context + Repository Context +
    Conversation History + Current User Message  →  LLM

Вопрос пользователя ОБЯЗАТЕЛЬНО уходит в LLM (запрет старой схемы,
где UI получал user_message, а usecase его игнорировал).

Контекст (ТЗ §10): до message_limit — вся история; при достижении —
старые сообщения сворачиваются в ChatSession.summary, а ПОЛНАЯ история
остаётся в chat_messages.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ChatService:
    """Сервис чата: сессии, сообщения, контекст, суммаризация."""

    def __init__(self, db=None, llm_config: Optional[Dict[str, Any]] = None,
                 message_limit: int = 7):
        """Инициализация.

        Args:
            db: Database (по умолчанию глобальная)
            llm_config: конфиг для LLMProviderFactory
            message_limit: лимит сообщений до суммаризации
        """
        if db is None:
            from gmod.infrastructure.db.database import get_database
            db = get_database()
        self.db = db
        self.llm_config = llm_config or {}
        self.message_limit = message_limit

    # ---------------- сессии ----------------

    def get_or_create_session(self, workspace_id: str = "default",
                              repository_id: str = "",
                              provider: str = "", model: str = "") -> Dict[str, Any]:
        """Активная сессия workspace или новая."""
        sessions = self.db.get_chat_sessions(workspace_id)
        for s in sessions:
            if (s.get("repository_id", "") or "") == (repository_id or ""):
                return s
        session_id = f"chat_{uuid.uuid4().hex[:8]}"
        session = {
            "id": session_id,
            "workspace_id": workspace_id,
            "repository_id": repository_id or "",
            "provider": provider,
            "model": model,
            "title": "Новый диалог",
            "summary": "",
        }
        self.db.save_chat_session(session)
        logger.info("chat: новая сессия %s (repo=%s)", session_id, repository_id)
        return session

    def list_sessions(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        """Все сессии workspace."""
        return self.db.get_chat_sessions(workspace_id)

    def rename_session(self, session_id: str, title: str) -> None:
        """Переименовать диалог (ТЗ §26: название диалога)."""
        session = self.db.get_chat_session(session_id) or {"id": session_id}
        session["title"] = title.strip() or session.get("title", "Новый диалог")
        self.db.save_chat_session(session)

    def clear_session(self, session_id: str) -> None:
        """Очистка только текущей сессии (ТЗ §26)."""
        self.db.clear_chat_session(session_id)

    def delete_session(self, session_id: str) -> None:
        """Удаление сессии с сообщениями."""
        self.db.delete_chat_session(session_id)

    def delete_message(self, message_id: int) -> None:
        """Удаление одного сообщения (ТЗ §26)."""
        self.db.delete_chat_message(message_id)

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """История сессии."""
        return self.db.get_chat_messages(session_id)

    # ---------------- отправка (ТЗ §8) ----------------

    def send_message(self, session_id: str, user_text: str,
                     system_prompt: str = "",
                     workspace_context: str = "",
                     repository_context: str = "",
                     llm_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Отправка сообщения пользователя в LLM.

        Args:
            session_id: сессия
            user_text: ВОПРОС ПОЛЬЗОВАТЕЛЯ (обязательно уходит в LLM)
            system_prompt: системный промпт
            workspace_context: контекст workspace
            repository_context: контекст репозитория (файлы, метрики, коммит)
            llm_kwargs: temperature / max_tokens

        Returns:
            {"status": "success", "message": {...assistant...}}
            {"status": "error", "message": ..., "hint": ...}
        """
        text = (user_text or "").strip()
        if not text:
            return {"status": "error", "message": "Пустое сообщение", "hint": ""}

        session = self.db.get_chat_session(session_id)
        if not session:
            return {"status": "error", "message": "Сессия не найдена",
                    "hint": "Создайте новый диалог."}

        # 1. Сохраняем вопрос СРАЗУ (ТЗ §9).
        seq = self.db.next_message_sequence(session_id)
        self.db.save_chat_message({
            "session_id": session_id, "role": "user", "content": text,
            "provider": session.get("provider", ""), "model": session.get("model", ""),
            "sequence": seq,
        })
        # Заголовок диалога — из первого вопроса.
        if session.get("title", "Новый диалог") == "Новый диалог":
            session["title"] = text[:60]
            self.db.save_chat_session(session)
        logger.info("chat: вопрос сохранён (сессия %s, seq %d)", session_id, seq)

        # 2. История + суммаризация при лимите (ТЗ §10).
        history = self.db.get_chat_messages(session_id)
        context_messages = self._apply_limit(session, history)

        # 3. Сборка пайплайна: system + workspace + repo + history + ВОПРОС.
        parts = []
        if system_prompt:
            parts.append(f"[SYSTEM]: {system_prompt}")
        if workspace_context:
            parts.append(f"[WORKSPACE]: {workspace_context}")
        if repository_context:
            parts.append(f"[REPOSITORY]: {repository_context}")
        for m in context_messages:
            role = str(m.get("role", "user")).upper()
            parts.append(f"[{role}]: {m.get('content', '')}")
        full_prompt = "\n\n".join(parts)
        logger.info("chat: пайплайн собран (%d блоков), вопрос включён", len(parts))

        # 4. Генерация.
        try:
            from gmod.infrastructure.llm.factory import LLMProviderFactory
            factory = LLMProviderFactory(self.llm_config)
            answer = factory.generate_with_fallback(full_prompt, **(llm_kwargs or {}))
        except Exception as e:
            logger.error("chat: генерация не удалась: %s", e)
            return {
                "status": "error",
                "message": f"LLM generation failed: {e}",
                "hint": "Проверьте статус нейросети во вкладке «Чат» (кнопка «Проверить»).",
            }

        # 5. Сохраняем ответ СРАЗУ (ТЗ §9).
        assistant_msg = {
            "session_id": session_id, "role": "assistant", "content": answer,
            "provider": session.get("provider", ""), "model": session.get("model", ""),
            "sequence": self.db.next_message_sequence(session_id),
        }
        assistant_msg["id"] = self.db.save_chat_message(assistant_msg)
        logger.info("chat: ответ сохранён (сессия %s)", session_id)
        return {"status": "success", "message": assistant_msg}

    def regenerate(self, session_id: str, system_prompt: str = "",
                   workspace_context: str = "", repository_context: str = "",
                   llm_kwargs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Повторная генерация последнего ответа (ТЗ §26)."""
        history = self.db.get_chat_messages(session_id)
        # Удаляем последний assistant-ответ, вопрос остаётся.
        for m in reversed(history):
            if m.get("role") == "assistant":
                self.db.delete_chat_message(m["id"])
                break
        history = self.db.get_chat_messages(session_id)
        last_user = next((m for m in reversed(history) if m.get("role") == "user"), None)
        if not last_user:
            return {"status": "error", "message": "Нет вопроса для повтора", "hint": ""}
        # Удаляем сохранённый дубликат вопроса? Нет — вопрос один, генерим заново.
        session = self.db.get_chat_session(session_id) or {}
        context_messages = [m for m in history if m.get("id") != last_user.get("id")]
        parts = []
        if system_prompt:
            parts.append(f"[SYSTEM]: {system_prompt}")
        if workspace_context:
            parts.append(f"[WORKSPACE]: {workspace_context}")
        if repository_context:
            parts.append(f"[REPOSITORY]: {repository_context}")
        for m in context_messages:
            parts.append(f"[{str(m.get('role', 'user')).upper()}]: {m.get('content', '')}")
        parts.append(f"[USER]: {last_user.get('content', '')}")
        try:
            from gmod.infrastructure.llm.factory import LLMProviderFactory
            factory = LLMProviderFactory(self.llm_config)
            answer = factory.generate_with_fallback("\n\n".join(parts),
                                                    **(llm_kwargs or {}))
        except Exception as e:
            return {"status": "error", "message": f"LLM generation failed: {e}",
                    "hint": "Проверьте статус нейросети."}
        assistant_msg = {
            "session_id": session_id, "role": "assistant", "content": answer,
            "provider": session.get("provider", ""), "model": session.get("model", ""),
            "sequence": self.db.next_message_sequence(session_id),
        }
        assistant_msg["id"] = self.db.save_chat_message(assistant_msg)
        return {"status": "success", "message": assistant_msg}

    # ---------------- контекст (ТЗ §10) ----------------

    def _apply_limit(self, session: Dict[str, Any],
                     history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """История для промпта: summary + свежие; при лимите — свернуть старые.

        Полная история НЕ удаляется из chat_messages.
        """
        non_system = [m for m in history if m.get("role") in ("user", "assistant")]
        if len(non_system) < self.message_limit:
            return self._with_summary(session, non_system)
        # Сворачиваем всё, кроме последних 4, в summary.
        keep = non_system[-4:]
        old = non_system[:-4]
        summary_add = self._summarize(old)
        new_summary = ((session.get("summary") or "") + "\n" + summary_add).strip()
        session["summary"] = new_summary[-2000:]
        self.db.save_chat_session(session)
        logger.info("chat: контекст свёрнут в summary (сессия %s)", session.get("id"))
        return self._with_summary(session, keep)

    @staticmethod
    def _with_summary(session: Dict[str, Any],
                      messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if session.get("summary"):
            return [{"role": "system",
                     "content": f"Previous conversation summary: {session['summary']}"}] + messages
        return messages

    def _summarize(self, messages: List[Dict[str, Any]]) -> str:
        """Суммаризация старых сообщений через LLM (fallback — срез)."""
        if not messages:
            return ""
        text = "\n".join(f"{m.get('role')}: {str(m.get('content', ''))[:300]}"
                         for m in messages)
        try:
            from gmod.infrastructure.llm.factory import LLMProviderFactory
            factory = LLMProviderFactory(self.llm_config)
            return factory.generate_with_fallback(
                "Summarize briefly in Russian (facts, decisions):\n" + text,
                temperature=0.3, max_tokens=400)
        except Exception as e:
            logger.warning("chat: суммаризация не удалась: %s", e)
            return text[:1000]

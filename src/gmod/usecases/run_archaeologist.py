"""Use case для запуска агента-археолога."""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from gmod.domain.entities import Repository, Commit
from gmod.domain.schemas import ArchaeologistResponse, ErrorResponse
from gmod.domain.prompts import ARCHAEOLOGIST_SYSTEM_PROMPT, ARCHAEOLOGIST_ANALYSIS_PROMPT
from gmod.infrastructure.llm.session_manager import SessionManager
from gmod.infrastructure.git.git_parser import GitParser
from gmod.infrastructure.db.database import get_database
from gmod.usecases.analyze_repository import AnalyzeRepositoryUseCase

logger = logging.getLogger(__name__)


class RunArchaeologistUseCase:
    """Use case для запуска агента-археолога."""
    
    def __init__(self, config: Dict[str, Any]):
        """Инициализация use case.
        
        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.db = get_database()
        
        # Инициализация менеджера сессий
        llm_config = config.get("llm", {})
        message_limit = llm_config.get("message_limit", 7)
        self.session_manager = SessionManager(message_limit=message_limit, config=config)
        
        # Инициализация парсера
        diff_only = config.get("analysis", {}).get("depth", "full") == "diff"
        self.git_parser = GitParser(diff_only=diff_only)
        
        # Use case для анализа репозитория
        self.analyze_usecase = AnalyzeRepositoryUseCase(diff_only=diff_only)
    
    def execute(
        self,
        repository: Repository,
        commit_hash: str,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Выполнение анализа агента-археолога.
        
        Args:
            repository: Репозиторий для анализа
            commit_hash: Хеш коммита для анализа
            agent_id: Идентификатор агента (если None, генерируется)
            
        Returns:
            Результат анализа с AI-отчётом
        """
        if not agent_id:
            agent_id = f"archaeologist_{commit_hash[:8]}"
        
        logger.info(f"Starting archaeologist analysis for commit {commit_hash}")
        
        try:
            # Получаем информацию о коммите
            commits = self.git_parser.get_commits(repository.id, limit=100)
            target_commit = next((c for c in commits if c.hash == commit_hash), None)
            
            if not target_commit:
                return {
                    "status": "error",
                    "message": f"Commit {commit_hash} not found",
                    "agent_id": agent_id
                }
            
            # Получаем результаты анализа метрик
            metrics_results = self.analyze_usecase.get_analysis_results(repository.id, commit_hash)
            
            if not metrics_results:
                return {
                    "status": "error",
                    "message": "No metrics found for commit",
                    "agent_id": agent_id
                }
            
            # Формируем сводку метрик
            metrics_summary = self._format_metrics_summary(metrics_results)
            
            # Получаем diff для файлов
            changed_files = self._get_changed_files(repository, commit_hash)
            file_diffs = []
            
            for file_path in changed_files[:5]:  # Ограничиваем до 5 файлов для анализа
                file_diff = self.git_parser.get_file_diff(repository.id, commit_hash, file_path)
                if file_diff:
                    file_diffs.append(self._format_file_diff(file_diff))
            
            if not file_diffs:
                return {
                    "status": "error",
                    "message": "No file diffs available",
                    "agent_id": agent_id
                }
            
            # Создаём сессию агента
            workspace_context = f"Repository: {repository.name}, Commit: {commit_hash}"
            self.session_manager.create_session(
                agent_id=agent_id,
                agent_type="archaeologist",
                model="default",
                workspace_context=workspace_context
            )
            
            # Формируем промпт
            prompt = ARCHAEOLOGIST_ANALYSIS_PROMPT.format(
                commit_hash=commit_hash,
                author=target_commit.author,
                commit_message=target_commit.message,
                date=target_commit.date.isoformat(),
                file_diff="\n\n".join(file_diffs),
                metrics_summary=metrics_summary
            )
            
            # Генерируем ответ через LLM
            try:
                response_text = self.session_manager.generate_response(
                    agent_id=agent_id,
                    user_message=prompt,
                    system_prompt=ARCHAEOLOGIST_SYSTEM_PROMPT
                )
                
                # Парсим JSON ответ
                response_data = self._parse_llm_response(response_text)
                
                if isinstance(response_data, ErrorResponse):
                    return {
                        "status": "error",
                        "message": response_data.error,
                        "error_type": response_data.error_type,
                        "agent_id": agent_id
                    }
                
                # Сохраняем отчёт в БД
                report_id = self.db.save_ai_report(
                    repo_id=repository.id,
                    commit_hash=commit_hash,
                    agent_type="archaeologist",
                    prompt=prompt,
                    response_json=response_text,
                    risk_score=response_data.risk_score
                )
                
                logger.info(f"Archaeologist analysis completed for commit {commit_hash}, report ID: {report_id}")
                
                return {
                    "status": "success",
                    "agent_id": agent_id,
                    "report_id": report_id,
                    "analysis": response_data.model_dump(),
                    "commit_hash": commit_hash,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error during LLM generation: {e}")
                return {
                    "status": "error",
                    "message": f"LLM generation failed: {str(e)}",
                    "agent_id": agent_id
                }
            
        except Exception as e:
            logger.error(f"Error in archaeologist analysis: {e}")
            return {
                "status": "error",
                "message": f"Analysis failed: {str(e)}",
                "agent_id": agent_id
            }
    
    def _format_metrics_summary(self, metrics_results: list) -> str:
        """Форматирование сводки метрик.
        
        Args:
            metrics_results: Результаты метрик
            
        Returns:
            Отформатированная сводка
        """
        # Группируем метрики по категориям
        by_unit = {}
        for metric in metrics_results:
            unit_key = f"{metric['unit_type']}:{metric['unit_name']}"
            if unit_key not in by_unit:
                by_unit[unit_key] = []
            by_unit[unit_key].append(metric)
        
        summary_parts = []
        for unit_key, unit_metrics in by_unit.items():
            summary_parts.append(f"\n{unit_key}:")
            for metric in unit_metrics[:10]:  # Ограничиваем количество метрик
                summary_parts.append(f"  {metric['metric_name']}: {metric['value']:.2f}")
        
        return "\n".join(summary_parts)
    
    def _format_file_diff(self, file_diff) -> str:
        """Форматирование diff файла.
        
        Args:
            file_diff: Diff файла
            
        Returns:
            Отформатированный diff
        """
        status = "MODIFIED"
        if file_diff.is_added:
            status = "ADDED"
        elif file_diff.is_deleted:
            status = "DELETED"
        
        result = f"File: {file_diff.file_path} ({status})\n"
        
        if file_diff.new_content:
            result += f"New content (first 500 chars):\n{file_diff.new_content[:500]}\n"
        
        if file_diff.old_content:
            result += f"Old content (first 500 chars):\n{file_diff.old_content[:500]}\n"
        
        return result
    
    def _get_changed_files(self, repository: Repository, commit_hash: str) -> list:
        """Получение изменённых файлов.
        
        Args:
            repository: Репозиторий
            commit_hash: Хеш коммита
            
        Returns:
            Список изменённых файлов
        """
        try:
            # Используем метод из analyze_repository
            return self.analyze_usecase._get_changed_files(repository, commit_hash)
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []
    
    def _parse_llm_response(self, response_text: str):
        """Парсинг ответа LLM.
        
        Args:
            response_text: Текст ответа от LLM
            
        Returns:
            ArchaeologistResponse или ErrorResponse
        """
        try:
            # Пытаемся извлечь JSON из ответа
            # LLM может добавить текст вокруг JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                data = json.loads(json_text)
                return ArchaeologistResponse(**data)
            else:
                # Если не найден JSON, возвращаем ошибку
                return ErrorResponse(
                    error="No valid JSON found in response",
                    error_type="parse_error",
                    fallback_attempted=False
                )
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return ErrorResponse(
                error=f"Invalid JSON in response: {str(e)}",
                error_type="json_error",
                fallback_attempted=False
            )
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return ErrorResponse(
                error=f"Parse error: {str(e)}",
                error_type="unknown_error",
                fallback_attempted=False
            )
    
    def get_archaeologist_reports(self, repo_id: str) -> list:
        """Получение всех отчётов археолога.
        
        Args:
            repo_id: ID репозитория
            
        Returns:
            Список отчётов
        """
        return self.db.get_ai_reports(repo_id)

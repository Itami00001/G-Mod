"""Use case для анализа репозитория."""

import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from gmod.domain.entities import Repository, Commit, CodeUnit, MetricResult
from gmod.infrastructure.git.git_parser import GitParser
from gmod.infrastructure.parsers.factory import ParserFactory
from gmod.infrastructure.metrics.factory import MetricFactory
from gmod.infrastructure.db.database import get_database

logger = logging.getLogger(__name__)


class AnalyzeRepositoryUseCase:
    """Use case для анализа репозитория."""
    
    def __init__(self, diff_only: bool = False):
        """Инициализация use case.
        
        Args:
            diff_only: Если True, анализирует только diff, иначе файл целиком
        """
        self.diff_only = diff_only
        self.git_parser = GitParser(diff_only=diff_only)
        self.db = get_database()
    
    def execute(self, repository: Repository, commit_hash: Optional[str] = None) -> Dict:
        """Выполнение анализа репозитория.
        
        Args:
            repository: Сущность репозитория
            commit_hash: Хеш коммита для анализа (если None, анализирует последний коммит)
            
        Returns:
            Словарь с результатами анализа
        """
        logger.info(f"Starting analysis of repository: {repository.id}")
        
        # Сохранение информации о репозитории
        self.git_parser.save_repository_info(repository)
        
        # Получение коммитов
        commits = self.git_parser.get_commits(repository.id, limit=100)
        
        # Определение коммита для анализа
        target_commit = commit_hash
        if not target_commit and commits:
            target_commit = commits[0].hash
        
        if not target_commit:
            logger.warning("No commits found for analysis")
            return {"status": "error", "message": "No commits found"}
        
        logger.info(f"Analyzing commit: {target_commit}")
        
        # Получение изменённых файлов
        changed_files = self._get_changed_files(repository, target_commit)
        
        if not changed_files:
            logger.warning("No changed files found")
            return {"status": "error", "message": "No changed files found"}
        
        logger.info(f"Found {len(changed_files)} changed files")
        
        # Анализ каждого файла
        results = {
            "status": "success",
            "repository_id": repository.id,
            "commit_hash": target_commit,
            "files_analyzed": 0,
            "units_analyzed": 0,
            "metrics_computed": 0,
            "errors": []
        }
        
        for file_path in changed_files:
            try:
                file_result = self._analyze_file(repository, target_commit, file_path)
                results["files_analyzed"] += 1
                results["units_analyzed"] += file_result["units_analyzed"]
                results["metrics_computed"] += file_result["metrics_computed"]
                
                if file_result["errors"]:
                    results["errors"].extend(file_result["errors"])
                    
            except Exception as e:
                error_msg = f"Error analyzing file {file_path}: {e}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
        
        logger.info(f"Analysis completed: {results['files_analyzed']} files, "
                    f"{results['units_analyzed']} units, {results['metrics_computed']} metrics")
        
        return results
    
    def _get_changed_files(self, repository: Repository, commit_hash: str) -> List[str]:
        """Получение списка изменённых файлов в коммите."""
        try:
            repo_path = Path(repository.local_path)
            import git
            repo = git.Repo(repo_path)
            commit = repo.commit(commit_hash)
            
            # Получение изменённых файлов
            if commit.parents:
                parent = commit.parents[0]
                diffs = parent.diff(commit)
            else:
                diffs = commit.diff(git.NULL_TREE)
            
            changed_files = []
            for diff in diffs:
                if diff.a_path:
                    changed_files.append(diff.a_path)
                if diff.b_path:
                    changed_files.append(diff.b_path)
            
            # Убираем дубликаты и фильтруем по поддерживаемым языкам
            changed_files = list(set(changed_files))
            changed_files = [f for f in changed_files if self._is_supported_file(f)]
            
            return changed_files
            
        except Exception as e:
            logger.error(f"Error getting changed files: {e}")
            return []
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Проверка, поддерживается ли файл."""
        # Определяем язык по расширению
        path = Path(file_path)
        language = ParserFactory.detect_language(path)
        
        # Проверяем, есть ли парсер для этого языка
        parser = ParserFactory.get_parser(language)
        return parser is not None
    
    def _analyze_file(self, repository: Repository, commit_hash: str, file_path: str) -> Dict:
        """Анализ отдельного файла."""
        result = {
            "file_path": file_path,
            "units_analyzed": 0,
            "metrics_computed": 0,
            "errors": []
        }
        
        try:
            # Получение diff файла
            file_diff = self.git_parser.get_file_diff(repository.id, commit_hash, file_path)
            
            if not file_diff:
                result["errors"].append(f"Could not get diff for {file_path}")
                return result
            
            # Определение содержимого для анализа
            content = file_diff.new_content if file_diff.new_content else file_diff.old_content
            if not content:
                result["errors"].append(f"No content available for {file_path}")
                return result
            
            # Определение языка
            path = Path(file_path)
            language = ParserFactory.detect_language(path)
            
            # Парсинг файла на единицы кода
            units = ParserFactory.parse_file(path, content, language)
            
            if not units:
                result["errors"].append(f"No code units found in {file_path}")
                return result
            
            logger.debug(f"Parsed {len(units)} code units from {file_path}")
            
            # Получение коммитов для VCS метрик
            commits = self.git_parser.get_commits(repository.id, limit=100)
            
            # Вычисление метрик для каждой единицы кода
            for unit in units:
                try:
                    # Вычисление всех метрик
                    metrics = MetricFactory.compute_all_metrics(unit)
                    
                    # Сохранение метрик в БД
                    for metric in metrics:
                        self._save_metric(repository.id, commit_hash, metric)
                    
                    result["metrics_computed"] += len(metrics)
                    result["units_analyzed"] += 1
                    
                except Exception as e:
                    error_msg = f"Error computing metrics for {unit.name} in {file_path}: {e}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error analyzing file {file_path}: {e}"
            logger.error(error_msg)
            result["errors"].append(error_msg)
        
        return result
    
    def _save_metric(self, repo_id: str, commit_hash: str, metric: MetricResult) -> None:
        """Сохранение метрики в БД с кэшированием."""
        try:
            # Проверяем кэш
            cached_value = self.db.get_cached_metric(
                repo_id=repo_id,
                commit_hash=commit_hash,
                file_path=metric.file_path,
                unit_type=metric.unit_type,
                unit_name=metric.unit_name,
                metric_name=metric.metric_name
            )
            
            if cached_value is not None:
                logger.debug(f"Metric {metric.metric_name} for {metric.unit_name} already cached")
                return
            
            # Сохраняем в БД
            self.db.save_metric(
                repo_id=repo_id,
                commit_hash=commit_hash,
                file_path=metric.file_path,
                unit_type=metric.unit_type,
                unit_name=metric.unit_name,
                metric_name=metric.metric_name,
                value=metric.value
            )
            
        except Exception as e:
            logger.error(f"Error saving metric: {e}")
    
    def get_analysis_results(self, repo_id: str, commit_hash: Optional[str] = None) -> List[Dict]:
        """Получение результатов анализа из БД.
        
        Args:
            repo_id: ID репозитория
            commit_hash: Хеш коммита (если None, возвращает все коммиты)
            
        Returns:
            Список результатов анализа
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                if commit_hash:
                    cursor.execute("""
                        SELECT file_path, unit_type, unit_name, metric_name, value, timestamp
                        FROM raw_metrics
                        WHERE repo_id = ? AND commit_hash = ?
                        ORDER BY file_path, unit_name, metric_name
                    """, (repo_id, commit_hash))
                else:
                    cursor.execute("""
                        SELECT file_path, unit_type, unit_name, metric_name, value, timestamp
                        FROM raw_metrics
                        WHERE repo_id = ?
                        ORDER BY commit_hash, file_path, unit_name, metric_name
                    """, (repo_id,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "file_path": row[0],
                        "unit_type": row[1],
                        "unit_name": row[2],
                        "metric_name": row[3],
                        "value": row[4],
                        "timestamp": row[5]
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting analysis results: {e}")
            return []
    
    def get_metrics_summary(self, repo_id: str, commit_hash: str) -> Dict:
        """Получение сводки по метрикам.
        
        Args:
            repo_id: ID репозитория
            commit_hash: Хеш коммита
            
        Returns:
            Сводка по метрикам
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Общая статистика
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT file_path) as files,
                        COUNT(DISTINCT unit_name) as units,
                        COUNT(DISTINCT metric_name) as metrics,
                        COUNT(*) as total_metrics
                    FROM raw_metrics
                    WHERE repo_id = ? AND commit_hash = ?
                """, (repo_id, commit_hash))
                
                stats = cursor.fetchone()
                
                # Статистика по категориям метрик
                cursor.execute("""
                    SELECT metric_name, AVG(value) as avg_value, MAX(value) as max_value, MIN(value) as min_value
                    FROM raw_metrics
                    WHERE repo_id = ? AND commit_hash = ?
                    GROUP BY metric_name
                    ORDER BY metric_name
                """, (repo_id, commit_hash))
                
                metric_stats = []
                for row in cursor.fetchall():
                    metric_stats.append({
                        "metric_name": row[0],
                        "avg_value": row[1],
                        "max_value": row[2],
                        "min_value": row[3]
                    })
                
                return {
                    "files": stats[0],
                    "units": stats[1],
                    "metrics": stats[2],
                    "total_metrics": stats[3],
                    "metric_details": metric_stats
                }
                
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}

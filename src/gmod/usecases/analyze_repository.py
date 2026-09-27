"""Use case для анализа репозитория."""

import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from gmod.domain.entities import Repository, Commit, CodeUnit, MetricResult
from gmod.domain.interfaces import IGitParser, ILanguageParser, IMetric
from gmod.infrastructure.db.database import get_database
from gmod.infrastructure.parsers.factory import ParserFactory
from gmod.infrastructure.metrics.factory import MetricFactory

logger = logging.getLogger(__name__)


class AnalyzeRepositoryUseCase:
    """Use case для анализа репозитория."""
    
    def __init__(
        self,
        diff_only: bool = False,
        git_parser: Optional[IGitParser] = None,
        parser_factory: Optional[ILanguageParser] = None,
        metric_factory: Optional[IMetric] = None,
    ):
        """Инициализация use case.
        
        Args:
            diff_only: Если True, анализирует только diff, иначе файл целиком
            git_parser: Реализация IGitParser (если None, создаётся по умолчанию)
            parser_factory: Фабрика парсеров (если None, используется ParserFactory)
            metric_factory: Фабрика метрик (если None, используется MetricFactory)
        """
        self.diff_only = diff_only
        self._git_parser = git_parser
        self._parser_factory = parser_factory
        self._metric_factory = metric_factory
        self.db = get_database()
    
    @property
    def git_parser(self) -> IGitParser:
        if self._git_parser is None:
            from gmod.infrastructure.git.git_parser import GitParser
            self._git_parser = GitParser(diff_only=self.diff_only)
        return self._git_parser
    
    @property
    def parser_factory(self) -> ILanguageParser:
        if self._parser_factory is None:
            from gmod.infrastructure.parsers.factory import ParserFactory
            self._parser_factory = ParserFactory()
        return self._parser_factory
    
    @property
    def metric_factory(self) -> IMetric:
        if self._metric_factory is None:
            from gmod.infrastructure.metrics.factory import MetricFactory
            self._metric_factory = MetricFactory()
        return self._metric_factory
    
    def execute(self, repository: Repository, commit_hash: Optional[str] = None) -> Dict:
        """Выполнение анализа репозитория.
        
        Args:
            repository: Сущность репозитория
            commit_hash: Хеш коммита для анализа (если None, анализирует последний коммит)
            
        Returns:
            Словарь с результатами анализа
        """
        logger.info(f"[GIT] Starting analysis of repository: {repository.id} (path={repository.local_path})")
        
        # Сохранение информации о репозитории
        logger.debug(f"[GIT] Saving repository info: {repository.id}")
        self.git_parser.save_repository_info(repository)
        
        # Получение коммитов
        logger.debug(f"[GIT] Fetching commits for repo: {repository.id}")
        commits = self.git_parser.get_commits(repository.id, limit=100)
        logger.info(f"[GIT] Retrieved {len(commits)} commits")
        
        # Определение коммита для анализа
        target_commit = commit_hash
        if not target_commit and commits:
            target_commit = commits[0].hash
        
        if not target_commit:
            logger.warning("[GIT] No commits found for analysis")
            return {"status": "error", "message": "No commits found"}
        
        logger.info(f"[GIT] Analyzing commit: {target_commit}")
        
        # Получение изменённых файлов
        logger.debug(f"[GIT] Getting changed files for commit: {target_commit}")
        changed_files = self._get_changed_files(repository, target_commit)
        
        if not changed_files:
            logger.warning("[GIT] No changed files found for commit")
            return {"status": "error", "message": "No changed files found"}
        
        logger.info(f"[GIT] Found {len(changed_files)} changed files: {changed_files}")
        
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
                logger.debug(f"[PARSE] Analyzing file: {file_path}")
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
        
        logger.info(f"[ANALYSIS] Completed: {results['files_analyzed']} files, "
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
            logger.debug(f"[GIT] Raw changed files before filter: {changed_files}")
            changed_files = [f for f in changed_files if self._is_supported_file(f)]
            logger.debug(f"[GIT] Supported changed files after filter: {changed_files}")
            
            return changed_files
            
        except Exception as e:
            logger.error(f"[GIT] Error getting changed files: {e}")
            return []
    
    def _is_supported_file(self, file_path: str) -> bool:
        """Проверка, поддерживается ли файл."""
        # Определяем язык по расширению
        path = Path(file_path)
        language = self.parser_factory.detect_language(path)
        
        # Проверяем, есть ли парсер для этого языка
        parser = self.parser_factory.get_parser(language)
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
            logger.debug(f"[GIT] Getting diff for file: {file_path}")
            file_diff = self.git_parser.get_file_diff(repository.id, commit_hash, file_path)
            
            if not file_diff:
                result["errors"].append(f"Could not get diff for {file_path}")
                return result
            
            # Определение содержимого для анализа
            content = file_diff.new_content if file_diff.new_content else file_diff.old_content
            if not content:
                result["errors"].append(f"No content available for {file_path}")
                return result
            
            logger.debug(f"[PARSE] File content length: {len(content)} chars, diff_only={self.diff_only}")
            
            # Определение языка
            path = Path(file_path)
            language = self.parser_factory.detect_language(path)
            logger.debug(f"[PARSE] Detected language: {language} for file: {file_path}")
            
            # Парсинг файла на единицы кода
            units = self.parser_factory.parse_file(path, content, language)
            
            if not units:
                result["errors"].append(f"No code units found in {file_path}")
                return result
            
            logger.info(f"[PARSE] Parsed {len(units)} code units from {file_path}: {[f'{u.unit_type}:{u.name}' for u in units]}")
            
            # Получение коммитов для VCS метрик
            commits = self.git_parser.get_commits(repository.id, limit=100)
            logger.debug(f"[GIT] Retrieved {len(commits)} commits for VCS metrics")
            
            # Вычисление метрик для каждой единицы кода
            for unit in units:
                try:
                    # Вычисление всех метрик
                    logger.debug(f"[METRICS] Computing metrics for unit: {unit.unit_type}:{unit.name}")
                    metrics = self.metric_factory.compute_all_metrics(unit)
                    logger.debug(f"[METRICS] Computed {len(metrics)} metrics for {unit.name}")
                    
                    # Сохранение метрик в БД
                    for metric in metrics:
                        self._save_metric(repository.id, commit_hash, metric)
                    
                    result["metrics_computed"] += len(metrics)
                    result["units_analyzed"] += 1
                    
                except Exception as e:
                    error_msg = f"Error computing metrics for {unit.name} in {file_path}: {e}"
                    logger.error(f"[METRICS] {error_msg}")
                    result["errors"].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error analyzing file {file_path}: {e}"
            logger.error(f"[ANALYSIS] {error_msg}")
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
                logger.debug(f"[DB] Metric {metric.metric_name} for {metric.unit_name} already cached (value={cached_value})")
                return
            
            # Сохраняем в БД
            logger.debug(f"[DB] Saving metric: {metric.metric_name}={metric.value} for {metric.unit_name} in {metric.file_path}")
            self.db.save_metric(
                repo_id=repo_id,
                commit_hash=commit_hash,
                file_path=metric.file_path,
                unit_type=metric.unit_type,
                unit_name=metric.unit_name,
                metric_name=metric.metric_name,
                value=metric.value
            )
            logger.debug(f"[DB] Metric saved successfully")
            
        except Exception as e:
            logger.error(f"[DB] Error saving metric {metric.metric_name}: {e}")
    
    def analyze_paths(self, repository: Repository, commit_hash: str,
                      paths: List[str]) -> Dict:
        """Анализ выбранных пользователем файлов/директорий (не только diff).

        Args:
            repository: репозиторий
            commit_hash: коммит для привязки метрик в БД
            paths: относительные пути файлов или директорий в репозитории

        Returns:
            dict с results + function_table: [{file, function, metric, value}]
        """
        logger.info("[PATHS] Анализ выбранных путей: %s (коммит %s)", paths, commit_hash)
        repo_root = Path(repository.local_path)
        files: List[str] = []
        for rel in paths:
            p = (repo_root / rel) if not Path(rel).is_absolute() else Path(rel)
            if p.is_dir():
                for f in sorted(p.rglob("*")):
                    if f.is_file():
                        try:
                            rel_parts = f.relative_to(repo_root).parts
                        except ValueError:
                            continue
                        if any(part.startswith(".") for part in rel_parts):
                            continue  # пропускаем .git и скрытые
                        try:
                            files.append(str(f.relative_to(repo_root)))
                        except ValueError:
                            files.append(str(f))
            elif p.is_file():
                try:
                    files.append(str(p.relative_to(repo_root)))
                except ValueError:
                    files.append(str(p))
            else:
                logger.warning("[PATHS] Путь не найден, пропускаем: %s", rel)

        files = [f for f in files if self._is_supported_file(f)]
        logger.info("[PATHS] Файлов к анализу после фильтра: %d", len(files))

        results: Dict = {
            "status": "success" if files else "error",
            "repository_id": repository.id,
            "commit_hash": commit_hash,
            "files_analyzed": 0,
            "units_analyzed": 0,
            "metrics_computed": 0,
            "errors": [],
            "function_table": [],
        }
        if not files:
            results["message"] = "Нет поддерживаемых файлов в выбранных путях"
            return results

        commits = self.git_parser.get_commits(repository.id, limit=100)

        for file_path in files:
            try:
                full = repo_root / file_path
                content = full.read_text(encoding="utf-8", errors="ignore")
                path = Path(file_path)
                language = self.parser_factory.detect_language(path)
                units = self.parser_factory.parse_file(path, content, language)
                results["files_analyzed"] += 1
                for unit in units:
                    unit.file_path = file_path
                    try:
                        metrics = self.metric_factory.compute_all_metrics(unit)
                        for metric in metrics:
                            metric.file_path = file_path
                            self._save_metric(repository.id, commit_hash, metric)
                            results["function_table"].append({
                                "file": file_path,
                                "function": f"{unit.unit_type}:{unit.name}",
                                "metric": metric.metric_name,
                                "value": round(float(metric.value), 4),
                            })
                        results["metrics_computed"] += len(metrics)
                        results["units_analyzed"] += 1
                    except Exception as e:
                        results["errors"].append(f"{file_path}::{unit.name}: {e}")
            except Exception as e:
                logger.error("[PATHS] Ошибка анализа %s: %s", file_path, e)
                results["errors"].append(f"{file_path}: {e}")

        logger.info(
            "[PATHS] Готово: файлов=%d единиц=%d метрик=%d",
            results["files_analyzed"], results["units_analyzed"], results["metrics_computed"],
        )
        return results

    def get_function_metrics_table(self, repo_id: str,
                                   commit_hash: Optional[str] = None) -> List[Dict]:
        """Плоская таблица «функция × метрика × значение» для UI."""
        rows = self.get_analysis_results(repo_id, commit_hash)
        table = []
        for r in rows:
            if r.get("unit_type") in ("function", "class", "method"):
                table.append({
                    "file": r["file_path"],
                    "function": f"{r['unit_type']}:{r['unit_name']}",
                    "metric": r["metric_name"],
                    "value": round(float(r["value"]), 4),
                })
        return table

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

"""Метрики истории VCS (churn)."""

import logging
from typing import List, Dict
from datetime import datetime, timedelta

from gmod.domain.entities import CodeUnit, MetricResult, Commit
from gmod.infrastructure.metrics.base import BaseMetric

logger = logging.getLogger(__name__)


class ChurnMetric(BaseMetric):
    """Churn - частота изменений файла."""
    
    def __init__(self, commits: List[Commit] = None):
        """Инициализация метрики churn.
        
        Args:
            commits: Список коммитов для анализа
        """
        super().__init__()
        self.commits = commits or []
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление churn для единицы кода."""
        if not self.commits:
            return 0.0
        
        # Подсчитываем количество изменений файла
        file_path = unit.file_path
        churn_count = 0
        
        for commit in self.commits:
            # В реальной реализации здесь нужно проверять diff коммита
            # Упрощённая версия: считаем что файл менялся в каждом коммите
            # где есть его путь в сообщении или это файл из того же репозитория
            if commit.repo_id in file_path or any(word in commit.message.lower() for word in file_path.split('/')):
                churn_count += 1
        
        return float(churn_count)


class ChangeFrequency(BaseMetric):
    """Частота изменений (изменений в день)."""
    
    def __init__(self, commits: List[Commit] = None):
        """Инициализация метрики частоты изменений.
        
        Args:
            commits: Список коммитов для анализа
        """
        super().__init__()
        self.commits = commits or []
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление частоты изменений."""
        if not self.commits:
            return 0.0
        
        # Определяем период анализа
        if len(self.commits) < 2:
            return 0.0
        
        first_commit = min(self.commits, key=lambda c: c.date)
        last_commit = max(self.commits, key=lambda c: c.date)
        
        period_days = (last_commit.date - first_commit.date).days
        if period_days == 0:
            period_days = 1
        
        # Подсчитываем изменения файла
        churn_metric = ChurnMetric(self.commits)
        churn_count = churn_metric._compute_impl(unit)
        
        # Частота изменений в день
        frequency = churn_count / period_days
        
        return float(frequency)


class RecentChanges(BaseMetric):
    """Количество недавних изменений (за последние 30 дней)."""
    
    def __init__(self, commits: List[Commit] = None):
        """Инициализация метрики недавних изменений.
        
        Args:
            commits: Список коммитов для анализа
        """
        super().__init__()
        self.commits = commits or []
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества недавних изменений."""
        if not self.commits:
            return 0.0
        
        # Определяем дату 30 дней назад
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Подсчитываем изменения за последние 30 дней
        recent_commits = [c for c in self.commits if c.date >= thirty_days_ago]
        
        churn_metric = ChurnMetric(recent_commits)
        recent_churn = churn_metric._compute_impl(unit)
        
        return float(recent_churn)


class AuthorsCount(BaseMetric):
    """Количество авторов, изменявших файл."""
    
    def __init__(self, commits: List[Commit] = None):
        """Инициализация метрики количества авторов.
        
        Args:
            commits: Список коммитов для анализа
        """
        super().__init__()
        self.commits = commits or []
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление количества авторов."""
        if not self.commits:
            return 0.0
        
        # Собираем уникальных авторов для файла
        file_path = unit.file_path
        authors = set()
        
        for commit in self.commits:
            # Упрощённая логика определения авторства файла
            if commit.repo_id in file_path or any(word in commit.message.lower() for word in file_path.split('/')):
                authors.add(commit.author)
        
        return float(len(authors))


class CommitMessageQuality(BaseMetric):
    """Качество сообщений коммитов."""
    
    def __init__(self, commits: List[Commit] = None):
        """Инициализация метрики качества сообщений коммитов.
        
        Args:
            commits: Список коммитов для анализа
        """
        super().__init__()
        self.commits = commits or []
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление качества сообщений коммитов."""
        if not self.commits:
            return 0.0
        
        # Анализируем сообщения коммитов, связанные с файлом
        file_path = unit.file_path
        relevant_commits = [
            c for c in self.commits 
            if file_path in c.message or any(word in c.message.lower() for word in file_path.split('/'))
        ]
        
        if not relevant_commits:
            return 0.0
        
        # Оцениваем качество по нескольким критериям
        total_score = 0
        
        for commit in relevant_commits:
            message = commit.message.strip()
            score = 0
            
            # Длина сообщения (оптимально 10-50 символов)
            if 10 <= len(message) <= 50:
                score += 1
            
            # Начинается с глагола
            first_word = message.split()[0] if message.split() else ""
            if first_word.lower() in ['add', 'fix', 'update', 'remove', 'change', 'implement', 'refactor']:
                score += 1
            
            # Содержит описание (не одно слово)
            if len(message.split()) > 2:
                score += 1
            
            # Не содержит "fix fix" или подобные повторы
            if 'fix fix' not in message.lower() and 'update update' not in message.lower():
                score += 1
            
            total_score += score
        
        # Среднее качество
        if relevant_commits:
            average_quality = total_score / len(relevant_commits)
            return float(average_quality)
        
        return 0.0


class BugFixFrequency(BaseMetric):
    """Частота исправления багов."""
    
    def __init__(self, commits: List[Commit] = None):
        """Инициализация метрики частоты исправления багов.
        
        Args:
            commits: Список коммитов для анализа
        """
        super().__init__()
        self.commits = commits or []
    
    def _compute_impl(self, unit: CodeUnit) -> float:
        """Вычисление частоты исправления багов."""
        if not self.commits:
            return 0.0
        
        # Ищем коммиты с указанием на исправление багов
        bug_keywords = ['fix', 'bug', 'error', 'issue', 'patch', 'hotfix']
        
        file_path = unit.file_path
        bug_fix_commits = 0
        
        for commit in self.commits:
            message_lower = commit.message.lower()
            # Проверяем наличие ключевых слов и связь с файлом
            if (any(keyword in message_lower for keyword in bug_keywords) and 
                (file_path in commit.message or any(word in message_lower for word in file_path.split('/')))):
                bug_fix_commits += 1
        
        return float(bug_fix_commits)

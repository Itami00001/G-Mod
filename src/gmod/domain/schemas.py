"""Pydantic схемы для ответов AI."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


class AIResponse(BaseModel):
    """Базовая схема ответа AI."""
    
    risk_score: int = Field(..., ge=1, le=10, description="Оценка риска от 1 до 10")
    reason: str = Field(..., description="Обоснование оценки")
    recommendation: str = Field(..., description="Рекомендация по исправлению")
    affected_units: List[str] = Field(default_factory=list, description="Затронутые единицы кода")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Уверенность в ответе")
    additional_info: Dict[str, Any] = Field(default_factory=dict, description="Дополнительная информация")
    
    @field_validator('risk_score', mode='before')
    @classmethod
    def coerce_risk_score(cls, v):
        """Приведение risk_score: '6/10' -> 6, 6.0 -> 6, кламп 1..10.

        Маленькие модели (llama3.1:8b и др.) часто отвечают строкой
        или дробью — приводим, а не падаем.
        """
        if isinstance(v, str):
            import re
            m = re.search(r'\d+', v)
            v = int(m.group()) if m else 5
        if isinstance(v, float):
            v = int(round(v))
        try:
            v = int(v)
        except (TypeError, ValueError):
            v = 5
        return max(1, min(10, v))

    @field_validator('risk_score')
    @classmethod
    def validate_risk_score(cls, v):
        """Валидация оценки риска."""
        if not 1 <= v <= 10:
            raise ValueError('risk_score must be between 1 and 10')
        return v

    @field_validator('reason', 'recommendation', mode='before')
    @classmethod
    def coerce_text_fields(cls, v):
        """Строковые поля: список -> склейка, прочее -> str().

        llama3.1:8b отдаёт recommendation списком — склеиваем,
        чтобы анализ не падал с 'Input should be a valid string'.
        """
        if isinstance(v, list):
            return "\n".join(str(x) for x in v)
        if v is None:
            return ""
        return v if isinstance(v, str) else str(v)

    @field_validator('affected_units', mode='before')
    @classmethod
    def coerce_affected_units(cls, v):
        """affected_units: строка -> [строка]."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('confidence', mode='before')
    @classmethod
    def coerce_confidence(cls, v):
        """Приведение confidence: '85%' -> 0.85, кламп 0..1."""
        if isinstance(v, str):
            v = v.strip().replace('%', '')
            try:
                num = float(v)
            except ValueError:
                num = 0.8
            v = num / 100.0 if num > 1.0 else num
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.8
        return max(0.0, min(1.0, v))
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v):
        """Валидация уверенности."""
        if not 0.0 <= v <= 1.0:
            raise ValueError('confidence must be between 0.0 and 1.0')
        return v


class ArchaeologistResponse(AIResponse):
    """Специфический ответ для агента-археолога."""
    
    performance_impact: str = Field(..., description="Влияние на производительность")
    complexity_change: str = Field(default="неизвестно", description="Изменение сложности")
    suggested_actions: List[str] = Field(default_factory=list, description="Предлагаемые действия")

    @field_validator('suggested_actions', mode='before')
    @classmethod
    def coerce_suggested_actions(cls, v):
        """suggested_actions: строка -> [строка]."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return v

    @field_validator('complexity_change', mode='before')
    @classmethod
    def coerce_complexity_change(cls, v):
        """Нормализация изменения сложности к русским каноническим."""
        normalized = str(v).strip().lower() if v is not None else "неизвестно"
        aliases = {
            "increased": "увеличилась",
            "decreased": "уменьшилась",
            "unchanged": "не изменилась",
            "unknown": "неизвестно",
            "увеличилась": "увеличилась",
            "уменьшилась": "уменьшилась",
            "не изменилась": "не изменилась",
            "неизвестно": "неизвестно",
        }
        return aliases.get(normalized, str(v) if v is not None else "неизвестно")
    
    @field_validator('performance_impact')
    @classmethod
    def validate_performance_impact(cls, v):
        """Валидация влияния на производительность.

        Промпт ARCHAEOLOGIST_ANALYSIS_PROMPT просит LLM отвечать
        high/medium/low, поэтому принимаем и английские значения
        и нормализуем их к русским каноническим.
        """
        normalized = str(v).strip().lower()
        aliases = {
            "high": "высокое",
            "medium": "среднее",
            "low": "низкое",
            "unknown": "неизвестно",
            "высокое": "высокое",
            "среднее": "среднее",
            "низкое": "низкое",
            "неизвестно": "неизвестно",
        }
        if normalized not in aliases:
            raise ValueError(
                f'performance_impact must be one of {sorted(set(aliases))}'
            )
        return aliases[normalized]


class SummaryResponse(BaseModel):
    """Схема для суммаризации диалога."""
    
    summary: str = Field(..., description="Суммаризация диалога")
    key_points: List[str] = Field(default_factory=list, description="Ключевые моменты")
    action_items: List[str] = Field(default_factory=list, description="Элементы действий")
    context: str = Field(default="", description="Контекст работы")


class ErrorResponse(BaseModel):
    """Схема для ответа об ошибке."""
    
    error: str = Field(..., description="Сообщение об ошибке")
    error_type: str = Field(..., description="Тип ошибки")
    fallback_attempted: bool = Field(default=False, description="Был ли попытан fallback")
    provider_used: Optional[str] = Field(None, description="Использованный провайдер")

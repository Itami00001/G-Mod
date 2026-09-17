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
    
    @field_validator('risk_score')
    @classmethod
    def validate_risk_score(cls, v):
        """Валидация оценки риска."""
        if not 1 <= v <= 10:
            raise ValueError('risk_score must be between 1 and 10')
        return v
    
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
    
    @field_validator('performance_impact')
    @classmethod
    def validate_performance_impact(cls, v):
        """Валидация влияния на производительность."""
        valid_impacts = ["высокое", "среднее", "низкое", "неизвестно"]
        if v.lower() not in valid_impacts:
            raise ValueError(f'performance_impact must be one of {valid_impacts}')
        return v.lower()


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

"""Тесты LLM функциональности (упрощённые)."""

import pytest


def test_import_schemas():
    """Тест импорта схем."""
    from gmod.domain.schemas import AIResponse, ArchaeologistResponse, ErrorResponse
    assert AIResponse is not None
    assert ArchaeologistResponse is not None
    assert ErrorResponse is not None


def test_import_prompts():
    """Тест импорта промптов."""
    from gmod.domain.prompts import (
        ARCHAEOLOGIST_SYSTEM_PROMPT,
        ARCHAEOLOGIST_ANALYSIS_PROMPT,
        SUMMARIZATION_PROMPT
    )
    assert ARCHAEOLOGIST_SYSTEM_PROMPT is not None
    assert ARCHAEOLOGIST_ANALYSIS_PROMPT is not None
    assert SUMMARIZATION_PROMPT is not None


def test_ai_response_creation():
    """Тест создания AI ответа."""
    from gmod.domain.schemas import AIResponse
    
    response = AIResponse(
        risk_score=5,
        reason="Test reason",
        recommendation="Test recommendation"
    )
    
    assert response.risk_score == 5
    assert response.reason == "Test reason"


def test_archaeologist_response_creation():
    """Тест создания ответа археолога."""
    from gmod.domain.schemas import ArchaeologistResponse
    
    response = ArchaeologistResponse(
        risk_score=7,
        reason="Test reason",
        recommendation="Test recommendation",
        performance_impact="высокое"
    )
    
    assert response.risk_score == 7
    assert response.performance_impact == "высокое"


def test_error_response_creation():
    """Тест создания ответа об ошибке."""
    from gmod.domain.schemas import ErrorResponse
    
    response = ErrorResponse(
        error="Test error",
        error_type="test_type"
    )
    
    assert response.error == "Test error"
    assert response.error_type == "test_type"

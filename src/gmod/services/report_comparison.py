"""ReportComparisonService — сравнение двух AI-отчётов (ТЗ v0.4 §3).

Правила выбора: ровно 2 отчёта (клик открывает, Ctrl+Click добавляет,
Shift+Click — диапазон, ☐ — без Ctrl). Экран: таблица поле|A|B +
diff-представление изменений AI-анализа.
"""

import difflib
import json
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

COMPARE_FIELDS = [
    ("risk_score", "Риск"),
    ("reason", "Обоснование"),
    ("recommendation", "Рекомендация"),
    ("performance_impact", "Влияние"),
    ("complexity_change", "Сложность"),
    ("confidence", "Уверенность"),
    ("affected_units", "Затронутые юниты"),
    ("suggested_actions", "Действия"),
]


def validate_selection(selected: list) -> Tuple[bool, str]:
    """Правило «ровно 2» (ТЗ §3.2)."""
    if len(selected) < 2:
        return False, "Для сравнения выберите 2 отчёта."
    if len(selected) > 2:
        return False, "Для сравнения можно выбрать только 2 отчёта."
    return True, ""


def parse_response(report: Dict[str, Any]) -> Dict[str, Any]:
    """Разбор response_json отчёта в словарь (толерантно)."""
    raw = report.get("response_json", "") or ""
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"text": raw}
    except Exception:
        # Возможно, JSON обёрнут в текст — ищем границы.
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(raw[start:end])
                return data if isinstance(data, dict) else {"text": raw}
        except Exception:
            pass
    return {"text": raw}


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, list):
        return "\n".join(f"• {x}" for x in value) or "—"
    return str(value)


def compare(report_a: Dict[str, Any],
            report_b: Dict[str, Any]) -> Dict[str, Any]:
    """Сравнение двух отчётов: таблица полей + AI-diff.

    Returns:
        {"rows": [{field, a, b, changed}], "ai_diff": str,
         "meta_a": {...}, "meta_b": {...}}
    """
    pa, pb = parse_response(report_a), parse_response(report_b)
    rows = []
    for key, label in COMPARE_FIELDS:
        va, vb = _fmt(pa.get(key)), _fmt(pb.get(key))
        rows.append({"field": label, "a": va, "b": vb,
                     "changed": va.strip() != vb.strip()})

    def _meta(r: Dict[str, Any]) -> Dict[str, Any]:
        return {"id": r.get("id"), "agent": r.get("agent_type"),
                "commit": str(r.get("commit_hash", ""))[:8],
                "risk": r.get("risk_score"), "time": r.get("timestamp")}

    pretty_a = json.dumps(pa, ensure_ascii=False, indent=2).splitlines()
    pretty_b = json.dumps(pb, ensure_ascii=False, indent=2).splitlines()
    diff = difflib.unified_diff(pretty_a, pretty_b, fromfile="Отчёт A",
                                tofile="Отчёт B", lineterm="")
    return {"rows": rows, "ai_diff": "\n".join(diff) or "Различий нет.",
            "meta_a": _meta(report_a), "meta_b": _meta(report_b)}

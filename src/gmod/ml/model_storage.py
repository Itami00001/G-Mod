"""ModelStorage: сохранение/версии/история моделей (ТЗ §25-26).

Хранилище: %APPDATA%\\GMod\\ml_models\\<model_id>.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def models_dir() -> Path:
    """Каталог моделей."""
    from gmod.config.constants import DATA_DIR
    path = DATA_DIR / "ml_models"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ModelStorage:
    """Версионированное хранилище моделей."""

    def __init__(self, directory: Optional[Path] = None):
        self.directory = Path(directory) if directory else models_dir()

    def _next_version(self, base: str) -> str:
        """Model vN: следующий номер для базового имени."""
        existing = [p.stem for p in self.directory.glob("*.json")]
        nums = []
        for stem in existing:
            if stem == base or stem.startswith(base + "_v"):
                tail = stem[len(base):].lstrip("_v")
                try:
                    nums.append(int(tail) if tail else 1)
                except ValueError:
                    pass
        return f"{base}_v{max(nums, default=0) + 1}"

    def save(self, model_id_base: str, payload: Dict[str, Any]) -> str:
        """Сохранить модель с автоверсией. Возвращает model_id."""
        model_id = self._next_version(model_id_base or "model")
        payload = dict(payload)
        payload["model_id"] = model_id
        payload.setdefault("created_at", datetime.now().isoformat())
        path = self.directory / f"{model_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("ml model saved: %s", model_id)
        return model_id

    def load(self, model_id: str) -> Dict[str, Any]:
        """Загрузить модель по id."""
        path = self.directory / f"{model_id}.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_models(self, limit: int = 50) -> List[Dict[str, Any]]:
        """История экспериментов (ТЗ §26): свежие сверху."""
        items = []
        for path in sorted(self.directory.glob("*.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items.append({
                    "model_id": data.get("model_id", path.stem),
                    "accuracy": ((data.get("validation_metrics") or {}).get("accuracy")
                                 or (data.get("training_metrics") or {}).get("val_accuracy", 0)),
                    "epochs": data.get("epochs", 0),
                    "activation": ((data.get("architecture") or {}).get("activation", "")),
                    "created_at": data.get("created_at", ""),
                })
            except Exception as e:
                logger.warning("ml list: %s: %s", path.name, e)
        return items

    def delete(self, model_id: str) -> bool:
        """Удаление модели."""
        path = self.directory / f"{model_id}.json"
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return False

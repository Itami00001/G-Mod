"""BackupService — резервные копии workspace (ТЗ §17-22, §30).

Структура NAME_GIT.zip:
    manifest.json / README.txt
    workspace/ (workspace.json, tabs.json, views.json, ui_state.json)
    chat/ (sessions.json, messages.json)
    repository/ (metadata.json)
    analysis/ (metrics.csv, reports.json)
    database/ (gmod.db)
    config/ (config.sanitized.yaml — БЕЗ секретов)

Reset pipeline: Confirm -> Flush -> Backup -> Verify -> Reset ->
Recreate defaults -> Reload. Без валидного backup reset НЕ выполняется.
Reset сбрасывает только workspace/UI state, НЕ трогает repository,
metrics, reports (ТЗ §21).
"""

import csv
import io
import json
import logging
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def backups_dir() -> Path:
    """Каталог резервных копий: %APPDATA%\\GMod\\backups."""
    from gmod.config.constants import DATA_DIR
    path = DATA_DIR / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitized_config() -> Dict[str, Any]:
    """config.yaml БЕЗ секретов (ТЗ §20: не содержать API-ключи)."""
    from gmod.config.settings import get_settings
    settings = get_settings()
    data: Dict[str, Any] = {}
    try:
        from gmod.config.constants import CONFIG_FILE
        import yaml
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
    except Exception:
        data = {}
    # Вычищаем все возможные места секретов.
    for p in data.get("llm", {}).get("providers", []):
        if isinstance(p, dict) and "api_key" in p:
            p["api_key"] = ""
    data.setdefault("llm", {})["providers"] = data.get("llm", {}).get("providers", [])
    data["_sanitized"] = True
    data["_sanitized_at"] = datetime.now().isoformat()
    # Пояс: модели/флаги остаются (нужны для восстановления).
    _ = settings
    return data


class BackupService:
    """Сервис резервного копирования и сброса."""

    def __init__(self, db=None):
        if db is None:
            from gmod.infrastructure.db.database import get_database
            db = get_database()
        self.db = db

    # ---------------- backup ----------------

    def list_backups(self) -> List[Dict[str, Any]]:
        """Список ZIP-копий (новые сверху)."""
        out = []
        directory = backups_dir()
        for path in sorted(directory.glob("*.zip"), key=lambda p: p.stat().st_mtime,
                           reverse=True):
            info: Dict[str, Any] = {"name": path.name, "path": str(path),
                                    "size": path.stat().st_size,
                                    "mtime": datetime.fromtimestamp(
                                        path.stat().st_mtime).isoformat()}
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                    info["manifest"] = manifest
            except Exception as e:
                info["manifest_error"] = str(e)
            out.append(info)
        return out

    def create_backup(self, workspace_id: str = "default",
                      repo_id: str = "") -> Dict[str, Any]:
        """Создание и проверка ZIP-копии.

        Returns:
            {"status": "success", "path": ..., "manifest": {...}}
            {"status": "error", "message": ...}
        """
        from gmod.services.workspace_service import WorkspaceService
        from gmod.config.constants import DATABASE_FILE

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ws_name = (self.db.get_workspace(workspace_id) or {}).get("name", "workspace")
        safe_repo = "".join(c if (c.isalnum() or c in "-_") else "_" for c in (repo_id or "norepo"))
        safe_ws = "".join(c if (c.isalnum() or c in "-_") else "_" for c in ws_name)
        filename = f"{safe_ws}_{safe_repo}_{stamp}.zip"

        # ТЗ §18: имя последней копии NAME_GIT.zip — держим symlink-копию.
        # Ротация: храним все, плюс перезаписываем latest.
        directory = backups_dir()
        path = directory / filename
        logger.info("backup: создание %s", path)
        try:
            ws_snapshot = WorkspaceService(db=self.db,
                                           workspace_id=workspace_id).snapshot()
            manifest = {
                "app": "GMod",
                "created_at": datetime.now().isoformat(),
                "schema_version": 3,
                "workspace": ws_snapshot.get("workspace", {}).get("name", ws_name),
                "repository": repo_id,
                "contains": ["workspace", "chat", "repository", "analysis",
                             "database", "config_sanitized"],
                "secrets": "excluded",
            }
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("manifest.json",
                            json.dumps(manifest, ensure_ascii=False, indent=2))
                zf.writestr("README.txt", self._readme_text(manifest))
                zf.writestr("workspace/workspace.json",
                            json.dumps(ws_snapshot.get("workspace", {}),
                                       ensure_ascii=False, indent=2))
                zf.writestr("workspace/tabs.json",
                            json.dumps(ws_snapshot.get("tabs", []),
                                       ensure_ascii=False, indent=2))
                zf.writestr("workspace/views.json",
                            json.dumps(ws_snapshot.get("views", []),
                                       ensure_ascii=False, indent=2))
                zf.writestr("workspace/ui_state.json",
                            json.dumps({"exported_at": manifest["created_at"]},
                                       ensure_ascii=False, indent=2))
                zf.writestr("chat/sessions.json",
                            json.dumps(self._json_safe(
                                self.db.get_chat_sessions(workspace_id)),
                                ensure_ascii=False, indent=2))
                all_messages = []
                for s in self.db.get_chat_sessions(workspace_id):
                    all_messages.extend(self.db.get_chat_messages(s["id"]))
                zf.writestr("chat/messages.json",
                            json.dumps(self._json_safe(all_messages),
                                       ensure_ascii=False, indent=2))
                zf.writestr("repository/metadata.json",
                            json.dumps(self._repository_metadata(repo_id),
                                       ensure_ascii=False, indent=2))
                zf.writestr("analysis/metrics.csv", self._metrics_csv(repo_id))
                zf.writestr("analysis/reports.json",
                            json.dumps(self._json_safe(
                                self.db.get_ai_reports(repo_id) if repo_id else []),
                                ensure_ascii=False, indent=2))
                # Копия БД (checkpoint для консистентности).
                with self.db.get_connection() as conn:
                    try:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    except Exception:
                        pass
                if DATABASE_FILE.exists():
                    zf.write(DATABASE_FILE, "database/gmod.db")
                import yaml
                zf.writestr("config/config.sanitized.yaml",
                            yaml.safe_dump(sanitized_config(), allow_unicode=True))

            # Verify: валидный ZIP + manifest читается (ТЗ §20).
            verify = self.verify_backup(path)
            if verify.get("status") != "success":
                try:
                    path.unlink()
                except Exception:
                    pass
                return {"status": "error",
                        "message": f"Backup verification failed: {verify.get('message')}"}

            # latest-копия NAME_GIT.zip (ТЗ §18) + ротация (держим 10).
            latest = directory / f"{safe_ws}_{safe_repo}_latest.zip"
            try:
                shutil.copyfile(path, latest)
            except Exception as e:
                logger.warning("backup: latest copy failed: %s", e)
            self._rotate(directory, keep=10)
            logger.info("backup: готово %s", path)
            return {"status": "success", "path": str(path), "manifest": manifest}
        except Exception as e:
            logger.error("backup: ошибка создания: %s", e, exc_info=True)
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass
            return {"status": "error", "message": str(e)}

    def verify_backup(self, path) -> Dict[str, Any]:
        """Проверка архива: валидный ZIP + manifest + структура."""
        try:
            path = Path(path)
            if not zipfile.is_zipfile(path):
                return {"status": "error", "message": "not a zip file"}
            with zipfile.ZipFile(path, "r") as zf:
                bad = zf.testzip()
                if bad:
                    return {"status": "error", "message": f"corrupt entry: {bad}"}
                names = set(zf.namelist())
                required = {"manifest.json", "README.txt", "workspace/workspace.json",
                            "chat/sessions.json", "config/config.sanitized.yaml"}
                missing = required - names
                if missing:
                    return {"status": "error", "message": f"missing: {sorted(missing)}"}
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                # Секреты искать не должно.
                blob = "".join(zf.read(n).decode("utf-8", errors="ignore")
                               for n in names if n.endswith((".yaml", ".json")))
                for marker in ("gsk_", "sk-ant-", "sk-proj-"):
                    if marker in blob:
                        return {"status": "error",
                                "message": f"secret leak detected: {marker}..."}
            return {"status": "success", "manifest": manifest}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ---------------- reset (ТЗ §17, §21, §22) ----------------

    def reset_workspace(self, workspace_id: str = "default",
                        repo_id: str = "") -> Dict[str, Any]:
        """Pipeline сброса: backup -> verify -> reset UI-state.

        НЕ трогает repository/metrics/reports (ТЗ §21).
        Без валидного backup reset НЕ выполняется (ТЗ §22).
        """
        logger.info("reset: старт (workspace=%s)", workspace_id)
        backup = self.create_backup(workspace_id, repo_id)
        if backup.get("status") != "success":
            msg = ("Не удалось создать резервную копию. "
                   "Рабочая область не была сброшена.")
            logger.error("reset: %s (%s)", msg, backup.get("message"))
            return {"status": "error", "message": msg,
                    "detail": backup.get("message", "")}
        # Сброс только workspace/UI state.
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM workspace_tabs WHERE workspace_id = ?",
                           (workspace_id,))
            cursor.execute("DELETE FROM workspace_views WHERE workspace_id = ?",
                           (workspace_id,))
        from gmod.services.workspace_service import WorkspaceService
        svc = WorkspaceService(db=self.db, workspace_id=workspace_id)
        ws = svc.get_or_create()
        ws["active_tab"] = "Чат"
        ws["theme"] = "dark"
        self.db.save_workspace(ws)
        # Legacy плоские ключи геометрии/доков — в дефолт.
        for key, value in (("window_width", "1200"), ("window_height", "800"),
                           ("left_dock_width", "250"), ("right_dock_width", "300"),
                           ("left_dock_visible", "1"), ("right_dock_visible", "1"),
                           ("active_tab", "Чат"), ("theme", "dark")):
            try:
                self.db.save_workspace_state(key, value)
            except Exception:
                pass
        logger.info("reset: готово, backup=%s", backup.get("path"))
        return {"status": "success", "backup": backup.get("path"),
                "manifest": backup.get("manifest")}

    # ---------------- helpers ----------------

    @staticmethod
    def _readme_text(manifest: Dict[str, Any]) -> str:
        return (
            "GMod workspace backup\n"
            f"Created: {manifest.get('created_at', '?')}\n"
            f"Workspace: {manifest.get('workspace', '?')}\n"
            f"Repository: {manifest.get('repository', '?')}\n"
            f"Schema: {manifest.get('schema_version', '?')}\n"
            "Secrets: excluded ( API keys are NOT stored here ).\n"
        )

    def _repository_metadata(self, repo_id: str) -> Dict[str, Any]:
        if not repo_id:
            return {}
        meta: Dict[str, Any] = {"id": repo_id}
        try:
            for suffix in ("path", "url", "branch"):
                meta[suffix] = self.db.load_workspace_state(f"repo_{repo_id}_{suffix}")
        except Exception:
            pass
        return meta

    def _metrics_csv(self, repo_id: str) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["file", "unit_type", "unit_name", "metric", "value", "timestamp"])
        if repo_id:
            try:
                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT file_path, unit_type, unit_name, metric_name, value, timestamp
                        FROM raw_metrics WHERE repo_id = ? ORDER BY file_path, unit_name
                    """, (repo_id,))
                    writer.writerows(cur.fetchall())
            except Exception as e:
                logger.warning("backup metrics csv: %s", e)
        return buf.getvalue()

    @staticmethod
    def _json_safe(rows) -> list:
        out = []
        for row in rows or []:
            clean = {}
            for k, v in dict(row).items():
                clean[k] = (str(v) if not isinstance(v, (str, int, float, bool, type(None)))
                            else v)
            out.append(clean)
        return out

    @staticmethod
    def _rotate(directory: Path, keep: int = 10) -> None:
        """Ротация: держим keep свежих ZIP (плюс *_latest.zip вне подсчёта)."""
        zips = sorted([p for p in directory.glob("*.zip") if not p.name.endswith("_latest.zip")],
                      key=lambda p: p.stat().st_mtime, reverse=True)
        for old in zips[keep:]:
            try:
                old.unlink()
                logger.info("backup: ротация, удалён %s", old.name)
            except Exception as e:
                logger.warning("backup: ротация не удалась: %s", e)

"""ContextAssemblyService — единственная точка формирования AI-контекста (ТЗ §1).

UI не формирует большие prompt самостоятельно: вызывает assemble() и
передаёт готовый текст + данные для инспектора в ChatService/LLMService.

Состав: Workspace + Repository + Git + Metrics (детально, не агрегат) +
релевантный код (Project/Metrics/Git Index + retrieval).
"""

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Грубая оценка токенов: ~4 символа на токен (запас для кириллицы).
CHARS_PER_TOKEN = 4

# Окна контекста по провайдерам (консервативно, токены).
MODEL_WINDOWS = {
    "groq": 8000,
    "gemini": 32000,
    "openai": 8000,
    "anthropic": 32000,
    "ollama": 8000,
    "default": 8000,
}

# Стоп-слова для retrieval (ru+en, короткие).
_STOPWORDS = set(
    "что это как или для при чем чем или the what how with from that this with and for are was were has have had will would there their them then than also into over such Only just about into через если есть нет или это как что all any can had her was one our out day get has him his how man new now old see two way who boy did its let put say she too use".split()
)

_CONFIG_NAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "tsconfig.json", "pom.xml", "build.gradle",
    "Cargo.toml", "go.mod", "composer.json", "Gemfile", "CMakeLists.txt",
    "Dockerfile", "docker-compose.yml", ".env.example",
}

_PACKAGE_NAMES = {
    "requirements.txt", "package.json", "pyproject.toml", "Pipfile",
    "poetry.lock", "package-lock.json", "yarn.lock", "pom.xml",
    "build.gradle", "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
}


@dataclass
class RepositoryContext:
    """Контекст репозитория (ТЗ §1.1)."""

    repository_id: str = ""
    name: str = ""
    local_path: str = ""
    remote_url: str = ""
    branch: str = ""
    languages: Dict[str, int] = field(default_factory=dict)
    file_count: int = 0
    directory_tree: str = ""
    readme: str = ""
    config_files: Dict[str, str] = field(default_factory=dict)
    package_files: Dict[str, str] = field(default_factory=dict)


@dataclass
class GitContext:
    """Git-контекст (ТЗ §1.1)."""

    commit_hash: str = ""
    author: str = ""
    date: str = ""
    message: str = ""
    branch: str = ""
    changed_files: List[str] = field(default_factory=list)
    diff_summary: str = ""
    recent_commits: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class MetricsContext:
    """Детальный контекст метрик из raw_metrics (ТЗ §1.1, §2)."""

    total: int = 0
    files: int = 0
    by_file: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    by_metric: Dict[str, Dict[str, float]] = field(default_factory=dict)
    top_values: List[Dict[str, Any]] = field(default_factory=list)
    lowest_values: List[Dict[str, Any]] = field(default_factory=list)
    averages: Dict[str, float] = field(default_factory=dict)
    outliers: List[Dict[str, Any]] = field(default_factory=list)
    snapshot_id: str = ""


@dataclass
class AssembledContext:
    """Результат сборки: текст + метаданные для инспектора (ТЗ §1.4)."""

    text: str = ""
    repository_id: str = ""
    commit_hash: str = ""
    metrics_snapshot_id: str = ""
    sections: Dict[str, Any] = field(default_factory=dict)
    estimated_tokens: int = 0
    truncated: bool = False


class ContextAssemblyService:
    """Сборка AI-контекста (ТЗ §1)."""

    def __init__(self, db=None):
        if db is None:
            from gmod.infrastructure.db.database import get_database
            db = get_database()
        self.db = db

    # ---------------- Repository (ТЗ §1.1) ----------------

    def build_repository_context(self, repo_id: str, repo_path: str,
                                 max_tree_entries: int = 120,
                                 max_readme_chars: int = 3000,
                                 max_file_chars: int = 1500) -> RepositoryContext:
        """Контекст репозитория с диска."""
        ctx = RepositoryContext(repository_id=repo_id)
        try:
            root = Path(repo_path or "")
            if not root.is_dir():
                logger.warning("context: нет директории %s", repo_path)
                return ctx
            ctx.name = root.name
            ctx.local_path = str(root)
            try:
                from gmod.services.repository_service import RepositoryService
                meta = RepositoryService(db=self.db).metadata(repo_id)
                ctx.remote_url = meta.get("url") or ""
                ctx.branch = meta.get("branch") or ""
            except Exception:
                pass
            if not ctx.branch:
                try:
                    import git
                    ctx.branch = git.Repo(str(root)).active_branch.name
                except Exception:
                    pass
            from collections import Counter
            counter: Counter = Counter()
            tree_lines: List[str] = []
            for p in sorted(root.rglob("*")):
                try:
                    rel = p.relative_to(root)
                except ValueError:
                    continue
                if any(part.startswith(".") for part in rel.parts):
                    continue
                if p.is_dir():
                    if len(tree_lines) < max_tree_entries:
                        tree_lines.append(str(rel) + "/")
                    continue
                if not p.is_file():
                    continue
                suffix = p.suffix.lower() or "(noext)"
                counter[suffix] += 1
                if len(tree_lines) < max_tree_entries:
                    tree_lines.append(str(rel))
                lname = p.name
                if lname in _CONFIG_NAMES and lname not in ctx.config_files:
                    try:
                        ctx.config_files[lname] = p.read_text(
                            encoding="utf-8", errors="ignore")[:max_file_chars]
                    except Exception:
                        pass
                if lname in _PACKAGE_NAMES and lname not in ctx.package_files:
                    try:
                        ctx.package_files[lname] = p.read_text(
                            encoding="utf-8", errors="ignore")[:max_file_chars]
                    except Exception:
                        pass
            ctx.languages = dict(counter)
            ctx.file_count = sum(counter.values())
            ctx.directory_tree = "\n".join(tree_lines)
            for cand in ("README.md", "README.MD", "readme.md", "README.txt", "README"):
                rp = root / cand
                if rp.is_file():
                    try:
                        ctx.readme = rp.read_text(
                            encoding="utf-8", errors="ignore")[:max_readme_chars]
                    except Exception:
                        pass
                    break
        except Exception as e:
            logger.error("context repo: %s", e)
        return ctx

    # ---------------- Git (ТЗ §1.1) ----------------

    def build_git_context(self, repo_id: str, repo_path: str,
                          recent_limit: int = 10) -> GitContext:
        """Git-контекст: текущий коммит, diff summary, история."""
        ctx = GitContext()
        try:
            from gmod.infrastructure.git.git_parser import GitParser
            parser = GitParser()
            commits = parser.get_commits(repo_id, limit=recent_limit,
                                         repo_path=repo_path or "")
            if not commits:
                return ctx
            head = commits[0]
            ctx.commit_hash = head.hash
            ctx.author = head.author
            ctx.date = head.date.isoformat() if hasattr(head.date, "isoformat") else str(head.date)
            ctx.message = head.message
            try:
                import git
                ctx.branch = git.Repo(repo_path).active_branch.name
            except Exception:
                ctx.branch = ""
            try:
                from gmod.usecases.analyze_repository import AnalyzeRepositoryUseCase
                from gmod.domain.entities import Repository
                from pathlib import Path as _P
                repo = Repository(id=repo_id, url="", local_path=repo_path or "",
                                  name=_P(repo_path).name if repo_path else repo_id)
                use = AnalyzeRepositoryUseCase()
                changed = use._get_changed_files(repo, head.hash)
                try:
                    changed = [f for f in changed
                               if use._is_supported_file(f)]
                except Exception:
                    pass
                ctx.changed_files = changed
            except Exception as e:
                logger.debug("context git changed: %s", e)
            # Diff summary: +/- строк по первым файлам.
            diff_lines: List[str] = []
            try:
                import git
                grepo = git.Repo(repo_path)
                commit = grepo.commit(head.hash)
                if commit.parents:
                    diffs = commit.parents[0].diff(commit, create_patch=True)
                else:
                    diffs = commit.diff(git.NULL_TREE, create_patch=True)
                added = deleted = files_n = 0
                for d in diffs:
                    files_n += 1
                    try:
                        patch = d.diff.decode("utf-8", errors="ignore") if isinstance(
                            d.diff, (bytes, bytearray)) else str(d.diff or "")
                    except Exception:
                        patch = ""
                    for line in patch.splitlines():
                        if line.startswith("+") and not line.startswith("+++"):
                            added += 1
                        elif line.startswith("-") and not line.startswith("---"):
                            deleted += 1
                diff_lines.append(f"files={files_n} +{added}/-{deleted}")
            except Exception as e:
                logger.debug("context git diff: %s", e)
            ctx.diff_summary = "; ".join(diff_lines)
            for c in commits[1:]:
                ctx.recent_commits.append({
                    "hash": c.hash[:8], "author": c.author,
                    "message": c.message[:120],
                    "date": c.date.isoformat() if hasattr(c.date, "isoformat") else str(c.date),
                })
        except Exception as e:
            logger.error("context git: %s", e)
        return ctx

    # ---------------- Metrics (ТЗ §1.1, §2) ----------------

    def build_metrics_context(self, repo_id: str, commit_hash: str = "",
                              max_files: int = 30, top_n: int = 10) -> MetricsContext:
        """Детальные метрики из raw_metrics (не агрегат-строка)."""
        ctx = MetricsContext()
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                if commit_hash:
                    cur.execute("""
                        SELECT file_path, unit_type, unit_name, metric_name, value
                        FROM raw_metrics WHERE repo_id = ? AND commit_hash = ?
                    """, (repo_id, commit_hash))
                else:
                    cur.execute("""
                        SELECT file_path, unit_type, unit_name, metric_name, value
                        FROM raw_metrics WHERE repo_id = ?
                    """, (repo_id,))
                rows = cur.fetchall()
            if not rows:
                return ctx
            from collections import defaultdict
            by_file: Dict[str, Dict[str, float]] = defaultdict(dict)
            by_type: Dict[str, int] = defaultdict(int)
            by_metric: Dict[str, List[float]] = defaultdict(list)
            flat: List[Tuple[str, str, str, float]] = []
            for file_path, unit_type, unit_name, metric_name, value in rows:
                try:
                    v = float(value)
                except (TypeError, ValueError):
                    continue
                by_file[file_path][f"{unit_type}:{unit_name}:{metric_name}"] = v
                by_type[str(unit_type)] += 1
                by_metric[str(metric_name)].append(v)
                flat.append((file_path, f"{unit_type}:{unit_name}", metric_name, v))
            ctx.total = len(flat)
            ctx.files = len(by_file)
            # Ограничение числа файлов (релевантные доберём в retrieval).
            kept_files = sorted(by_file)[:max_files]
            ctx.by_file = {f: by_file[f] for f in kept_files}
            ctx.by_type = dict(by_type)
            for name, values in by_metric.items():
                n = len(values)
                avg = sum(values) / n
                ctx.by_metric[name] = {"avg": round(avg, 4), "min": round(min(values), 4),
                                       "max": round(max(values), 4), "count": n}
                ctx.averages[name] = round(avg, 4)
                if n >= 4:
                    var = sum((x - avg) ** 2 for x in values) / n
                    std = math.sqrt(var)
                    if std > 1e-9:
                        for (fp, unit, mname, v) in flat:
                            if mname == name and abs(v - avg) / std > 2.0:
                                ctx.outliers.append({"file": fp, "unit": unit,
                                                     "metric": mname,
                                                     "value": round(v, 4),
                                                     "z": round((v - avg) / std, 2)})
                        ctx.outliers = ctx.outliers[:20]
            ordered = sorted(flat, key=lambda r: r[3], reverse=True)
            ctx.top_values = [{"file": f, "unit": u, "metric": m, "value": round(v, 4)}
                              for (f, u, m, v) in ordered[:top_n]]
            ctx.lowest_values = [{"file": f, "unit": u, "metric": m, "value": round(v, 4)}
                                 for (f, u, m, v) in ordered[-top_n:][::-1]]
            digest = f"{repo_id}|{commit_hash}|{ctx.total}|{len(rows)}"
            ctx.snapshot_id = hashlib.sha1(digest.encode()).hexdigest()[:12]
        except Exception as e:
            logger.error("context metrics: %s", e)
        return ctx

    # ---------------- Retrieval (ТЗ §1.2) ----------------

    @staticmethod
    def _keywords(question: str) -> List[str]:
        words = re.findall(r"[A-Za-zА-Яа-яЁё_]{3,}", (question or "").lower())
        seen = []
        for w in words:
            if w not in _STOPWORDS and w not in seen:
                seen.append(w)
        return seen[:20]

    def select_relevant(self, question: str, repo_ctx: RepositoryContext,
                        metrics_ctx: MetricsContext, git_ctx: GitContext,
                        repo_path: str, max_files: int = 8,
                        max_chars_per_file: int = 2500) -> Dict[str, Any]:
        """Project/Metrics/Git Index + keyword retrieval (ТЗ §1.2)."""
        result: Dict[str, Any] = {"files": {}, "functions": [],
                                  "metrics": [], "git": []}
        try:
            keywords = self._keywords(question)
            root = Path(repo_path or "")
            candidates: List[Tuple[float, str]] = []
            if root.is_dir():
                for p in root.rglob("*.py"):
                    try:
                        rel = str(p.relative_to(root))
                    except ValueError:
                        continue
                    if any(part.startswith(".") for part in p.relative_to(root).parts):
                        continue
                    name_l = rel.lower().replace("/", " ").replace("_", " ")
                    score = sum(2.0 for kw in keywords if kw in name_l)
                    # Бонус файлам из последнего коммита и с выбросами метрик.
                    if rel in (git_ctx.changed_files or []):
                        score += 3.0
                    for o in (metrics_ctx.outliers or []):
                        if o.get("file") == rel:
                            score += 2.0
                    # Бонус проблемным файлам из top values.
                    for t in (metrics_ctx.top_values or [])[:5]:
                        if t.get("file") == rel:
                            score += 1.0
                    if score > 0 or not keywords:
                        candidates.append((score, rel))
            candidates.sort(reverse=True)
            for _score, rel in candidates[:max_files]:
                try:
                    content = (root / rel).read_text(
                        encoding="utf-8", errors="ignore")[:max_chars_per_file]
                except Exception:
                    continue
                result["files"][rel] = content
                # Функции/классы из метрик этого файла.
                for key in (metrics_ctx.by_file.get(rel) or {}):
                    parts = key.split(":")
                    if len(parts) >= 2 and parts[0] in ("function", "class", "method"):
                        result["functions"].append(f"{rel}::{parts[1]}")
            result["functions"] = result["functions"][:30]
            # Релевантные метрики: выбросы + top.
            result["metrics"] = (metrics_ctx.outliers[:10]
                                 + metrics_ctx.top_values[:10])
            result["git"] = git_ctx.recent_commits[:5]
        except Exception as e:
            logger.error("context retrieval: %s", e)
        return result

    # ---------------- Assemble (ТЗ §1.3) ----------------

    def assemble(self, repo_id: str, repo_path: str,
                 workspace: Optional[Dict[str, Any]] = None,
                 provider: str = "", model: str = "",
                 active_tab: str = "", question: str = "",
                 mode: str = "auto", commit_hash: str = "",
                 model_window: int = 0) -> AssembledContext:
        """Сборка полного контекста с бюджетами по режимам (ТЗ §1.1-1.3).

        Режимы: auto (как standard + retrieval), brief, standard, full.
        """
        mode = (mode or "auto").lower()
        if mode not in ("auto", "brief", "standard", "full"):
            mode = "auto"
        window = model_window or MODEL_WINDOWS.get(provider.lower(), MODEL_WINDOWS["default"])
        budget = max(2000, int(window * 0.5))  # половина окна под контекст

        repo_ctx = self.build_repository_context(repo_id, repo_path)
        git_ctx = self.build_git_context(repo_id, repo_path)
        commit = commit_hash or git_ctx.commit_hash
        metrics_ctx = self.build_metrics_context(repo_id, commit)

        sections: Dict[str, Any] = {}
        chunks: List[str] = []

        def _add(title: str, body: str, key: str, count: Any = True):
            if body:
                chunks.append(f"### {title}\n{body}")
                sections[key] = count

        # Workspace (ТЗ §1.1).
        ws = workspace or {}
        ws_text = "\n".join([
            f"id: {ws.get('id', 'default')}",
            f"name: {ws.get('name', '')}",
            f"active repository: {repo_id}",
            f"active branch: {repo_ctx.branch or git_ctx.branch}",
            f"active tab: {active_tab}",
            f"AI provider: {provider}",
            f"AI model: {model}",
        ])
        _add("Workspace", ws_text, "workspace", True)

        # Repository.
        if mode == "brief":
            repo_text = (f"{repo_ctx.name} ({repo_ctx.file_count} файлов; "
                         f"языки: {dict(sorted(repo_ctx.languages.items(), key=lambda kv: -kv[1])[:6])})\n"
                         f"README:\n{(repo_ctx.readme or 'нет')[:1200]}")
        else:
            repo_text = (
                f"Name: {repo_ctx.name}\nPath: {repo_ctx.local_path}\n"
                f"Remote: {repo_ctx.remote_url or 'нет'}\nBranch: {repo_ctx.branch}\n"
                f"Files: {repo_ctx.file_count}, languages: {repo_ctx.languages}\n"
                f"Tree (первые строки):\n{repo_ctx.directory_tree[:3000]}\n"
                f"README:\n{(repo_ctx.readme or 'нет')[:2500]}")
            if mode in ("standard", "auto", "full") and repo_ctx.config_files:
                cfg = "\n".join(f"--- {n} ---\n{c[:800]}"
                                for n, c in list(repo_ctx.config_files.items())[:4])
                repo_text += f"\nConfig files:\n{cfg}"
            if mode == "full" and repo_ctx.package_files:
                pkg = "\n".join(f"--- {n} ---\n{c[:800]}"
                                for n, c in list(repo_ctx.package_files.items())[:3])
                repo_text += f"\nDependencies:\n{pkg}"
        _add("Repository", repo_text, "repository", True)
        sections["readme"] = bool(repo_ctx.readme)

        # Git.
        if mode == "brief":
            git_text = (f"HEAD {git_ctx.commit_hash[:8]} {git_ctx.author}: "
                        f"{git_ctx.message[:200]}; changed: {len(git_ctx.changed_files)}")
        else:
            recent = "\n".join(
                f"- {c['hash']} {c['author']}: {c['message']}" for c in git_ctx.recent_commits[:8])
            git_text = (
                f"Commit: {git_ctx.commit_hash}\nAuthor: {git_ctx.author}\n"
                f"Date: {git_ctx.date}\nMessage: {git_ctx.message[:500]}\n"
                f"Changed files ({len(git_ctx.changed_files)}): "
                f"{', '.join(git_ctx.changed_files[:20])}\n"
                f"Diff summary: {git_ctx.diff_summary or 'нет'}\n"
                f"Recent:\n{recent}")
        _add("Git", git_text, "git", True)
        sections["current_commit"] = bool(git_ctx.commit_hash)

        # Metrics — детально (ТЗ §1.1: НЕ агрегат-строка).
        if metrics_ctx.total:
            if mode == "brief":
                m_text = (f"total={metrics_ctx.total}, files={metrics_ctx.files}, "
                          f"avg by metric: {metrics_ctx.averages}")
                m_count = metrics_ctx.total
            else:
                lines = [f"total={metrics_ctx.total}, files={metrics_ctx.files}",
                         f"by type: {metrics_ctx.by_type}",
                         "by metric (avg/min/max/count):"]
                for name, st in sorted(metrics_ctx.by_metric.items()):
                    lines.append(f"  {name}: avg={st['avg']} min={st['min']} "
                                 f"max={st['max']} n={st['count']}")
                if metrics_ctx.outliers:
                    lines.append("outliers (|z|>2):")
                    lines += [f"  {o['file']}::{o['unit']} {o['metric']}={o['value']} (z={o['z']})"
                              for o in metrics_ctx.outliers[:12]]
                lines.append("top values:")
                lines += [f"  {t['file']}::{t['unit']} {t['metric']}={t['value']}"
                          for t in metrics_ctx.top_values[:12]]
                if mode in ("auto", "full"):
                    lines.append("lowest values:")
                    lines += [f"  t={t['value']} {t['file']}::{t['unit']} {t['metric']}"
                              for t in metrics_ctx.lowest_values[:8]]
                    if mode == "full":
                        lines.append("raw values (первые файлы):")
                        for f, mm in list(metrics_ctx.by_file.items())[:10]:
                            lines.append(f"  {f}: " + ", ".join(
                                f"{k}={v}" for k, v in list(mm.items())[:12]))
                m_text = "\n".join(lines)
                m_count = metrics_ctx.total
            _add("Metrics", m_text, "metrics", m_count)
        else:
            sections["metrics"] = 0

        # Relevant source (standard/auto/full).
        relevant: Dict[str, Any] = {}
        if mode in ("standard", "auto", "full") and question:
            max_f = 8 if mode != "full" else 15
            relevant = self.select_relevant(question, repo_ctx, metrics_ctx, git_ctx,
                                            repo_path, max_files=max_f)
            if relevant.get("files"):
                src = "\n".join(f"--- {fn} ---\n{code}"
                                for fn, code in relevant["files"].items())
                _add("Relevant source", src, "relevant_source",
                     f"{len(relevant['files'])} files")
            if relevant.get("functions"):
                _add("Relevant functions", ", ".join(relevant["functions"][:30]),
                     "relevant_functions", len(relevant["functions"]))

        text = "\n\n".join(chunks)
        estimated = max(1, len(text) // CHARS_PER_TOKEN)
        truncated = False
        if estimated > budget:
            # Режем с конца (релевантный код), сохраняя начало (workspace/repo/git).
            allowed_chars = budget * CHARS_PER_TOKEN
            text = text[:allowed_chars] + "\n\n[контекст обрезан до бюджета модели]"
            estimated = budget
            truncated = True

        sections["files"] = len(relevant.get("files", {})) if relevant else 0
        logger.info("context: repo=%s commit=%s mode=%s tokens~%d truncated=%s",
                    repo_id, commit[:8], mode, estimated, truncated)
        return AssembledContext(
            text=text, repository_id=repo_id, commit_hash=commit,
            metrics_snapshot_id=metrics_ctx.snapshot_id,
            sections=sections, estimated_tokens=estimated, truncated=truncated)

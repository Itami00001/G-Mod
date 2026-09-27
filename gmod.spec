# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для GMod.

Включает:
- data/config.yaml, README.md
- tree-sitter грамматики (Python)
- иконку приложения
- hiddenimports всех слоёв Clean Architecture
- numpy, numpy.core, numpy.linalg для pyqtgraph/networkx
- collect_data_files для litellm и pyqtgraph
- collect_submodules для pyqtgraph
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Собираем tree-sitter грамматики для Python
tree_sitter_grammars = []
try:
    import tree_sitter_python as tsp
    import tree_sitter
    grammar_path = Path(tsp.__file__).parent / "grammar"
    if grammar_path.exists():
        tree_sitter_grammars.append((str(grammar_path), "tree_sitter_python/grammar"))
except ImportError:
    pass

# Собираем data files для litellm и pyqtgraph
litellm_data_files = collect_data_files('litellm')
pyqtgraph_data_files = collect_data_files('pyqtgraph')
pyqtgraph_hiddenimports = collect_submodules('pyqtgraph')
# tiktoken: кодировки (cl100k_base и др.) лежат в отдельном пакете
# tiktoken_ext, который litellm подхватывает через entry points, —
# без явного сбора frozen-exe падает "Unknown encoding cl100k_base".
tiktoken_data_files = collect_data_files('tiktoken')
tiktoken_ext_data_files = collect_data_files('tiktoken_ext')

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".") / "src")],
    binaries=[],
    datas=[
        ("data/config.yaml", "data"),
        ("README.md", "."),
        ("assets/icon.ico", "."),
    ] + tree_sitter_grammars + litellm_data_files + pyqtgraph_data_files
    + tiktoken_data_files + tiktoken_ext_data_files,
    hiddenimports=[
        # Токенизаторы (entry-point плагины tiktoken_ext не видны анализатору)
        "tiktoken", "tiktoken.registry", "tiktoken_ext", "tiktoken_ext.openai_public",
        # Core UI
        "gmod.ui.main_window",
        "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui",
        "PySide6.QtNetwork", "PySide6.QtSvg",
        # Infrastructure
        "gmod.infrastructure.db.database",
        "gmod.infrastructure.git.git_parser",
        "gmod.infrastructure.parsers.python_parser",
        "gmod.infrastructure.parsers.factory",
        "gmod.infrastructure.metrics.factory",
        "gmod.infrastructure.metrics.complexity",
        "gmod.infrastructure.metrics.size",
        "gmod.infrastructure.metrics.coupling",
        "gmod.infrastructure.metrics.oop",
        "gmod.infrastructure.metrics.comments",
        "gmod.infrastructure.metrics.code_smells",
        "gmod.infrastructure.metrics.vcs",
        "gmod.infrastructure.llm.factory",
        "gmod.infrastructure.llm.ollama_provider",
        "gmod.infrastructure.llm.groq_provider",
        "gmod.infrastructure.llm.gemini_provider",
        "gmod.infrastructure.llm.session_manager",
        "gmod.infrastructure.llm.base",
        # Usecases
        "gmod.usecases.analyze_repository",
        "gmod.usecases.run_archaeologist",
        # Config
        "gmod.config.settings",
        "gmod.config.constants",
        "gmod.config.logging_config",
        # Domain
        "gmod.domain.entities",
        "gmod.domain.interfaces",
        "gmod.domain.schemas",
        "gmod.domain.prompts",
        # Visualization
        "pyqtgraph", "networkx",
        # Parsing
        "tree_sitter", "tree_sitter_python",
        # Git
        "git",
        # LLM
        "litellm",
        # NumPy (required by pyqtgraph, networkx)
        "numpy", "numpy.core", "numpy.linalg",
        # Stdlib
        "yaml", "json", "sqlite3", "pathlib", "tempfile",
    ] + pyqtgraph_hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tests", "pytest", "pytest_qt", "black", "ruff", "mypy",
        "pre_commit", "IPython", "jupyter", "notebook",
        "tkinter", "matplotlib", "pandas", "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GMod",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="assets/icon.ico" if Path("assets/icon.ico").exists() else None,
    version="file_version_info.txt" if Path("file_version_info.txt").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GMod",
)

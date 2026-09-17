# GMod - Git Archaeologist

GMod — это инструмент для AI-анализа кода с визуализацией метрик. Проект помогает анализировать изменения в коде, вычислять метрики сложности и получать AI-отчёты о потенциальных проблемах.

## Стек технологий

- **Python 3.11+**
- **PySide6** — Qt фреймворк для GUI
- **gitpython** — работа с Git репозиториями
- **tree-sitter** — парсинг кода
- **litellm** — работа с LLM провайдерами
- **SQLite** — хранение данных
- **pyqtgraph** — визуализация графов
- **networkx** — работа с графами
- **pydantic** — валидация данных
- **qdarktheme** — тёмная тема для Qt

## Архитектура

Проект следует принципам Clean Architecture:

```
src/gmod/
├── domain/           # Сущности и интерфейсы
├── usecases/         # Сценарии использования
├── infrastructure/   # Внешние зависимости (Git, БД, LLM, парсеры)
├── ui/              # PySide6 виджеты
└── config/          # Конфигурация и константы
```

## Установка и разработка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd g-mod
```

### 2. Создание виртуального окружения

```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -e .
pip install -e ".[dev]"
```

### 4. Настройка pre-commit hooks

```bash
pre-commit install
```

### 5. Запуск приложения

```bash
python main.py
```

## Разработка

### Форматирование кода

```bash
black src/ tests/
```

### Линтинг

```bash
ruff check src/ tests/
```

### Типизация

```bash
mypy src/
```

### Запуск тестов

```bash
pytest tests/
```

## Структура проекта

```
g-mod/
├── src/
│   └── gmod/
│       ├── domain/              # Доменные сущности
│       │   ├── entities.py      # Repository, Commit, FileDiff, CodeUnit, MetricResult
│       │   └── interfaces.py    # IGitParser, ILanguageParser, IMetric, ILLMProvider
│       ├── usecases/            # Сценарии использования
│       ├── infrastructure/      # Инфраструктура
│       │   ├── git/            # Git парсер
│       │   ├── db/              # База данных
│       │   ├── llm/             # LLM провайдеры
│       │   ├── parsers/         # Парсеры языков
│       │   └── metrics/         # Метрики кода
│       ├── ui/                  # Пользовательский интерфейс
│       │   └── main_window.py   # Главное окно
│       └── config/              # Конфигурация
│           ├── constants.py     # Константы
│           └── logging_config.py  # Настройка логирования
├── data/                        # Данные приложения
│   ├── config.yaml             # Конфигурация
│   └── gmod.db                 # База данных SQLite
├── logs/                        # Логи приложения
├── tests/                       # Тесты
├── main.py                      # Точка входа
├── pyproject.toml              # Зависимости проекта
└── README.md                   # Этот файл
```

## Конфигурация

Конфигурация хранится в `data/config.yaml`. Основные секции:

- `app` — общие настройки приложения
- `ui` — настройки интерфейса
- `database` — настройки БД
- `llm` — настройки LLM провайдеров
- `analysis` — настройки анализа кода
- `logging` — настройки логирования

## Логирование

Логи сохраняются в `logs/gmod.log` с ротацией (максимум 10 MB, 5 файлов).

Уровень логирования можно изменить в `data/config.yaml`:

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Сборка в .exe

Для сборки используется PyInstaller:

```bash
pip install pyinstaller
pyinstaller gmod.spec
```

## Планы развития

- [ ] Реализация парсеров для разных языков
- [ ] Внедрение всех метрик из спецификации
- [ ] Интеграция с LLM провайдерами
- [ ] Визуализация графов зависимостей
- [ ] Режимы "Детектив" и "Архитектор"

## Лицензия

MIT License

## Контакты

GMod Team

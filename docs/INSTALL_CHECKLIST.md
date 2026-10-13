# Чек-лист сборки GMod (перед pyinstaller + ISCC)

## 1. Чистка мусора (иначе попадёт в дистрибутив!)

```powershell
# Удалить клонированные репозитории из прошлой отладки exe:
Remove-Item -Recurse -Force dist\GMod\data\repos -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force .pytest_cache -ErrorAction SilentlyContinue
```

## 2. Проверки перед сборкой

- [ ] `python -m pytest tests/ -q` — всё зелёное.
- [ ] `data/config.yaml` НЕ содержит `api_key` со значениями
      (ключи живут только в Credential Manager).
- [ ] `dist\GMod\data\` содержит только `config.yaml`
      (проверить: там НЕ должно быть `repos/` и `gmod.db`).
- [ ] `vendor\portable-git\cmd\git.exe` на месте
      (если нет — `powershell -ExecutionPolicy Bypass -File tools\fetch_portable_git.ps1`).

## 3. Сборка

```powershell
pyinstaller gmod.spec --clean -y
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

Результат: `installer_output\g-mod-installer.exe`.

## 4. Проверка на чистой машине

- [ ] Установка проходит, ярлыки создаются.
- [ ] При старте НЕТ предупреждения «Git не найден»
      (иначе — portable-git не попал в installer).
- [ ] Клонирование публичного репозитория работает.
- [ ] `%APPDATA%\GMod\` содержит только свежие `config.yaml`/`gmod.db`.
      Учтите: `%APPDATA%` — это Roaming, при общем доменном пользователе
      база может «переехать» со старой машины сама.
- [ ] Метрики считаются после загрузки репозитория.
- [ ] Проверка провайдеров показывает статусы с HTTP-кодами.

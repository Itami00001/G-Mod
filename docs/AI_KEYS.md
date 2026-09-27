# API-ключи нейросетей

## Основной режим: Ollama localhost

GMod рассчитан на локальную Ollama и не требует API-ключа:

- сайт: https://ollama.com/
- загрузка Windows: https://ollama.com/download/windows
- документация API: https://github.com/ollama/ollama/blob/main/docs/api.md
- локальный endpoint: `http://localhost:11434`

Проверка установки:

```powershell
ollama serve
ollama pull llama3.2:3b
curl http://localhost:11434/api/tags
```

В GMod укажите провайдера Ollama и модель, например `llama3.2:3b`.
Для обычной локальной Ollama поле API Key оставьте пустым. Ключ нужен только для Ollama Cloud или защищённого прокси.

## Облачные альтернативы

- Groq Console: https://console.groq.com/keys
- Google AI Studio / Gemini: https://aistudio.google.com/app/apikey
- OpenAI Platform: https://platform.openai.com/api-keys
- Anthropic Console: https://console.anthropic.com/settings/keys

Ключи нельзя публиковать в Git, записывать в логи или помещать в отчёты. В GMod ключ хранится в пользовательской конфигурации, а в логах разрешено показывать только факт наличия и длину ключа.

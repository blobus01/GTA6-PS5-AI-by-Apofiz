# GTA6 PS5 AI by Apofiz — правила для агентов

- Основная ветка `main`. Коммиты небольшие, по делу.
- Никогда не коммитить секреты: `.env.local`, `~/.ps5-remote/`, PSN npsso, ключи консоли, логи, скриншоты.
- Перед пушем: `.venv/bin/python -m pytest -q tests` и проверка на секреты.
- Апстрим (основа удалённого пульта): https://github.com/Jeff-Kazzee/ps5-agent-remote (MIT) — remote `upstream`.

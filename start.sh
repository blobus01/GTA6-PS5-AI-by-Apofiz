#!/bin/bash
# Запуск PS5 Agent Remote на Маке: веб-пульт http://127.0.0.1:8765
cd "$(dirname "$0")"
exec .venv/bin/python server.py

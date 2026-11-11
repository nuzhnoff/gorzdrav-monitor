#!/bin/bash
# Ручной запуск Telegram-бота Горздрав на Orange Pi
# Использование: bash run_bot.sh

cd ~/gorzdrav_spb_checkbot || { echo "Папка проекта не найдена"; exit 1; }

# Активация venv
source venv/bin/activate || { echo "venv не найден"; exit 1; }

# Проверка .env
if [ ! -f .env ]; then
    echo ".env не найден"
    exit 1
fi

# Запуск бота
echo "Запуск бота..."
python src/app.py

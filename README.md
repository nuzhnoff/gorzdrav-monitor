# Gorzdrav Monitor

Мониторинг свободных талонов на портале [gorzdrav.spb.ru](https://gorzdrav.spb.ru) с уведомлениями на email.

## Скрипты

- **`build_db.py`** — собирает базу врачей (SQLite) через API Горздрава. Запускается один раз.
- **`search_db.py`** — интерактивный поиск по базе: поликлиника → специальность → врач. Записывает выбранного врача в `doctor_info.json`.
- **`monitor.py`** — проверяет расписание выбранного врача каждые 5 минут и отправляет email, когда появляются свободные талоны.

## Требования

- Python 3.10+
- Аккаунт Яндекс.Почты (для SMTP)

## Установка

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/nuzhnoff/gorzdrav-monitor.git
   cd gorzdrav-monitor
##Создайте виртуальное окружение и установите зависимости:
bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
##Скопируйте .env.example в .env и заполните:
bash

cp .env.example .env
nano .env

##Важно: YANDEX_PASSWORD — это пароль приложения, не основной пароль от почты. Создайте его в настройках Яндекс ID → «Пароли приложений» → тип «Почта».

##Добавьте сертификат Минцифры в certifi (требуется для доступа к gorzdrav.spb.ru):
bash

curl -k "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt" -w "\n" >> $(python -m certifi)

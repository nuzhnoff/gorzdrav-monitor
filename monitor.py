"""Мониторинг талонов по списку врачей из watchlist.json."""
import requests
import time
import smtplib
import os
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

import watchlist

load_dotenv()

CHECK_INTERVAL = 300       # проверка каждые 5 минут
NOTIFY_COOLDOWN = 3600     # по одному врачу не спамить чаще раза в час

SMTP_HOST = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_USER = os.getenv("YANDEX_LOGIN")
SMTP_PASS = os.getenv("YANDEX_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_RECEIVER")

# {(lpu_id, doctor_id): timestamp последнего уведомления}
last_notified = {}


def send_email(subject, body):
    if not all([SMTP_USER, SMTP_PASS, EMAIL_TO]):
        print("Ошибка: не заданы YANDEX_LOGIN/YANDEX_PASSWORD/EMAIL_RECEIVER в .env")
        return
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())
        print(f"[{time.strftime('%H:%M:%S')}] Email отправлен на {EMAIL_TO}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка email: {e}")


def build_link(lpu_id, spec_id, doctor_id):
    return (
        "https://gorzdrav.spb.ru/service-free-schedule"
        f"#%5B%7B%22lpu%22:%22{lpu_id}%22%7D,"
        f"%7B%22speciality%22:%22{spec_id}%22%7D,"
        f"%7B%22doctor%22:%22{doctor_id}%22%7D%5D"
    )


def check_doctor(lpu_id, doctor_id, details):
    """Проверяет одного врача. details — dict из БД (ФИО, специальность, ЛПУ)."""
    key = (str(lpu_id), str(doctor_id))
    name = details["doctor_name"]
    spec = details["speciality"]
    lpu_name = details["lpu_name"]
    spec_id = details.get("speciality_id", "")

    # Кулдаун: если недавно уже уведомляли — пропускаем
    if key in last_notified:
        elapsed = time.time() - last_notified[key]
        if elapsed < NOTIFY_COOLDOWN:
            mins = int((NOTIFY_COOLDOWN - elapsed) / 60)
            print(f"[{time.strftime('%H:%M:%S')}] {name}: кулдаун, ещё {mins} мин")
            return

    url = f"https://gorzdrav.spb.ru/_api/api/v2/schedule/lpu/{lpu_id}/doctor/{doctor_id}/timetable"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        result = data.get("result")
        if result is None:
            print(f"[{time.strftime('%H:%M:%S')}] {name}: неожиданный формат ответа")
            return

        free_days = []
        for day in result:
            appts = day.get("appointments", [])
            if appts:
                slots_fmt = []
                for a in appts[:5]:
                    start = a.get("visitStart", "")
                    end = a.get("visitEnd", "")
                    t_start = start[11:16] if len(start) >= 16 else start
                    t_end = end[11:16] if len(end) >= 16 else end
                    room = a.get("room") or "—"
                    addr = a.get("address") or ""
                    line = f"{t_start}–{t_end}  |  каб. {room}"
                    if addr:
                        line += f"  |  {addr}"
                    slots_fmt.append(line)
                free_days.append({
                    "date": day.get("visitStart", "")[:10],
                    "count": len(appts),
                    "slots": slots_fmt,
                })

        if free_days:
            link = build_link(lpu_id, spec_id, doctor_id)
            subject = f"🎉 Талоны: {name} ({spec})"
            lines = [
                f"👨‍⚕️ Врач: {name}",
                f"🩺 Специальность: {spec}",
                f"🏥 Учреждение: {lpu_name}",
            ]
            if details.get("lpu_address"):
                lines.append(f"📍 Адрес: {details['lpu_address']}")
            lines += [
                "",
                "🔗 Ссылка на запись:",
                link,
                "",
            ]
            for d in free_days:
                word = "слот" if d["count"] == 1 else ("слота" if d["count"] < 5 else "слотов")
                lines.append(f"📅 {d['date']} — {d['count']} {word}")
                for slot in d["slots"]:
                    lines.append(f"   • {slot}")
                lines.append("")
            body = "\n".join(lines)
            print(f"[{time.strftime('%H:%M:%S')}] {name}: ТАЛОНЫ ЕСТЬ! Отправка email...")
            send_email(subject, body)
            last_notified[key] = time.time()
        else:
            print(f"[{time.strftime('%H:%M:%S')}] {name}: талонов нет (дней: {len(result)})")

    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] {name}: сеть — {e}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] {name}: ошибка — {e}")


def main():
    print("Монитор запущен (watchlist режим).")
    print(f"Интервал: {CHECK_INTERVAL} сек, кулдаун уведомлений: {NOTIFY_COOLDOWN} сек")
    print(f"Email: {EMAIL_TO}\n")

    while True:
        entries = watchlist.list_watchlist()
        if not entries:
            print(f"[{time.strftime('%H:%M:%S')}] Watchlist пуст. Ждём...")
            time.sleep(CHECK_INTERVAL)
            continue

        print(f"\n[{time.strftime('%H:%M:%S')}] Проверка {len(entries)} врач(ей)...")
        for entry in entries:
            lpu_id = str(entry.get("lpu_id", ""))
            doctor_id = str(entry.get("doctor_id", ""))
            details = watchlist.get_doctor_details(doctor_id, lpu_id)
            if not details:
                print(f"[{time.strftime('%H:%M:%S')}] {lpu_id}/{doctor_id}: не найден в БД")
                continue
            check_doctor(lpu_id, doctor_id, details)
            time.sleep(0.5)  # пауза между врачами, чтобы не долбить API

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОстановлено.")

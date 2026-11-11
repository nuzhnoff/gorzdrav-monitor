import requests
import time
import smtplib
import sqlite3
import json
import os
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "doctors.db"
DOCTOR_INFO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doctor_info.json")
CHECK_INTERVAL = 300

SMTP_HOST = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_USER = os.getenv("YANDEX_LOGIN")
SMTP_PASS = os.getenv("YANDEX_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_RECEIVER")

def load_doctor_info():
    """Читает doctor_info.json. Возвращает dict или None."""
    try:
        with open(DOCTOR_INFO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка JSON в {DOCTOR_INFO_FILE}: {e}")
        return None

def get_doctor_from_db(doctor_id):
    """Ищет врача в БД. Возвращает (lpu_id, name, speciality_id, speciality_name, lpu_name) или None."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            SELECT lpu_id, name, speciality_id, speciality_name, lpu_name
            FROM doctors WHERE id = ?
        """, (str(doctor_id),))
        row = cur.fetchone()
        conn.close()
        return row
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Ошибка БД: {e}")
        return None

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

def check_doctor(info):
    """info — dict из doctor_info.json + данные из БД."""
    doctor_id = info["doctor_id"]
    lpu_id = info["lpu_id"]
    spec_id = info["speciality_id"]
    name = info["doctor_name"]
    spec_name = info["speciality"]
    lpu_name = info["lpu_name"]

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
                free_days.append({
                    "date": day.get("visitStart", "")[:10],
                    "count": len(appts),
                    "slots": appts[:5],
                })

        if free_days:
            link = build_link(lpu_id, spec_id, doctor_id)
            subject = f"🎉 Талоны: {name} ({spec_name})"
            lines = [
                f"👨‍⚕️ Врач: {name}",
                f"🩺 Специальность: {spec_name}",
                f"🏥 Учреждение: {lpu_name}",
            ]
            if info.get("lpu_address"):
                lines.append(f"📍 Адрес: {info['lpu_address']}")
            lines += [
                "",
                "🔗 Ссылка на запись:",
                link,
                "",
            ]
            for d in free_days:
                lines.append(f"📅 {d['date']} — {d['count']} слотов")
                for slot in d["slots"]:
                    lines.append(f"   • {slot}")
                lines.append("")
            body = "\n".join(lines)
            print(f"[{time.strftime('%H:%M:%S')}] {name}: ТАЛОНЫ ЕСТЬ! Отправка...")
            send_email(subject, body)
            time.sleep(3600)
        else:
            print(f"[{time.strftime('%H:%M:%S')}] {name}: талонов нет (дней: {len(result)})")

    except requests.exceptions.RequestException as e:
        print(f"[{time.strftime('%H:%M:%S')}] {name}: сеть — {e}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] {name}: ошибка — {e}")

def resolve_info(file_info):
    """
    Объединяет данные из doctor_info.json с данными из БД.
    Приоритет у БД (там точные ФИО/специальность). Fallback — файл.
    """
    doctor_id = file_info.get("doctor_id")
    if not doctor_id:
        return None
    row = get_doctor_from_db(doctor_id)
    if row:
        lpu_id, name, spec_id, spec_name, lpu_name = row
        return {
            "doctor_id": str(doctor_id),
            "lpu_id": str(lpu_id),
            "speciality_id": str(spec_id),
            "doctor_name": name,
            "speciality": spec_name,
            "lpu_name": lpu_name,
            "lpu_address": file_info.get("lpu_address", ""),
        }
    # fallback на файл
    if all(k in file_info for k in ("lpu_id", "speciality_id", "doctor_name", "speciality", "lpu_name")):
        return file_info
    print(f"[{time.strftime('%H:%M:%S')}] Врач {doctor_id} не найден в БД и в файле недостаточно данных")
    return None

def main():
    print("Монитор запущен (автоматический режим).")
    print(f"Файл настроек: {DOCTOR_INFO_FILE}")
    print(f"Интервал: {CHECK_INTERVAL} сек.\n")

    last_doctor_id = None
    while True:
        file_info = load_doctor_info()
        if not file_info:
            print(f"[{time.strftime('%H:%M:%S')}] doctor_info.json не найден или пуст. Ждём...")
            time.sleep(CHECK_INTERVAL)
            continue

        info = resolve_info(file_info)
        if not info:
            time.sleep(CHECK_INTERVAL)
            continue

        # Если врач сменился — сообщим в лог
        if info["doctor_id"] != last_doctor_id:
            print(f"[{time.strftime('%H:%M:%S')}] Активный врач: {info['doctor_name']} "
                  f"({info['speciality']}, {info['lpu_name']})")
            last_doctor_id = info["doctor_id"]

        check_doctor(info)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nОстановлено.")

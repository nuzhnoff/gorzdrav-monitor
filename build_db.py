import requests
import sqlite3
import time
import sys

BASE_URL = "https://gorzdrav.spb.ru/_api/api/v2"
DB_PATH = "doctors.db"
REQUEST_DELAY = 0.3

# --- ID ПУШКИНСКОГО РАЙОНА ---
PUSHKIN_DISTRICT_ID = "16"  # ID из ваших ссылок

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS districts (
            id TEXT PRIMARY KEY,
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS lpus (
            id TEXT PRIMARY KEY,
            district_id TEXT,
            name TEXT,
            address TEXT
        );
        CREATE TABLE IF NOT EXISTS specialities (
            id TEXT PRIMARY KEY,
            lpu_id TEXT,
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS doctors (
            id TEXT,
            lpu_id TEXT,
            speciality_id TEXT,
            name TEXT,
            speciality_name TEXT,
            lpu_name TEXT,
            PRIMARY KEY (id, lpu_id)
        );
    """)
    conn.commit()
    return conn

def api_get(url):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Ошибка запроса {url}: {e}")
        return None

def build():
    conn = init_db()
    cur = conn.cursor()

    # 0. Получаем название района (для информации)
    print(f"=== Сбор данных для района ID: {PUSHKIN_DISTRICT_ID} ===")
    districts_data = api_get(f"{BASE_URL}/shared/districts")
    district_name = "Пушкинский"
    if districts_data and districts_data.get("success"):
        for d in districts_data.get("result", []):
            if str(d.get("id")) == PUSHKIN_DISTRICT_ID:
                district_name = d.get("name", district_name)
                break
    print(f"Район: {district_name}")

    # Сохраняем район в БД (чтобы было)
    cur.execute("INSERT OR REPLACE INTO districts (id, name) VALUES (?, ?)",
                (PUSHKIN_DISTRICT_ID, district_name))
    conn.commit()

    # 1. ЛПУ Пушкинского района
    print("\n=== ЛПУ Пушкинского района ===")
    data = api_get(f"{BASE_URL}/shared/district/{PUSHKIN_DISTRICT_ID}/lpus")
    if not data or not data.get("success"):
        print("Не удалось получить ЛПУ")
        return
    lpus = data.get("result", [])
    for l in lpus:
        cur.execute("INSERT OR REPLACE INTO lpus (id, district_id, name, address) VALUES (?, ?, ?, ?)",
                    (str(l["id"]), PUSHKIN_DISTRICT_ID,
                     l.get("lpuFullName") or l.get("lpuShortName", ""),
                     l.get("address", "")))
    conn.commit()
    print(f"ЛПУ: {len(lpus)}")

    # 2. Специальности и врачи по каждому ЛПУ
    print("\n=== Специальности и врачи ===")
    cur.execute("SELECT id, name FROM lpus WHERE district_id = ?", (PUSHKIN_DISTRICT_ID,))
    all_lpus = cur.fetchall()
    for lpu_id, lpu_name in all_lpus:
        data = api_get(f"{BASE_URL}/schedule/lpu/{lpu_id}/specialties")
        if not data or not data.get("success"):
            continue
        specs = data.get("result", [])
        for s in specs:
            sid = str(s["id"])
            cur.execute("INSERT OR REPLACE INTO specialities (id, lpu_id, name) VALUES (?, ?, ?)",
                        (sid, lpu_id, s.get("name", "")))
            data2 = api_get(f"{BASE_URL}/schedule/lpu/{lpu_id}/speciality/{sid}/doctors")
            if data2 and data2.get("success"):
                docs = data2.get("result", [])
                for doc in docs:
                    cur.execute("""INSERT OR REPLACE INTO doctors 
                                   (id, lpu_id, speciality_id, name, speciality_name, lpu_name) 
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (str(doc["id"]), lpu_id, sid,
                                 doc.get("name", ""), s.get("name", ""), lpu_name))
            time.sleep(REQUEST_DELAY)
        conn.commit()
        print(f"  ЛПУ {lpu_name}: {len(specs)} специальностей")
        time.sleep(REQUEST_DELAY)

    conn.close()
    print("\n=== Готово ===")

if __name__ == "__main__":
    build()

#!/usr/bin/env python3
"""Интерактивный поиск по doctors.db + запись выбранного врача в doctor_info.json."""
import sqlite3
import sys
import json
import os

DB_PATH = "doctors.db"
DOCTOR_INFO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doctor_info.json")

def connect():
    try:
        return sqlite3.connect(DB_PATH)
    except sqlite3.Error as e:
        print(f"Ошибка открытия БД: {e}")
        sys.exit(1)

def list_lpus(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT d.lpu_id, d.lpu_name, l.address, COUNT(*) as cnt
        FROM doctors d
        LEFT JOIN lpus l ON l.id = d.lpu_id
        GROUP BY d.lpu_id, d.lpu_name, l.address
        ORDER BY d.lpu_name
    """)
    return cur.fetchall()

def list_specialities(conn, lpu_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT speciality_id, speciality_name, COUNT(*) as cnt
        FROM doctors
        WHERE lpu_id = ?
        GROUP BY speciality_id, speciality_name
        ORDER BY speciality_name
    """, (lpu_id,))
    return cur.fetchall()

def list_doctors(conn, lpu_id, speciality_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name
        FROM doctors
        WHERE lpu_id = ? AND speciality_id = ?
        ORDER BY name
    """, (lpu_id, speciality_id))
    return cur.fetchall()

def choose(prompt, items, display):
    if not items:
        print("  (пусто)")
        return None
    for i, item in enumerate(items, 1):
        print(f"  {i}. {display(item)}")
    print()
    while True:
        raw = input(f"{prompt} (номер, 0 — назад): ").strip()
        if raw == "0":
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return items[int(raw) - 1]
        print("  Неверный ввод, попробуйте снова.")

def save_doctor_info(lpu_id, lpu_name, lpu_address, spec_id, spec_name, doctor_id, doctor_name):
    data = {
        "doctor_name": doctor_name,
        "speciality": spec_name,
        "speciality_id": str(spec_id),
        "lpu_name": lpu_name,
        "lpu_address": lpu_address or "",
        "lpu_id": str(lpu_id),
        "doctor_id": str(doctor_id),
    }
    with open(DOCTOR_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n✅ Сохранено в {DOCTOR_INFO_FILE}:")
    print(f"   Врач: {doctor_name}")
    print(f"   Специальность: {spec_name}")
    print(f"   Поликлиника: {lpu_name}")
    if lpu_address:
        print(f"   Адрес: {lpu_address}")
    print(f"   ID врача: {doctor_id}")
    print(f"   ID ЛПУ: {lpu_id}")
    print(f"   ID специальности: {spec_id}")

def main():
    conn = connect()
    while True:
        print("\n" + "=" * 70)
        print("  ПОИСК ПО БАЗЕ ВРАЧЕЙ")
        print("=" * 70)

        lpus = list_lpus(conn)
        if not lpus:
            print("В базе нет данных. Запустите build_db.py.")
            return

        print(f"\nПоликлиники ({len(lpus)}):\n")
        lpu = choose("Выберите поликлинику", lpus,
                     lambda x: f"{x[1]}\n       Адрес: {x[2] or '—'}  [{x[3]} врачей]")
        if lpu is None:
            print("Выход.")
            break
        lpu_id, lpu_name, lpu_address, _ = lpu

        while True:
            specs = list_specialities(conn, lpu_id)
            print(f"\n--- {lpu_name} ---")
            if lpu_address:
                print(f"    Адрес: {lpu_address}")
            print(f"\nСпециальности ({len(specs)}):\n")
            spec = choose("Выберите специальность", specs,
                          lambda x: f"{x[1]}  [{x[2]} врачей]")
            if spec is None:
                break
            spec_id, spec_name, _ = spec

            doctors = list_doctors(conn, lpu_id, spec_id)
            while True:
                print(f"\n--- {lpu_name} ---")
                if lpu_address:
                    print(f"    Адрес: {lpu_address}")
                print(f"    Специальность: {spec_name}")
                print(f"\nВрачи ({len(doctors)}):\n")
                for i, (doc_id, doc_name) in enumerate(doctors, 1):
                    print(f"  {i}. {doc_name}  (ID: {doc_id})")
                print()
                raw = input("Выберите врача для сохранения в doctor_info.json (0 — назад): ").strip()
                if raw == "0":
                    break
                if raw.isdigit() and 1 <= int(raw) <= len(doctors):
                    doc_id, doc_name = doctors[int(raw) - 1]
                    save_doctor_info(lpu_id, lpu_name, lpu_address,
                                     spec_id, spec_name, doc_id, doc_name)
                    input("\nНажмите Enter, чтобы продолжить...")
                    break
                print("  Неверный ввод, попробуйте снова.")
    conn.close()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")

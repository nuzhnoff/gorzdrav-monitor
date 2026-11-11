import smtplib
from email.mime.text import MIMEText
from email.header import Header
import os
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_USER = os.getenv("YANDEX_LOGIN")
SMTP_PASS = os.getenv("YANDEX_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_RECEIVER")

print(f"Логин: {SMTP_USER}")
print(f"Кому: {EMAIL_TO}")
print(f"Пароль задан: {'да' if SMTP_PASS else 'НЕТ'}")

msg = MIMEText("Это тестовое письмо от монитора Горздрав.", "plain", "utf-8")
msg["Subject"] = Header("Тест монитора Горздрав", "utf-8")
msg["From"] = SMTP_USER
msg["To"] = EMAIL_TO

try:
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())
    print("✅ Письмо отправлено. Проверьте почту.")
except Exception as e:
    print(f"❌ Ошибка: {e}")

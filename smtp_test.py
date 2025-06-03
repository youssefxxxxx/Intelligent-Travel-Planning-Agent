# smtp_test.py

import os
import ssl
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Charge les variables depuis .env
load_dotenv()

host = os.getenv("SMTP_HOST")
port = int(os.getenv("SMTP_PORT", "587"))
user = os.getenv("SMTP_USER")
pwd  = os.getenv("SMTP_PASS")
to   = os.getenv("EMAIL_TO")

# Construction du message
msg = EmailMessage()
msg["Subject"] = "Test SMTP depuis travel_planner"
msg["From"] = user
msg["To"] = to
msg.set_content("Ceci est un test d’envoi SMTP via le script Python.")

# Envoi
context = ssl.create_default_context()
with smtplib.SMTP(host, port) as server:
    server.starttls(context=context)
    server.login(user, pwd)
    server.send_message(msg)

print("E-mail de test envoyé avec succès !")

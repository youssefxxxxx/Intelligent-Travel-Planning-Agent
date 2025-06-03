# services/accommodation.py

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Mapping

_SMTP = {
    "host": os.getenv("SMTP_HOST"),
    "port": int(os.getenv("SMTP_PORT", "587")),
    "user": os.getenv("SMTP_USER"),
    "pass": os.getenv("SMTP_PASS"),
}

def send_confirmation_email(to_addr: str, hotel: Mapping, trip_id: str) -> None:
    """
    Envoie un e-mail de demande de confirmation pour la réservation d'un hôtel.
    """
    body = f"""Bonjour,

Vous avez demandé une réservation pour le voyage {trip_id} :

 Hôtel : {hotel['name']}
 Prix total : {hotel['total']} €
 Dates      : {hotel['check_in']} → {hotel['check_out']}

Merci de confirmer en répondant OK à cet e-mail.

Cordialement,
Votre agent IA
"""
    msg = EmailMessage()
    msg["Subject"] = f"[Action requise] Confirmation hôtel – {hotel['name']}"
    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = to_addr
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(_SMTP["host"], _SMTP["port"]) as s:
        s.starttls(context=context)
        s.login(_SMTP["user"], _SMTP["pass"])
        s.send_message(msg)

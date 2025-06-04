import os, smtplib, mimetypes
from email.message import EmailMessage

def send_confirmation_email(
    recipient_email: str,
    hotel: dict,
    trip_id: str,
    attachment_path: str | None = None,
    gsheet_url: str | None = None,
):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("EMAIL_FROM", smtp_user)

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass]):
        raise RuntimeError("❌ SMTP_* non configurées.")

    subject = f"[Action requise] Confirmation hôtel – {hotel['name']}"
    body_txt = f"""
Bonjour,

Voici la confirmation de votre réservation factice :

Nom de l’hôtel : {hotel['name']}
Prix total estimé : {hotel['total']} €
Dates : {hotel['check_in']} → {hotel['check_out']}
Référence voyage : {trip_id}

{ 'Vous pouvez consulter votre itinéraire ici : ' + gsheet_url if gsheet_url else '' }

Ceci est un e-mail de démonstration.
Bonne journée,
L’Agent de Voyage IA
"""

    msg = EmailMessage()
    msg["From"] = email_from
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.set_content(body_txt)

    # attachment ?
    if attachment_path and os.path.exists(attachment_path):
        ctype, encoding = mimetypes.guess_type(attachment_path)
        maintype, subtype = (ctype.split("/", 1) if ctype else ("application", "octet-stream"))
        with open(attachment_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=os.path.basename(attachment_path),
            )

    # send
    with smtplib.SMTP(smtp_host, int(smtp_port)) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)

# services/sheets.py

from __future__ import annotations
import os, tempfile, datetime as dt

import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def _create_gsheet_with_tabs(xlsx_path: str, share_with: str) -> str | None:
    """
    1) Crée un Google Sheet AVEC deux onglets nommés "Itinerary" et "Weather"
    2) Copie le contenu du XLSX dans ces onglets
    3) Partage la feuille avec l’e-mail `share_with`
    Retourne l’URL web du Google Sheet ou None si échec / non configuré.
    """
    sa_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not sa_file or not os.path.exists(sa_file):
        return None

    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = Credentials.from_service_account_file(sa_file, scopes=scopes)

    try:
        # 1) Création du Google Sheet avec 2 onglets
        sheets_service = build("sheets", "v4", credentials=creds)
        spreadsheet_body = {
            "properties": {"title": os.path.splitext(os.path.basename(xlsx_path))[0]},
            "sheets": [
                {"properties": {"title": "Itinerary"}},
                {"properties": {"title": "Weather"}},
            ],
        }
        spreadsheet = sheets_service.spreadsheets().create(
            body=spreadsheet_body, fields="spreadsheetId"
        ).execute()
        sheet_id: str = spreadsheet["spreadsheetId"]
        web_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"

        # 2) Charger le XLSX
        xls = pd.ExcelFile(xlsx_path)
        for sheet_name in ["Itinerary", "Weather"]:
            if sheet_name not in xls.sheet_names:
                continue
            df = xls.parse(sheet_name)
            values = [df.columns.tolist()] + df.values.tolist()

            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": values},
            ).execute()

        # 3) Partage avec l’utilisateur
        drive_service = build("drive", "v3", credentials=creds)
        drive_service.permissions().create(
            fileId=sheet_id,
            body={"type": "user", "role": "writer", "emailAddress": share_with},
            sendNotificationEmail=True,
        ).execute()

        return web_url

    except HttpError:
        return None


def generate_workbook(itin: dict, hotel: dict, traveller_email: str) -> dict:
    """
    Construit en local un XLSX avec deux onglets (Itinerary, Weather),
    puis tente de l’uploader dans Google Sheets si possible.
    Renvoie {"local_file": <chemin>, "gsheet_url": <URL ou None>}.
    """
    tmp_dir = tempfile.gettempdir()
    first_day = itin["days"][0]["date"]
    base_name = f"itinerary_{first_day}_{traveller_email.split('@')[0]}"
    xlsx_path = os.path.join(tmp_dir, f"{base_name}.xlsx")

    df_days = pd.DataFrame(itin["days"])
    df_weather = pd.DataFrame(itin["meteo"])

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df_days.to_excel(writer, sheet_name="Itinerary", index=False)
        df_weather.to_excel(writer, sheet_name="Weather", index=False)

    gsheet_url = _create_gsheet_with_tabs(xlsx_path, traveller_email)
    return {"local_file": xlsx_path, "gsheet_url": gsheet_url}

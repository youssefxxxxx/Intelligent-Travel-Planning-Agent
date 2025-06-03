# services/weather.py

import os
import datetime
import requests
from core.models import WeatherSlice

_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"
_API_KEY = os.getenv("OW_API_KEY")

def fetch_weather(city: str, start: datetime.date, end: datetime.date, lang="fr") -> list[WeatherSlice]:
    """
    Récupère la météo en mode prévision 5 jours / 3h de OpenWeather
    et regroupe en tranches journalières.
    """
    params = {
        "q": city,
        "units": "metric",
        "appid": _API_KEY,
        "lang": lang
    }
    resp = requests.get(_BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    items = resp.json()["list"]

    # Regrouper chaque créneau par date
    acc: dict[datetime.date, list] = {}
    for slot in items:
        ts = datetime.datetime.fromtimestamp(slot["dt"])
        d = ts.date()
        if start <= d <= end:
            acc.setdefault(d, []).append(slot)

    slices: list[WeatherSlice] = []
    for d, lst in acc.items():
        temps = [v["main"]["temp"] for v in lst]
        pivot = max(lst, key=lambda v: v["pop"])  # on prend l’état météo le plus « pluvieux » comme représentant
        slices.append(
            WeatherSlice(
                date=d,
                temp_min=round(min(temps)),
                temp_max=round(max(temps)),
                description=pivot["weather"][0]["description"],
                icon=pivot["weather"][0]["icon"],
            )
        )
    return sorted(slices, key=lambda w: w.date)

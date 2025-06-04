import os, datetime as dt, requests
from core.models import WeatherSlice

_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"


def fetch_weather(city: str,
                  start: dt.date,
                  end: dt.date,
                  lang: str = "fr") -> list[WeatherSlice]:
    api_key = os.getenv("OW_API_KEY")
    if not api_key:
        raise RuntimeError("OW_API_KEY manquante ou vide.")

    params = {
        "q": city,
        "units": "metric",
        "appid": api_key,
        "lang": lang,
    }
    r = requests.get(_BASE_URL, params=params, timeout=10)
    r.raise_for_status()
    slots = r.json()["list"]

    # Regrouper par jour
    buckets: dict[dt.date, list] = {}
    for s in slots:
        d = dt.datetime.fromtimestamp(s["dt"]).date()
        if start <= d <= end:
            buckets.setdefault(d, []).append(s)

    slices: list[WeatherSlice] = []
    for day, lst in buckets.items():
        temps = [v["main"]["temp"] for v in lst]
        pivot = max(lst, key=lambda v: v["pop"])  # créneau le + pluvieux
        slices.append(
            WeatherSlice(
                date=day,
                temp_min=round(min(temps)),
                temp_max=round(max(temps)),
                description=pivot["weather"][0]["description"],
                icon=pivot["weather"][0]["icon"],
            )
        )
    return sorted(slices, key=lambda w: w.date)

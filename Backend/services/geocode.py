# services/geocode.py

import requests

def city_to_coords(city_name: str) -> tuple[float, float]:
    """
    Convertit un nom de ville en (latitude, longitude) en interrogeant
    directement l’API Nominatim d’OpenStreetMap.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": city_name,
        "format": "json",
        "limit": 1
    }
    # Nominatim exige un User-Agent explicite
    headers = {
        "User-Agent": "travel-agent-app/1.0 (contact@example.com)"
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    r.raise_for_status()
    results = r.json()
    if not results:
        raise RuntimeError(f"Impossible de géocoder la ville « {city_name} ».")
    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    return (lat, lon)

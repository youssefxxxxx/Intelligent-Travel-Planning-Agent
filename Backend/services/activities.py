# services/activities.py

def fetch_activities(city: str) -> list[dict]:
    """
    Retourne une liste d'activités factices pour la démonstration.
    À remplacer plus tard par l'intégration TripAdvisor/Viator.
    """
    return [
        {"name": "Visite guidée de la Sagrada Família", "price": 32, "duration_h": 2},
        {"name": "Tapas & Flamenco Night", "price": 45, "duration_h": 3},
    ]

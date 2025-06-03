# services/flights.py

from core.models import TripRequest

def fetch_flights(req: TripRequest) -> list[dict]:
    """
    Stub MVP : retourne une liste de vols factices.
    À remplacer plus tard par l’intégration Skyscanner/Amadeus.
    """
    return [
        {
            "carrier": "Vueling",
            "flight_no": "VY8001",
            "price": 79,
            "depart": f"{req.start} 07:05",
            "arrive": f"{req.start} 08:50",
        }
    ]

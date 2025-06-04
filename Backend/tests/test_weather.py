# tests/test_weather.py

import datetime
import os
import pytest
from services.weather import fetch_weather

@pytest.mark.skipif(not os.getenv("OW_API_KEY"), reason="OW_API_KEY absent : test sauté")
def test_fetch_weather():
    """
    Test basique pour s'assurer que fetch_weather renvoie une liste de WeatherSlice.
    Si OW_API_KEY n'existe pas, on skip le test.
    """
    today = datetime.date.today()
    lst = fetch_weather("Barcelona,ES", today, today)
    assert isinstance(lst, list)
    assert all(hasattr(item, "temp_min") and hasattr(item, "description") for item in lst)

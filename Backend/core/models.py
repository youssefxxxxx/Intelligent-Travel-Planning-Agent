# core/models.py

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

@dataclass
class TripRequest:
    city: str
    origin: str
    start: date
    end: date
    budget: float
    email: str

@dataclass
class WeatherSlice:
    date: date
    temp_min: int
    temp_max: int
    description: str
    icon: str

@dataclass
class ItineraryDay:
    date: date
    morning: str
    afternoon: str
    evening: str
    weather: Optional[WeatherSlice] = None

@dataclass
class Itinerary:
    days: List[ItineraryDay] = field(default_factory=list)
    total_cost: float = 0.0
    chain_of_thought: str = ""

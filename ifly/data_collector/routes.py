# Defines the origin and destination tuples for daily monitoring

from itertools import product

CONTINENTS = {
    "asia": ["SIN", "HKG", "NRT"],
    "europe": ["LHR", "FRA", "CDG"],
    "north_america": ["JFK", "LAX", "ORD"],
    "middle_east": ["DXB", "DOH"],
    "oceania": ["SYD"]
}

DATE_OFFSETS = [7, 14, 30, 45, 60]

ALLOWED_PAIRS = [
    ("asia", "europe"),
    ("asia", "north_america"),
    ("europe", "north_america"),
    ("asia", "oceania"),
    ("europe", "middle_east"),
    ("north_america", "middle_east"),
]

def generate_routes():
    routes = []
    for c1, c2 in ALLOWED_PAIRS:
        for a, b in product(CONTINENTS[c1], CONTINENTS[c2]):
            routes.append((a, b))
            routes.append((b, a))
    return routes

ROUTES = generate_routes()

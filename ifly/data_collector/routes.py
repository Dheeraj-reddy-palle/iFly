# Defines the origin and destination tuples for daily monitoring

from itertools import product

# Define neutral global hub airports by continent
CONTINENTS = {
    "asia": ["SIN", "HKG", "NRT", "ICN"],
    "europe": ["LHR", "FRA", "CDG", "AMS"],
    "north_america": ["JFK", "LAX", "ORD", "YYZ"],
    "middle_east": ["DXB", "DOH", "AUH"],
    "oceania": ["SYD", "MEL"]
}

# Future departure offsets in days
DATE_OFFSETS = [7, 14, 30, 45, 60]

# Allowed cross-continent pairings (prevents regional bias)
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
            routes.append((b, a))  # bidirectional

    return routes

ROUTES = generate_routes()

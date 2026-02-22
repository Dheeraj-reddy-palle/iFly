# Curated top 50 routes for quota-efficient collection
# Mix: domestic India (20), transatlantic (10), intra-Asia (10), Middle East (5), misc (5)

DATE_OFFSETS = [14, 45]  # Reduced from [7,30,60] to save API quota

# Each tuple: (origin, destination)
ROUTES = [
    # === Domestic India (20 routes) ===
    ("DEL", "BOM"), ("BOM", "DEL"),
    ("DEL", "BLR"), ("BLR", "DEL"),
    ("BOM", "BLR"), ("BLR", "BOM"),
    ("DEL", "HYD"), ("HYD", "DEL"),
    ("DEL", "CCU"), ("CCU", "DEL"),
    ("BOM", "GOI"), ("GOI", "BOM"),
    ("BLR", "HYD"), ("HYD", "BLR"),
    ("DEL", "MAA"), ("MAA", "DEL"),
    ("BOM", "CCU"), ("CCU", "BOM"),
    ("BLR", "CCU"), ("CCU", "BLR"),

    # === Transatlantic (10 routes) ===
    ("JFK", "LHR"), ("LHR", "JFK"),
    ("JFK", "CDG"), ("CDG", "JFK"),
    ("LAX", "LHR"), ("LHR", "LAX"),
    ("ORD", "FRA"), ("FRA", "ORD"),
    ("JFK", "FRA"), ("FRA", "JFK"),

    # === Intra-Asia (10 routes) ===
    ("SIN", "NRT"), ("NRT", "SIN"),
    ("SIN", "HKG"), ("HKG", "SIN"),
    ("DEL", "SIN"), ("SIN", "DEL"),
    ("BOM", "SIN"), ("SIN", "BOM"),
    ("HKG", "NRT"), ("NRT", "HKG"),

    # === Middle East Hub (5 routes) ===
    ("DXB", "LHR"), ("LHR", "DXB"),
    ("DXB", "BOM"), ("BOM", "DXB"),
    ("DOH", "LHR"),

    # === Cross-Continental (5 routes) ===
    ("SIN", "LHR"), ("LHR", "SIN"),
    ("SYD", "SIN"), ("SIN", "SYD"),
    ("DEL", "JFK"),
]

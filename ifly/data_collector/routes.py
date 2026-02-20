# Defines the origin and destination tuples for daily monitoring

ROUTES = [
    # Major Domestic Hubs (India)
    ("DEL", "BOM"), ("BOM", "DEL"),
    ("DEL", "BLR"), ("BLR", "DEL"),
    ("DEL", "CCU"), ("CCU", "DEL"),
    ("BOM", "BLR"), ("BLR", "BOM"),
    ("DEL", "HYD"), ("HYD", "DEL"),
    ("DEL", "MAA"), ("MAA", "DEL"),
    ("BOM", "HYD"), ("HYD", "BOM"),
    ("BOM", "CCU"), ("CCU", "BOM"),
    ("BLR", "HYD"), ("HYD", "BLR"),
    ("MAA", "BLR"), ("BLR", "MAA"),
    
    # Tier 2 Connects (India)
    ("DEL", "PNQ"), ("PNQ", "DEL"),
    ("DEL", "GOI"), ("GOI", "DEL"),
    ("BOM", "GOI"), ("GOI", "BOM"),
    ("BLR", "PNQ"), ("PNQ", "BLR"),
    ("DEL", "ATQ"), ("DEL", "SXR"),
    
    # Major International Connectivity
    ("DEL", "LHR"), ("BOM", "LHR"),  # London
    ("DEL", "JFK"), ("BOM", "JFK"),  # New York
    ("DEL", "DXB"), ("BOM", "DXB"),  # Dubai
    ("DEL", "SIN"), ("BOM", "SIN"),  # Singapore
    ("DEL", "BKK"), ("BOM", "BKK"),  # Bangkok
    ("DEL", "CDG"), ("BOM", "CDG"),  # Paris
    ("DEL", "SYD"), ("BOM", "SYD"),  # Sydney
    ("DEL", "YYZ"), ("BOM", "YYZ"),  # Toronto
    ("BLR", "LHR"), ("BLR", "DXB"),
    ("HYD", "DXB"), ("MAA", "DXB")
]

# Forecast window gaps explicitly (in days)
# 7 = Next week
# 14 = 2 weeks out
# 30 = Next month 
# 45 = Target medium booking
# 60 = Advance planning tracking
DATE_OFFSETS = [7, 14, 30, 45, 60]

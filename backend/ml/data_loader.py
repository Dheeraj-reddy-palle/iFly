import os
import sys
import pandas as pd
import numpy as np
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

# Setup explicit path reference for Python imports to hit the root namespace correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.airport import Airport
from app.models.flight_offer import FlightOffer


def compute_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0  # Earth radius in kilometers
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c


def load_airports(db):
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "data", "airports.csv")
        df = pd.read_csv(csv_path)
        records = df.to_dict(orient="records")

        stmt = insert(Airport).values(records)
        stmt = stmt.on_conflict_do_update(
            index_elements=["iata_code"],
            set_={
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "country": stmt.excluded.country
            }
        )
        db.execute(stmt)
        db.commit()
        print(f"[INFO] Successfully upserted {len(records)} airports via bulk insert.")
    except Exception as e:
        print(f"[ERROR] Failed to load airports: {e}")
        db.rollback()


def backfill_distances(db):
    print("[INFO] Fetching airports for mapping...")
    airports = {a.iata_code: (a.latitude, a.longitude) for a in db.query(Airport).all()}

    print("[INFO] Scanning for missing distance_km data...")
    missing_offers = db.query(FlightOffer.id, FlightOffer.origin, FlightOffer.destination).filter(FlightOffer.distance_km == None).all()

    total = len(missing_offers)
    print(f"[INFO] Found {total} records requiring distance backfill.")

    if total == 0:
        return

    mappings = []
    for row in missing_offers:
        o_iata = row.origin
        d_iata = row.destination

        if o_iata in airports and d_iata in airports:
            o_lat, o_lon = airports[o_iata]
            d_lat, d_lon = airports[d_iata]
            dist = float(compute_haversine_distance(o_lat, o_lon, d_lat, d_lon))
            mappings.append((row.id, dist))

    if mappings:
        print(f"[INFO] Uploading {len(mappings)} natively mapped rows via high-performance chunked VALUES clause...")
        chunk_size = 5000
        for i in range(0, len(mappings), chunk_size):
            chunk = mappings[i:i + chunk_size]
            values_str = ", ".join([f"({id_val}, {dist_val})" for id_val, dist_val in chunk])
            query = f"UPDATE flight_offers SET distance_km = v.dist FROM (VALUES {values_str}) AS v(id, dist) WHERE flight_offers.id = v.id;"
            db.execute(text(query))
            db.commit()
            print(f"[INFO] Checkpoint: Backfilled {min(i + chunk_size, len(mappings))}/{total} rows...")

    print(f"[SUCCESS] Complete. Backfilled {len(mappings)} total rows natively.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        load_airports(db)
        backfill_distances(db)
    finally:
        db.close()

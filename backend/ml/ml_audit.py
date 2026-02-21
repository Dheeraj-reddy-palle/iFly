import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from ml.feature_engineering import prepare_ml_pipeline, load_data, engineer_base_features, apply_frequency_encoding

def format_fail(msg):
    return f"[FAIL] {msg}"

def format_pass(msg):
    return f"[PASS] {msg}"

def run_audit():
    print("=== STRICT ML TECHNICAL AUDIT ===\n")
    db = SessionLocal()
    
    try:
        df_raw = load_data(db)
        if len(df_raw) == 0:
            print("No data loaded.")
            return

        # 3) Duration Parsing Robustness
        print("--- 3) Duration Parsing Robustness ---")
        from ml.feature_engineering import extract_duration_minutes
        durations = ["PT45M", "PT3H", "PT2H15M", "PT0H50M", "PT12H5M"]
        expected = [45, 180, 135, 50, 725]
        parsed = [extract_duration_minutes(d) for d in durations]
        if parsed == expected:
            print(format_pass("Duration parsing correctly handles complex ISO formats."))
        else:
            print(format_fail(f"Duration parsing failed. Expected {expected}, got {parsed}"))
            
        # 4) Distance Integrity
        print("\n--- 4) Distance Integrity ---")
        null_dists = df_raw['distance_km'].isnull().sum()
        if null_dists == 0:
            print(format_pass("distance_km has no NULL values."))
        else:
            print(format_fail(f"distance_km has {null_dists} NULL values."))
            
        from ml.data_loader import compute_haversine_distance
        # LHR (51.47, -0.45) to JFK (40.64, -73.78) is approx 5540 km.
        dist = compute_haversine_distance(51.47, -0.45, 40.64, -73.78)
        if 5400 < dist < 5700:
            print(format_pass(f"Haversine formula uses correct earth radius (computed LHR-JFK ~ {dist:.0f} km)"))
        else:
            print(format_fail(f"Haversine formula anomalous. LHR-JFK distance: {dist}"))

        # Feature Sanity & Data Leakage Review
        df_eng = engineer_base_features(df_raw.copy())
        
        # 5) Feature Sanity
        print("\n--- 5) Feature Sanity ---")
        airline_card = df_eng['airline'].nunique()
        route_card = df_eng['route_key'].nunique()
        print(f"Cardinality - airline: {airline_card}, route_key: {route_card}")
        if airline_card > 1000 or route_card > 10000:
            print(format_fail("High cardinality detected potentially impacting frequency mapping."))
        else:
            print(format_pass("Cardinality metrics are within reasonable limits. No one-hot explosion possible with current setup."))

        # Re-run pipeline to check 6) Model Stability & 2) Isolation
        print("\n--- 6) Model Stability & 2) Train/Test Isolation ---")
        features_to_keep = ['distance_km', 'stops', 'month', 'weekday', 'departure_hour_bucket', 'duration_minutes', 'airline_freq', 'route_key_freq']
        
        # Split natively
        train_df, test_df = train_test_split(df_eng, test_size=0.2, random_state=42)
        train_df, test_df = apply_frequency_encoding(train_df, test_df, ['airline', 'route_key'])
        
        X_train, y_train = train_df[features_to_keep], train_df['price']
        X_test, y_test = test_df[features_to_keep], test_df['price']

        model = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)
        
        y_train_pred = model.predict(X_train)
        y_test_pred = model.predict(X_test)
        
        train_r2 = r2_score(y_train, y_train_pred)
        test_r2 = r2_score(y_test, y_test_pred)
        test_mae = mean_absolute_error(y_test, y_test_pred)
        
        print(f"Train R²: {train_r2:.4f}")
        print(f"Test R²:  {test_r2:.4f}")
        print(f"Test MAE: {test_mae:.2f}")
        
        if train_r2 - test_r2 > 0.15:
            print(format_fail("Severe overfitting detected. Model stability compromised."))
        else:
            print(format_pass("Model exhibits stable generalization without extreme train-test gap."))
            
        # Run second instance
        model2 = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42, n_jobs=-1)
        model2.fit(X_train, y_train)
        y_p2 = model2.predict(X_test)
        if np.allclose(y_test_pred, y_p2):
            print(format_pass("Training runs are deterministic with fixed random_state."))
        else:
            print(format_fail("Training runs are non-deterministic."))

        # 7) Residual Analysis
        print("\n--- 7) Residual Analysis ---")
        residuals = y_test - y_test_pred
        mean_res = np.mean(residuals)
        std_res = np.std(residuals)
        print(f"Residual Mean: {mean_res:.4f}, Std: {std_res:.4f}")
        
        corr_dist_res = np.corrcoef(X_test['distance_km'], np.abs(residuals))[0, 1]
        print(f"Correlation between distance and absolute error (Heteroscedasticity): {corr_dist_res:.4f}")
        if corr_dist_res > 0.2:
            print(format_fail("High positive correlation detected. Variance in error grows with distance (Heteroscedasticity present)."))
        else:
            print(format_pass("No severe heteroscedasticity linearly tied to distance."))

        # 1) Data Leakage Audit
        print("\n--- 1) Data Leakage Audit (Analysis) ---")
        if "future_data" in df_eng.columns: # Placeholder for actual time split check
             pass
        else:
            print("Note: Train/Test split is currently fully RANDOM.")
            print("Since 'scraped_at' or 'departure_date' evolves dynamically, a random split mixes future timeline pricing knowledge into the training set predicting the past.")
            print(format_fail("Random split violates strict temporal isolation (Time Leakage)."))
            
        print("\n--- 8) Realism Check ---")
        print("R² of ~0.85 is highly optimistic for flight prices tracking solely basic distance/duration/category frequencies without exact advanced pricing buckets (advanced purchase days, specific availability tiers).")
        print("The primary leakage vector here is temporal shuffling: flights parsed on the same day for the exact same route with near-identical constraints leak directly across the random split barrier, artificially inflating metrics.")

    finally:
        db.close()

if __name__ == "__main__":
    run_audit()

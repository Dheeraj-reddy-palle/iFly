import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
import os

def load_data(db: Session) -> pd.DataFrame:
    query_str = """
    SELECT
        *,
        (origin || '-' || destination) AS route_key,
        (airline || '-' || origin || '-' || destination) AS airline_route,
        
        COALESCE(AVG(price) OVER (
            PARTITION BY origin, destination
            ORDER BY created_at
            ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
        ), 0.0) AS route_rolling_mean_30d,
        
        COALESCE(STDDEV(price) OVER (
            PARTITION BY origin, destination
            ORDER BY created_at
            ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
        ), 1.0) AS route_rolling_std_30d,
        
        COALESCE(AVG(price) OVER (
            PARTITION BY airline, origin, destination
            ORDER BY created_at
            ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
        ), 0.0) AS airline_route_mean_price,
        
        COUNT(*) OVER (
            PARTITION BY origin, destination
            ORDER BY created_at
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS route_offer_count_7d,
        
        COALESCE(AVG(price) OVER (
            PARTITION BY origin, destination
            ORDER BY created_at
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ), 0.0) AS route_mean_7d,
        
        COALESCE(AVG(price) OVER (
            PARTITION BY airline, origin, destination
            ORDER BY created_at
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ), 0.0) AS airline_route_mean_7d,
        
        COALESCE(STDDEV(price) OVER (
            PARTITION BY airline, origin, destination
            ORDER BY created_at
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ), 1e-6) AS airline_route_volatility_7d,
        
        COUNT(*) OVER (
            PARTITION BY airline, origin, destination
            ORDER BY created_at
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS airline_route_offer_count_7d
        
    FROM flight_offers
    WHERE distance_km IS NOT NULL
    ORDER BY created_at ASC
    """
    df = pd.read_sql(query_str, con=db.connection().connection)
    
    # Generate derived ratio features securely vectorized via pandas directly
    df['route_price_momentum'] = np.where(
        df['route_rolling_mean_30d'] > 0, 
        df['route_mean_7d'] / df['route_rolling_mean_30d'], 
        1.0
    )
    
    df['route_volatility_index'] = np.where(
        df['route_rolling_mean_30d'] > 0,
        df['route_rolling_std_30d'] / df['route_rolling_mean_30d'],
        1e-6
    )
    
    df['airline_price_relative_to_route_mean'] = np.where(
        df['route_mean_7d'] > 0,
        df['airline_route_mean_7d'] / df['route_mean_7d'],
        1.0
    )
    
    df['airline_route_mean_7d'] = np.where(df['airline_route_mean_7d'] == 0.0, df['route_rolling_mean_30d'], df['airline_route_mean_7d'])
    df['route_mean_7d'] = np.where(df['route_mean_7d'] == 0.0, df['route_rolling_mean_30d'], df['route_mean_7d'])
    
    return df

def extract_duration_minutes(duration_str) -> int:
    import re
    duration_str = str(duration_str).replace('PT', '')
    hours, minutes = 0, 0
    h_match = re.search(r'(\d+)H', duration_str)
    if h_match: hours = int(h_match.group(1))
    m_match = re.search(r'(\d+)M', duration_str)
    if m_match: minutes = int(m_match.group(1))
    return (hours * 60) + minutes

def map_hour_to_bucket(hour: int) -> int:
    if 5 <= hour <= 11: return 0
    elif 12 <= hour <= 16: return 1
    elif 17 <= hour <= 21: return 2
    else: return 3

def engineer_base_features(df: pd.DataFrame) -> pd.DataFrame:
    df['departure_date'] = pd.to_datetime(df['departure_date'], utc=True)
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    
    df['month'] = df['departure_date'].dt.month
    df['weekday'] = df['departure_date'].dt.weekday
    
    df['departure_time'] = pd.to_datetime(df['departure_time'])
    df['departure_hour_bucket'] = df['departure_time'].dt.hour.apply(map_hour_to_bucket)
    
    df['duration_minutes'] = df['duration'].apply(extract_duration_minutes)
    
    df['days_until_departure'] = (df['departure_date'] - df['created_at']).dt.days
    df['days_until_departure'] = df['days_until_departure'].clip(lower=0)
    
    return df

def apply_frequency_encoding(train_df: pd.DataFrame, test_df: pd.DataFrame, columns: list):
    for col in columns:
        freq_map = train_df[col].value_counts(normalize=True).to_dict()
        train_df[f"{col}_freq"] = train_df[col].map(freq_map)
        test_df[f"{col}_freq"] = test_df[col].map(lambda x: freq_map.get(x, 0))
    return train_df, test_df

def prepare_ml_data(db: Session):
    df = load_data(db)
    if len(df) == 0:
        raise ValueError("Database contains no actionable flight_offers with distance_km filled.")
        
    df = engineer_base_features(df)
    
    # Strictly define columns used going into the tree native
    features_to_keep = [
        'distance_km', 'stops', 'month', 'weekday', 
        'departure_hour_bucket', 'duration_minutes', 
        'days_until_departure', 'route_rolling_mean_30d',
        'route_rolling_std_30d', 'airline_route_mean_price',
        'route_offer_count_7d', 'route_mean_7d', 
        'route_price_momentum', 'route_volatility_index',
        'airline_route_mean_7d', 'airline_route_volatility_7d',
        'airline_route_offer_count_7d', 'airline_price_relative_to_route_mean',
        'airline_freq', 'route_key_freq'
    ]
    
    # Chronological Split strictly precedes rolling mapping constraints
    df = df.sort_values(by='created_at', ascending=True).reset_index(drop=True)
    return df, features_to_keep

def generate_fold_features(train_df: pd.DataFrame, test_df: pd.DataFrame, features_to_keep: list):
    # Vectorized SQL Windows have inherently solved chronological extraction natively
    
    # Safe fallback initialization bounds preventing 0.0 tree biases
    first_price = train_df['price'].iloc[0] if len(train_df) > 0 else 0.0
    train_df['route_rolling_mean_30d'] = train_df['route_rolling_mean_30d'].replace(0.0, first_price)
    train_df['airline_route_mean_price'] = train_df['airline_route_mean_price'].replace(0.0, first_price)
    test_df['route_rolling_mean_30d'] = test_df['route_rolling_mean_30d'].replace(0.0, first_price)
    test_df['airline_route_mean_price'] = test_df['airline_route_mean_price'].replace(0.0, first_price)
    
    train_df, test_df = apply_frequency_encoding(train_df, test_df, ['airline', 'route_key'])
    
    X_train = train_df[features_to_keep]
    y_train = train_df['price']
    
    X_test = test_df[features_to_keep]
    y_test = test_df['price']
    
    return X_train, X_test, y_train, y_test, features_to_keep

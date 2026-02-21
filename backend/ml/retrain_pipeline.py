import os
import joblib
import logging
from datetime import datetime
from sqlalchemy import text
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import root_mean_squared_error, mean_absolute_error, r2_score
from sklearn.inspection import permutation_importance
import pandas as pd
import numpy as np

from app.database import SessionLocal
from app.models.model_registry import ModelRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("RetrainPipeline")

MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)


def train_and_evaluate(df: pd.DataFrame, features: list):
    if df.empty or len(df) < 50:
        logger.error("Insufficient data to train model.")
        return None, None, None, None
        
    logger.info(f"Training on {len(df)} records.")
    
    # Chronological Split (Strictly Required)
    df = df.sort_values('created_at').reset_index(drop=True)
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    # Generate Stateful Features after splitting to avoid leakage
    from ml.feature_engineering import generate_fold_features
    X_train, X_test, y_train, y_test, _ = generate_fold_features(train_df, test_df, features)
    
    numeric_features = ['days_to_departure', 'route_mean_7d', 'airline_route_mean_7d', 'airline_price_relative_to_route_mean', 'route_volatility_7d']
    numeric_features = [f for f in numeric_features if f in features]
    categorical_features = ['origin', 'destination', 'airline']
    categorical_features = [f for f in categorical_features if f in features]

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
        ])

    model = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))
    ])
    
    model.fit(X_train, y_train)
    
    # Predictions
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    
    # Metrics
    metrics = {
        'train_r2': r2_score(y_train, y_train_pred),
        'test_r2': r2_score(y_test, y_test_pred),
        'test_mae': mean_absolute_error(y_test, y_test_pred),
        'test_rmse': root_mean_squared_error(y_test, y_test_pred)
    }
    
    # Permutation Test (Data Leakage Guard)
    logger.info("Running permutation test guard rail...")
    # Shuffle all features to see if model secretly depends on row-order index leakage
    X_test_permuted = X_test.dropna().copy()
    for col in X_test_permuted.columns:
        X_test_permuted[col] = np.random.permutation(X_test_permuted[col].values)
        
    y_perm_pred = model.predict(X_test_permuted)
    perm_r2 = r2_score(y_test.dropna(), y_perm_pred)
    
    logger.info(f"Permuted R2 score: {perm_r2:.4f}")
    if perm_r2 > 0.05:
        logger.critical(f"CRITICAL: Permutation test FAILED! (R2: {perm_r2:.4f} > 0.05). Potential data leakage detected.")
        metrics['leakage_detected'] = True
    else:
        metrics['leakage_detected'] = False
        
    return model, metrics, X_test, y_test

def check_deployment_gate(db, new_model, new_metrics: dict, X_test: pd.DataFrame, y_test: pd.Series) -> tuple[bool, ModelRegistry, dict]:
    logger.info("Checking performance comparison gate...")
    
    deployed_model = db.query(ModelRegistry).filter(ModelRegistry.deployed == True).first()
    
    if not deployed_model:
        logger.info("No deployed model found. Automatic deployment approved.")
        return True, None, {}
        
    old_model_path = deployed_model.file_path
    if not os.path.exists(old_model_path):
        logger.warning(f"Deployed model file missing at {old_model_path}. Auto-deploying new.")
        return True, deployed_model, {}

    try:
        old_model = joblib.load(old_model_path)
        y_old_pred = old_model.predict(X_test)
        
        old_test_r2 = r2_score(y_test, y_old_pred)
        old_test_mae = mean_absolute_error(y_test, y_old_pred)
        
    except Exception as e:
        logger.error(f"Failed to load or evaluate old model: {e}. Rejecting deployment to be safe.")
        return False, deployed_model, {}
        
    logger.info(f"Current deployed (v={deployed_model.model_version}) R2 on new slice:  {old_test_r2:.4f} | MAE: {old_test_mae:.4f}")
    logger.info(f"Candidate     R2 on new slice:  {new_metrics['test_r2']:.4f} | MAE: {new_metrics['test_mae']:.4f}")
    
    # Strict Improvement Gate rules
    r2_improved = new_metrics['test_r2'] > old_test_r2
    mae_improved = new_metrics['test_mae'] < old_test_mae
    
    comparison_metadata = {
        'compared_against_version': deployed_model.model_version,
        'compared_on_timestamp': datetime.now()
    }

    if r2_improved and mae_improved:
        logger.info("Deployment approved. Model strictly outperforms deployed version on recent holdout.")
        return True, deployed_model, comparison_metadata
    else:
        logger.warning("Candidate model underperforms or tied on recent holdout. Deployment rejected.")
        return False, deployed_model, comparison_metadata

def run_pipeline():
    timestamp_str = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    version = f"v{timestamp_str}"
    file_path = os.path.join(MODEL_DIR, f"flight_price_model_{version}.pkl")
    
    db = SessionLocal()
    try:
        # Load & Feature Engineer
        from ml.feature_engineering import prepare_ml_data
        df_featured, features = prepare_ml_data(db)
        
        # Train
        model, metrics, X_test, y_test = train_and_evaluate(df_featured, features)
        if not model:
            return
            
        logger.info(f"Metrics: R2={metrics['test_r2']:.4f}, MAE={metrics['test_mae']:.4f}, RMSE={metrics['test_rmse']:.4f}")
        
        # Check Leakage
        should_deploy = False
        old_deployed = None
        is_candidate = True
        comparison_metadata = {}
        
        if metrics['leakage_detected']:
            logger.critical("Aborting deployment due to data leakage.")
            should_deploy = False
        else:
            should_deploy, old_deployed, comparison_metadata = check_deployment_gate(db, model, metrics, X_test, y_test)
            if should_deploy:
                is_candidate = False
                
        # Save File
        logger.info(f"Saving model to {file_path}")
        try:
            joblib.dump(model, file_path)
        except Exception as e:
            logger.error(f"Failed to save model file: {e}. Aborting database insert.")
            return

        # Update DB State
        if should_deploy and old_deployed:
            old_deployed.deployed = False
            db.add(old_deployed)
            
        new_registry = ModelRegistry(
            model_version=version,
            trained_at=datetime.now(),
            train_r2=metrics['train_r2'],
            test_r2=metrics['test_r2'],
            test_mae=metrics['test_mae'],
            test_rmse=metrics['test_rmse'],
            deployed=should_deploy,
            file_path=file_path,
            is_candidate=is_candidate,
            compared_against_version=comparison_metadata.get('compared_against_version'),
            compared_on_timestamp=comparison_metadata.get('compared_on_timestamp')
        )
        db.add(new_registry)
        db.commit()
        
        logger.info(f"Weekly Retrain complete for {version}. Deployed: {should_deploy}")
        
    except Exception as e:
        logger.error(f"Retrain pipeline crashed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()

import sys
import os
import json
import joblib
import logging
from datetime import datetime
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TrainPipeline")

from app.database import SessionLocal
from ml.feature_engineering import prepare_ml_data, generate_fold_features

def main():
    logger.info("Initiating Phase 3 ML Model Pipeline (Walk-Forward Validation)...")
    
    db = SessionLocal()
    try:
        df, features = prepare_ml_data(db)
        logger.info(f"Pipeline prepared. Total dataset size: {len(df)}")
        logger.info(f"Features mapped: {features}")
        
        import pandas as pd
        min_date = df['created_at'].min()
        max_date = df['created_at'].max()
        
        total_days = (max_date - min_date).days
        train_days = min(90, max(7, total_days // 2))
        test_days = min(14, max(2, total_days // 5))
        
        current_start = min_date
        folds = []
        
        # Rigorous rolling training bounds mapping onto a sliding test chunk seamlessly simulating deployed retraining arrays.
        while True:
            train_end = current_start + pd.Timedelta(days=train_days)
            test_end = train_end + pd.Timedelta(days=test_days)
            
            if train_end >= max_date:
                break
                
            train_raw = df[(df['created_at'] >= current_start) & (df['created_at'] < train_end)].copy()
            test_raw = df[(df['created_at'] >= train_end) & (df['created_at'] < test_end)].copy()
            
            if len(train_raw) > 10 and len(test_raw) > 2: # ensure viable sample
                folds.append((train_raw, test_raw))
                
            current_start += pd.Timedelta(days=test_days)
            
        logger.info(f"Rolling Windows Validated: {len(folds)} strict {train_days}->{test_days} day blocks.")
        
        if len(folds) == 0:
            logger.warning("Dataset temporal span too small for rolling. Falling back to single timeline split.")
            split_idx = int(len(df) * 0.8)
            folds = [(df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy())]

        fold_metrics = []
        
        for idx, (train_raw, test_raw) in enumerate(folds):
            fold_num = idx + 1
            logger.info(f"Fold {fold_num}: Extracting chronological state features (Train: {len(train_raw)}, Test: {len(test_raw)})...")
            X_train, X_test, y_train, y_test, _ = generate_fold_features(train_raw, test_raw, features)
            
            model = XGBRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=6,
                random_state=42,
                n_jobs=-1
            )
            
            y_train_log = np.log1p(y_train)
            model.fit(X_train, y_train_log)
            
            train_preds = np.expm1(model.predict(X_train))
            test_preds = np.expm1(model.predict(X_test))
            
            train_r2 = float(r2_score(y_train, train_preds))
            test_r2 = float(r2_score(y_test, test_preds))
            train_mae = float(mean_absolute_error(y_train, train_preds))
            test_mae = float(mean_absolute_error(y_test, test_preds))
            test_rmse = float(np.sqrt(mean_squared_error(y_test, test_preds)))
            
            logger.info(f"  Train R²: {train_r2:.4f} | Test R²: {test_r2:.4f}")
            logger.info(f"  Train MAE: {train_mae:.2f} | Test MAE: {test_mae:.2f} | Test RMSE: {test_rmse:.2f}")
            
            fold_metrics.append({
                'fold': fold_num,
                'train_r2': train_r2,
                'test_r2': test_r2,
                'train_mae': train_mae,
                'test_mae': test_mae,
                'test_rmse': test_rmse
            })
            
            if fold_num == 1:
                logger.info("Running Correlation Sanity Test (Fold 1)...")
                try:
                    features_to_check = ['airline_route_mean_7d', 'route_mean_7d', 'airline_price_relative_to_route_mean']
                    corr_df = pd.DataFrame(X_train, columns=features)[features_to_check]
                    corr_matrix = corr_df.corr()
                    logger.debug(f"Correlation matrix:\n{corr_matrix}")
                    corr_val = corr_matrix.loc['airline_route_mean_7d', 'route_mean_7d']
                    if abs(corr_val) > 0.85:
                        logger.warning(f"High correlation ({corr_val:.4f} > 0.85) detected between airline_route_mean_7d and route_mean_7d.")
                except Exception as e:
                    logger.warning(f"Could not compute correlation matrix: {e}")

                logger.info("Running Permutation Sanity Test (Fold 1)...")
                np.random.seed(999)
                y_train_shuffled = np.random.permutation(y_train_log)
                model_perm = XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=6, random_state=42, n_jobs=-1)
                model_perm.fit(X_train, y_train_shuffled)
                test_preds_perm = np.expm1(model_perm.predict(X_test))
                perm_r2 = float(r2_score(y_test, test_preds_perm))
                logger.info(f"  Test R² (Shuffled Targets): {perm_r2:.4f}")
                
            # We will save the model and metadata for the final executing fold acting as the deployed artifact seamlessly
            if fold_num == len(folds):
                final_model = model
                final_X_test = X_test
                final_y_test = y_test
                final_test_preds = test_preds
                final_X_train = X_train
                final_y_train = y_train
                final_train_raw = train_raw

        # Validation Summary
        test_r2s = [m['test_r2'] for m in fold_metrics]
        test_maes = [m['test_mae'] for m in fold_metrics]
        test_rmses = [m['test_rmse'] for m in fold_metrics]
        
        mean_r2 = np.mean(test_r2s)
        std_r2 = np.std(test_r2s)
        mean_mae = np.mean(test_maes)
        mean_rmse = np.mean(test_rmses)
        
        best_r2_fold = max(fold_metrics, key=lambda x: x['test_r2'])
        worst_r2_fold = min(fold_metrics, key=lambda x: x['test_r2'])
        
        logger.info("=" * 50)
        logger.info("ROLLING WINDOW VALIDATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"  Mean Test R²:   {mean_r2:.4f} ± {std_r2:.4f}")
        logger.info(f"  Mean Test MAE:  {mean_mae:.2f}")
        logger.info(f"  Mean Test RMSE: {mean_rmse:.2f}")
        logger.info(f"  Best Fold:  Fold {best_r2_fold['fold']} (R²: {best_r2_fold['test_r2']:.4f})")
        logger.info(f"  Worst Fold: Fold {worst_r2_fold['fold']} (R²: {worst_r2_fold['test_r2']:.4f})")
        logger.info(f"  Variance Range: [{worst_r2_fold['test_r2']:.4f}, {best_r2_fold['test_r2']:.4f}]")
        logger.info("=" * 50)
        
        # Residual Verification (from final fold)
        abs_residuals = np.abs(final_y_test - final_test_preds)
        corr = np.corrcoef(final_X_test['distance_km'], abs_residuals)[0, 1]
        logger.info(f"Residual-Distance Correlation (Final Fold): {corr:.4f}")
        
        # Compute Residual Stats for Confidence Interval mapping natively
        logger.info("Computing route-specific residual statistics for Confidence Intervals...")
        final_train_preds = np.expm1(final_model.predict(final_X_train))
        train_residuals = final_y_train - final_train_preds
        
        global_residual_std = float(np.std(train_residuals))
        residual_stats = {"global_residual_std": global_residual_std}
        
        final_train_raw['residual'] = train_residuals
        route_stats = final_train_raw.groupby('route_key')['residual'].agg(['std', 'count'])
        
        for route, row in route_stats.iterrows():
            if row['count'] >= 10 and pd.notnull(row['std']):
                residual_stats[str(route)] = float(row['std'])
                
        out_dir = os.path.dirname(__file__)
        residual_stats_path = os.path.join(out_dir, "residual_stats.json")
        with open(residual_stats_path, 'w') as f:
            json.dump(residual_stats, f, indent=4)
        logger.info(f"Residual stats exported to {residual_stats_path}")
        
        # Output feature importances
        importances = final_model.feature_importances_
        logger.info("Feature Importances (Final Fold):")
        for name, imp in zip(features, importances):
            logger.info(f"  {name}: {imp:.4f}")
            
        logger.info("Serializing model artifact...")
        out_dir = os.path.dirname(__file__)
        model_path = os.path.join(out_dir, "flight_price_model.pkl")
        joblib.dump(final_model, model_path)
        
        metadata_path = os.path.join(out_dir, "model_metadata.json")
        metadata = {
            "validation_strategy": "rolling-90-14-window",
            "training_row_count": len(folds[-1][0]) if folds else 0,
            "features": features,
            "metrics": {
                "Mean_Test_R2": mean_r2,
                "Mean_Test_MAE": mean_mae,
                "Mean_Test_RMSE": mean_rmse,
                "Residual_Distance_Corr": corr
            },
            "timestamp": datetime.now().isoformat()
        }
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)
            
        logger.info(f"Model artifact exported to {model_path}")
        logger.info(f"Metadata exported to {metadata_path}")
        
    except Exception as e:
        logger.error(f"ML pipeline exception: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    main()

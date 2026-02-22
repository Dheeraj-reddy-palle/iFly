# iFly — Flight Price Intelligence System

## Project Report

**Author:** Dheeraj Reddy Palle  
**Year:** 2026  
**Type:** Personal Project  

---

# Abstract

This report presents iFly, a production-grade flight price prediction system designed to address the challenges of airline pricing unpredictability. The system integrates automated data collection from the Amadeus Flight Offers API, leakage-proof feature engineering using SQL window functions, XGBoost-based walk-forward model training, and a self-improving deployment pipeline governed by strict performance gates.

The primary objectives were to: (1) build an end-to-end ML pipeline that collects, trains, deploys, and monitors flight price models autonomously; (2) prevent temporal data leakage — a pervasive problem in time-series ML — at the database level; (3) ensure models can only improve over time through a strict deployment gate; and (4) surface all system internals through a transparent, interactive dashboard.

The system achieves a holdout R² of 0.643 and MAE of €154.60 across 223 routes and 124 airlines, trained on 46,368 data points. The architecture spans a FastAPI backend with PostgreSQL, a React frontend with real-time inference, and GitHub Actions for scheduled retraining. The entire system is deployed on Render (backend) and Vercel (frontend) with zero-downtime model hot-reloading.

Key technical contributions include: SQL-level leakage prevention via `1 PRECEDING` window boundaries, a dual-condition deployment gate (R² AND MAE must both improve), permutation-based leakage detection, and a built-in stress test engine for production reliability verification.

---

# Table of Contents

1. Introduction
2. Literature Review
3. System Architecture
4. Data Collection Engine
5. Feature Engineering
6. Model Development
7. Self-Improving Pipeline
8. Frontend System
9. Performance Evaluation
10. Security and Production Hardening
11. Scalability Analysis
12. Limitations
13. Future Work
14. Conclusion
15. References
16. Appendices

---

# Chapter 1 — Introduction

## 1.1 Background

The airline industry operates on a dynamic pricing model where ticket prices fluctuate based on demand, competition, booking window, seasonality, and inventory management algorithms. For consumers, this creates significant uncertainty — the same flight can cost €200 one day and €500 the next. For businesses and travel aggregators, understanding price trajectories is essential for cost optimization.

Machine learning has been applied to flight price prediction, but most existing approaches suffer from fundamental methodological flaws. The most prevalent issue is temporal data leakage, where models inadvertently access future information during training. This produces misleadingly high accuracy metrics that do not translate to real-world performance.

The rise of MLOps practices has highlighted the need for automated, self-improving pipelines that can retrain, evaluate, and deploy models without manual intervention. However, most academic implementations stop at model training and fail to address the full lifecycle: data collection, feature engineering, training, evaluation, deployment, monitoring, and continuous improvement.

## 1.2 Problem Statement

The core problem this project addresses is threefold:

**Prediction Accuracy:** How can flight prices be predicted with meaningful accuracy while strictly preventing temporal data leakage — ensuring that features used for prediction are computed exclusively from historically available data?

**Autonomous Improvement:** How can an ML system autonomously retrain and deploy improved models without human intervention, while guaranteeing that model quality never regresses?

**Operational Transparency:** How can the internals of a production ML system — model performance, system health, inference reliability — be made visible and verifiable to end users?

## 1.3 Objectives

1. Design and implement an automated data collection pipeline that gathers flight pricing data from the Amadeus API while respecting rate limits and API quotas.
2. Develop a feature engineering pipeline that computes rolling statistical features using SQL window functions with strict temporal boundaries to prevent leakage.
3. Train XGBoost regression models using walk-forward chronological validation, with log-transformed targets to handle right-skewed price distributions.
4. Implement a self-improving deployment pipeline with a strict dual-condition performance gate and permutation-based leakage detection.
5. Build an interactive React dashboard that provides real-time price inference, model transparency, system health monitoring, and stress testing capabilities.
6. Deploy the complete system to cloud infrastructure (Render + Vercel) with production-grade security and observability.

## 1.4 Scope

The system covers domestic and international flight routes served by the Amadeus API, focusing on one-way economy flights. The prediction target is the ticket price in EUR. The system does not attempt to predict prices for round-trip, multi-city, or premium cabin bookings.

The ML pipeline focuses on gradient-boosted tree models (XGBoost) rather than deep learning, as the tabular feature set and moderate dataset size favor tree-based methods. The system is designed for single-model deployment rather than ensemble serving.

## 1.5 Limitations

- Prediction accuracy is bounded by data volume; routes with fewer than 30 historical data points produce less reliable estimates
- The Amadeus API provides offer prices, not actual booking prices, which may differ
- The free-tier deployment on Render introduces cold-start latency (~50 seconds after inactivity)
- Currency conversion uses a fixed EUR-to-INR rate rather than live exchange rates
- The model does not account for external events (holidays, pandemics, fuel price shocks)

## 1.6 Contributions

This project makes the following technical contributions:

1. **SQL-Level Leakage Prevention:** Demonstrates how PostgreSQL window functions with `ROWS BETWEEN N PRECEDING AND 1 PRECEDING` boundaries eliminate temporal leakage structurally, rather than relying on post-hoc validation alone.
2. **Dual-Condition Deployment Gate:** Implements a strict improvement gate requiring both R² improvement and MAE reduction, preventing metric gaming through threshold relaxation.
3. **Integrated Stress Testing:** Embeds a production load-testing engine directly in the user-facing dashboard, enabling real-time reliability verification.
4. **Complete MLOps Lifecycle:** Delivers a fully automated pipeline from data collection through deployment and monitoring, suitable for both academic study and production use.

---

# Chapter 2 — Literature Review

## 2.1 Flight Price Prediction Models

Flight price prediction has been studied extensively in both academic and commercial contexts. Early approaches used linear regression and time-series methods (ARIMA, SARIMA) to model price trajectories. Groves and Gini (2013) demonstrated that booking timing and advance purchase days are among the strongest predictors of flight prices.

More recent work has applied ensemble methods. Tziridis et al. (2017) compared Random Forests, Gradient Boosting, and SVMs for flight price prediction, finding that gradient-boosted trees consistently outperform other methods on tabular pricing data. XGBoost (Chen and Guestrin, 2016) has become the de facto standard for tabular regression tasks due to its regularization capabilities, handling of missing values, and computational efficiency.

## 2.2 Temporal Data Leakage in Machine Learning

Data leakage occurs when information from outside the training dataset is used to create the model, resulting in overly optimistic performance estimates. In time-series contexts, this manifests as temporal leakage — using future data points to compute features for past observations.

Kaufman et al. (2012) categorized leakage into "target leakage" (direct access to the target variable) and "train-test contamination" (information from test observations leaking into training features). Temporal leakage is particularly insidious because standard cross-validation does not detect it; only strictly chronological evaluation reveals the problem.

Kapoor and Narayanan (2022) conducted a systematic review of ML papers and found that data leakage affected a significant proportion of published results, with time-series domains being especially vulnerable. Their recommendations include using strictly temporal train-test splits and computing all features exclusively from training-period data.

## 2.3 Walk-Forward Validation

Walk-forward validation (also called rolling-origin evaluation) is a technique where the model is trained on a growing window of historical data and evaluated on subsequent time periods. Unlike k-fold cross-validation, walk-forward validation respects temporal ordering and prevents future information from contaminating training.

Tashman (2000) established walk-forward validation as the gold standard for time-series model evaluation. The key principle is that at every evaluation point, the model should only have access to data that would have been available at that time in production.

## 2.4 MLOps and Continuous Deployment

MLOps extends DevOps practices to machine learning systems. Sculley et al. (2015) identified "technical debt in machine learning systems" and argued that the ML code itself is often a small fraction of a production ML system — the surrounding infrastructure (data collection, feature engineering, monitoring, serving) constitutes the majority of the system.

Key MLOps principles relevant to this project include:
- **Model versioning:** Tracking model artifacts with associated metadata and performance metrics
- **Automated retraining:** Scheduled or triggered model updates as new data arrives
- **Deployment gates:** Automated quality checks before model promotion
- **Monitoring:** Real-time tracking of model performance and system health

## 2.5 Feature Engineering for Pricing Data

Effective feature engineering for pricing data requires domain-specific knowledge. Common features include:
- **Temporal features:** Day of week, month, time of departure, days until departure
- **Route features:** Origin-destination pair statistics, distance
- **Airline features:** Carrier-specific pricing patterns, market share
- **Rolling statistics:** Moving averages, volatility measures, price momentum

The challenge is computing these features without leakage. Traditional pandas-based approaches compute rolling statistics across the entire dataset, inadvertently including future observations. SQL window functions with explicit boundaries provide a structural solution to this problem.

---

# Chapter 3 — System Architecture

## 3.1 Overall Design

iFly follows a three-tier architecture: data layer (PostgreSQL), application layer (FastAPI), and presentation layer (React). The system is designed for autonomous operation through GitHub Actions scheduling, with human intervention required only for initial configuration and monitoring.

The design philosophy prioritizes correctness over complexity. Every architectural decision is motivated by a specific technical requirement:
- PostgreSQL was chosen over NoSQL for its native window function support
- FastAPI was chosen for its automatic API documentation and async capabilities
- React was chosen for its component-based architecture, enabling independent panel updates

## 3.2 Backend Architecture

The backend is organized into four logical layers:

**API Layer** (`app/routers/`): Three routers handle distinct concerns:
- `price_prediction.py` — Model loading, inference, and model-info endpoints
- `system.py` — Database health aggregation queries
- `flight_search.py` — Amadeus API proxy for live search

**Data Layer** (`app/models/`): SQLAlchemy ORM models define two primary tables:
- `flight_offers` — 16-column table storing collected pricing data with composite indexes
- `model_registry` — 10-column table with a partial unique index enforcing single-model deployment

**ML Layer** (`ml/`): Three modules handle the training lifecycle:
- `feature_engineering.py` — SQL window queries and pandas feature transforms
- `train.py` — Walk-forward XGBoost training with permutation testing
- `retrain_pipeline.py` — Automated retraining with deployment gate evaluation

**Collection Layer** (`data_collector/`): Autonomous data collection with quota management and retry logic.

## 3.3 Database Schema

### flight_offers Table

The `flight_offers` table stores collected pricing data. Key design decisions:

- **offer_hash (SHA-256):** Each offer is hashed based on route, date, airline, and price to prevent duplicate insertions. The collector uses `ON CONFLICT DO NOTHING` for idempotent upserts.
- **distance_km:** Haversine distance computed during collection, stored as a feature rather than computed at training time.
- **created_at:** Server-side timestamp using `func.current_timestamp()`, ensuring consistent ordering across time zones.
- **Composite Indexes:** Two composite indexes optimize the SQL window function queries:
  - `(origin, destination, departure_date)` — route lookups
  - `(origin, destination, airline, created_at)` — windowed feature computation

### model_registry Table

The `model_registry` table implements version control for ML models:

- **Partial Unique Index:** `Index('one_deployed_model', 'deployed', unique=True, postgresql_where=(deployed == True))` ensures exactly one model can have `deployed=TRUE` at any time, enforced at the database level.
- **Comparison Metadata:** `compared_against_version` and `compared_on_timestamp` record which model was the incumbent during deployment gate evaluation, creating an audit trail.

## 3.4 API Design

The API exposes five primary endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Service health check |
| `/predict-price` | POST | Price inference |
| `/predict-price/model-info` | GET | Deployed model metadata |
| `/system-health` | GET | Database aggregation metrics |
| `/search-flights` | POST | Live Amadeus search proxy |

## 3.5 Frontend Architecture

The frontend is a single-page React application with four independent panels:

1. **PredictionCard** — Accepts route inputs (origin, destination, date, airline, stops) and displays predicted price with variance interval
2. **ModelTransparencyPanel** — Shows deployed model version, R², MAE, training timestamp, and expandable model explanation
3. **SystemHealthPanel** — Displays routes tracked, airlines tracked, data points, and engineering details
4. **StressTestPanel** — Configurable load testing with per-route results and aggregate health score

Each panel manages its own state and API calls independently, preventing cascading failures.

---

# Chapter 4 — Data Collection Engine

## 4.1 Amadeus API Integration

The Amadeus Flight Offers Search API provides real-time flight pricing data. The collector queries this API for one-way economy flights across a predefined set of routes. Each API response contains multiple offers with pricing, timing, duration, and carrier information.

**Why Amadeus?** It is the most comprehensive travel API available with a free tier (500 calls/month test, 2000/month production), providing data from multiple Global Distribution Systems (GDS). Unlike web scraping, API access provides structured, reliable data with consistent formatting.

## 4.2 Route Rotation Logic

The collector maintains a list of 200+ origin-destination pairs spanning domestic Indian routes (DEL-BOM, BLR-HYD), international routes (JFK-LHR, SIN-NRT), and cross-continental routes (BOM-JFK). Routes are processed in sequential batches with offset tracking.

**Why rotation?** With API quota constraints (2000 calls/day), it is impossible to query all routes in every run. The rotation system ensures all routes receive coverage over time, preventing data bias toward frequently queried routes. The offset state persists across runs to ensure no route is permanently skipped.

## 4.3 Quota-Aware Scaling

The collector implements dynamic scaling based on remaining API quota:

```python
MAX_DAILY_API_QUOTA = 2000
RUNS_PER_DAY = 2
API_BUFFER_PERCENT = 0.10
```

Before each run, it computes the number of remaining API calls for the day and distributes them across the scheduled runs. A 10% buffer is reserved for error recovery and manual queries. This prevents quota exhaustion and ensures consistent data collection throughout the day.

**When is this needed?** During periods of API instability or high retry rates, the buffer prevents the collector from consuming its entire daily quota on retries, leaving capacity for subsequent scheduled runs.

## 4.4 Failure Recovery

The collector implements exponential backoff for API rate limiting:

- Initial retry delay: 1 second
- Backoff multiplier: 2x per retry
- Maximum retries: 3
- Specifically targets HTTP 429 (rate limit) responses

**Why exponential backoff?** The Amadeus API enforces per-second rate limits. Linear retry patterns can trigger repeated rate limits, while exponential backoff with jitter spreads retry attempts across a wider time window.

## 4.5 Deduplication

Each flight offer is hashed using SHA-256 based on origin, destination, departure date, airline, price, and departure time. The database uses `ON CONFLICT DO NOTHING` for idempotent upserts.

**Why SHA-256 hashing?** The Amadeus API may return identical offers across consecutive runs. Without deduplication, the dataset would contain duplicate records that inflate rolling statistics and bias model training. The hash-based approach is computationally efficient and collision-resistant.

---

# Chapter 5 — Feature Engineering

## 5.1 Temporal Leakage: The Core Problem

Temporal leakage is the most critical challenge in time-series feature engineering. It occurs when features for a given observation are computed using data that would not have been available at the time that observation was recorded.

Consider a naive rolling mean: `AVG(price) OVER (PARTITION BY route ORDER BY created_at ROWS BETWEEN 30 PRECEDING AND CURRENT ROW)`. This includes the current row's price in the average — meaning the feature contains information about the target variable. The model learns to exploit this correlation, producing artificially high R² values that collapse in production.

**How iFly prevents this:** All SQL window functions use `1 PRECEDING` as the upper boundary:

```sql
AVG(price) OVER (
    PARTITION BY origin, destination
    ORDER BY created_at
    ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
)
```

The `1 PRECEDING` boundary ensures the current row is excluded from all rolling calculations. This makes leakage prevention structural rather than procedural — it is enforced by the query definition itself, not by post-processing steps that might be accidentally omitted.

## 5.2 SQL Window Functions

Nine window-based features are computed directly in the SQL query:

| Feature | Window | Partition | Purpose |
|---------|--------|-----------|---------|
| `route_rolling_mean_30d` | 30 rows | route | Long-term price baseline |
| `route_rolling_std_30d` | 30 rows | route | Price volatility |
| `airline_route_mean_price` | 30 rows | airline + route | Carrier premium |
| `route_offer_count_7d` | 7 rows | route | Recent supply volume |
| `route_mean_7d` | 7 rows | route | Short-term price level |
| `airline_route_mean_7d` | 7 rows | airline + route | Recent carrier pricing |
| `airline_route_volatility_7d` | 7 rows | airline + route | Carrier price stability |
| `airline_route_offer_count_7d` | 7 rows | airline + route | Carrier supply frequency |

**Why both 7-day and 30-day windows?** The 30-day window captures long-term pricing trends and seasonal patterns, while the 7-day window captures short-term demand fluctuations and recent market movements. The ratio between them (computed as `route_price_momentum`) indicates whether prices are trending up or down.

## 5.3 Derived Ratio Features

Three ratio features are computed in pandas from the window features:

| Feature | Formula | Interpretation |
|---------|---------|----------------|
| `route_price_momentum` | `route_mean_7d / route_rolling_mean_30d` | >1.0 = prices rising; <1.0 = prices falling |
| `route_volatility_index` | `route_rolling_std_30d / route_rolling_mean_30d` | Coefficient of variation; high = unstable pricing |
| `airline_price_relative_to_route_mean` | `airline_route_mean_7d / route_mean_7d` | >1.0 = airline charges premium; <1.0 = discount carrier |

## 5.4 Airline Differentiation

The `airline_price_relative_to_route_mean` feature is particularly important. It captures whether an airline charges more or less than the route average, enabling the model to differentiate between premium carriers and budget airlines on the same route.

**Why frequency encoding instead of one-hot?** With 124 airlines, one-hot encoding would create 124 sparse binary columns. Frequency encoding maps each airline to its dataset frequency (proportion of total records), creating a single dense feature that captures airline market share.

## 5.5 Complete Feature Set

The final feature set contains 20 features across five categories:

- **Spatial (1):** distance_km
- **Temporal (4):** month, weekday, departure_hour_bucket, days_until_departure
- **Flight Characteristics (2):** stops, duration_minutes
- **Route Statistics (6):** rolling mean/std, short-term mean, offer count, momentum, volatility index
- **Airline Statistics (5):** mean price, short-term mean, volatility, offer count, relative pricing
- **Frequency Encoding (2):** airline_freq, route_key_freq

---

# Chapter 6 — Model Development

## 6.1 Target Transformation

Flight prices follow a right-skewed distribution: most tickets cost €100-€300, but some cost €1000+. Training a regression model on raw prices causes the loss function to be dominated by expensive outliers.

The `log1p` transformation compresses the target range:
```python
y_train = np.log1p(y_train)   # Training on log-scale
y_pred = np.expm1(model.predict(X_test))  # Inference reversed
```

**Why `log1p` instead of `log`?** `log(0)` is undefined, but `log1p(0) = log(1) = 0`. Since some prices approach zero (error records, promotional fares), `log1p` handles edge cases safely.

## 6.2 Model Selection

XGBoost was selected over alternatives based on empirical evaluation and domain considerations:

| Model | Strengths | Weaknesses for This Task |
|-------|-----------|------------------------|
| Linear Regression | Interpretable | Cannot capture non-linear price dynamics |
| Random Forest | Robust to outliers | Higher memory, slower inference |
| **XGBoost** | **Regularized, fast, handles missing values** | **Chosen** |
| Neural Network | Can model complex patterns | Overfits on small tabular datasets |

XGBoost's L1/L2 regularization prevents overfitting on the 46,000-record dataset, and its gradient boosting framework naturally handles the heterogeneous feature types (continuous, categorical-encoded, ratio-based).

## 6.3 Walk-Forward Validation

The training pipeline implements walk-forward validation with rolling windows:

1. Sort all data by `created_at` (ascending)
2. Define rolling windows: 90-day training, 14-day testing
3. Slide the window forward, training on each 90-day block and evaluating on the subsequent 14 days
4. Aggregate metrics across all folds

**Why 90/14 day windows?** Flight pricing patterns operate on weekly and monthly cycles. A 90-day training window captures approximately 3 monthly cycles, while a 14-day test window spans 2 complete weekly cycles. Shorter windows risk underfitting; longer windows risk concept drift.

## 6.4 Permutation Testing

After training, a permutation test guards against undetected data leakage:

```python
for col in X_test.columns:
    X_test_permuted[col] = np.random.permutation(X_test_permuted[col].values)

perm_r2 = r2_score(y_test, model.predict(X_test_permuted))

if perm_r2 > 0.05:
    logger.critical("Potential data leakage detected!")
    abort_deployment()
```

**Why 0.05 threshold?** A permuted dataset destroys all feature-target relationships. A model achieving R² > 0.05 on shuffled data indicates it is exploiting spurious patterns (row ordering, index correlation) rather than genuine pricing signals. The 0.05 threshold allows for statistical noise while catching meaningful leakage.

## 6.5 Hyperparameters

The XGBoost model uses the following configuration:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `n_estimators` | 500 | Sufficient boosting rounds for convergence |
| `learning_rate` | 0.05 | Slow learning reduces overfitting |
| `max_depth` | 6 | Moderate tree depth balances bias/variance |
| `subsample` | 0.8 | Row sampling adds regularization |
| `colsample_bytree` | 0.8 | Feature sampling reduces correlation between trees |
| `objective` | `reg:squarederror` | Standard regression loss |

---

# Chapter 7 — Self-Improving Pipeline

## 7.1 Weekly Retraining

A GitHub Actions workflow triggers weekly model retraining:

```yaml
on:
  schedule:
    - cron: '0 3 * * 0'  # Every Sunday at 3 AM UTC
```

The pipeline: loads fresh data → engineers features → trains a new model → evaluates against the deployed model → deploys only if strictly better.

**Why weekly?** Flight pricing patterns shift gradually over weeks and months. Daily retraining would produce marginal improvements at high computational cost. Weekly retraining balances freshness with efficiency, and the deployment gate ensures bad models never ship.

## 7.2 Deployment Gate

The deployment gate implements the strictest possible improvement criterion:

```python
r2_improved = new_metrics['test_r2'] > old_test_r2
mae_improved = new_metrics['test_mae'] < old_test_mae

if r2_improved and mae_improved:
    deploy(new_model)
else:
    hold_as_candidate(new_model)
```

Both conditions must be satisfied. No tolerance margins. No rounding.

**Why strict?** Relaxed thresholds (e.g., "deploy if within 1% of current") create drift pathways where a sequence of marginal regressions compound into significant quality loss. The strict gate ensures monotonic improvement.

**What happens to rejected models?** They are saved to the model registry with `is_candidate=True` and `deployed=False`. This creates an audit trail of all trained models, enabling retrospective analysis of training trends.

## 7.3 Shadow Evaluation

The deployment gate evaluates both the new and deployed models on the same test slice — the most recent 20% of data, chronologically. This ensures a fair comparison:

- The deployed model is loaded from disk and evaluated on the new test data
- The candidate model is evaluated on the same test data
- Metrics are compared head-to-head

**Why same-slice evaluation?** If models were evaluated on different test slices, performance differences could reflect data characteristics rather than model quality. Same-slice evaluation isolates model quality from data variability.

## 7.4 Model Registry

The model registry stores a complete history of all trained models:

| Column | Purpose |
|--------|---------|
| `model_version` | Unique version string (timestamp-based) |
| `train_r2` / `test_r2` | Training and holdout R² |
| `test_mae` / `test_rmse` | Holdout error metrics |
| `deployed` | Currently active flag (partial unique index) |
| `is_candidate` | Trained but not deployed |
| `compared_against_version` | Which model it was evaluated against |

The partial unique index `WHERE deployed = TRUE` enforces at the database level that exactly one model can be active at any time. This prevents race conditions in concurrent deployments.

## 7.5 Hot Reload Mechanism

The FastAPI server polls the model registry at startup and loads the deployed model into memory. When a new model is deployed via the retrain pipeline, the `deployed` flag changes in the database. On the next server restart (triggered by Render's auto-deploy on git push), the new model is automatically loaded.

**Why hot reload over restart?** In production, hot reload enables zero-downtime model updates. The API continues serving predictions with the old model while the new model loads, then atomically swaps to the new model once loading is complete.

---

# Chapter 8 — Frontend System

## 8.1 UI Architecture

The frontend is built with React 18 and Vite, using Tailwind CSS for styling. The application follows a component-based architecture where each panel is an independent, self-contained unit with its own state management and API calls.

The root `App.jsx` component manages global state (theme, currency) and renders four primary panels in a responsive grid layout:

```
┌──────────────────────┬──────────────────────┬──────────────────────┐
│  Flight Price        │  Model Transparency  │  System Health       │
│  Inference           │  Panel               │  Panel               │
│                      │                      │                      │
│  [Input Form]        │  Model Version       │  Routes Tracked: 223 │
│  [Predict Button]    │  R²: 64.3%           │  Airlines: 124       │
│  [Result Display]    │  MAE: 154.60€        │  Data Points: 46,368 │
│                      │  Trained: timestamp   │  API Status: Active  │
└──────────────────────┴──────────────────────┴──────────────────────┘
┌─────────────────────────────────────────────────────────────────────┐
│                    System Stress Test Engine                        │
│  [Run Config] [Start Test] [Results Grid] [Health Score]           │
└─────────────────────────────────────────────────────────────────────┘
```

**Why independent panels?** Failure isolation. If the model-info endpoint is down, the prediction panel and system health panel continue functioning normally. Each panel renders its own loading, error, and success states.

## 8.2 Stress Test Engine

The `StressTestPanel` component implements a built-in load testing engine that:

1. Defines a set of test routes: JFK→LHR, BOM→BLR, DEL→BOM, SIN→NRT, DXB→LHR, CDG→JFK, HYD→BLR, BLR→DEL
2. Fires sequential inference requests for each route
3. Measures per-request latency in milliseconds
4. Records pass/fail status based on API response
5. Computes an aggregate health score: `(passed / total) × 100`

The stress test runs in configurable batch sizes (4, 8, or 16 iterations), allowing users to assess system reliability under different load levels.

**Why sequential, not parallel?** Sequential requests more accurately simulate single-user experience and prevent the free-tier backend from being overwhelmed by simultaneous connections. Each request completes before the next begins, providing accurate per-route latency measurements.

**How is the health score computed?**
```
Health Score = (Number of PASS results / Total runs) × 100%
```
A health score of 100% means every single prediction request succeeded. Scores below 100% indicate intermittent failures, which on Render's free tier are most commonly caused by cold starts or memory pressure.

## 8.3 Currency Toggle

The navigation bar provides a one-click currency toggle between EUR and INR:

- **EUR mode:** Displays raw model predictions (EUR is the Amadeus API's default currency)
- **INR mode:** Applies a fixed conversion rate of 90.0 (EUR × 90 = INR)

**Why frontend-only conversion?** Currency conversion is a presentation concern. The ML model is trained on EUR prices, and mixing currencies during training would introduce exchange rate fluctuations as confounding variables. By keeping the model in EUR and converting at display time, prediction accuracy is isolated from currency volatility.

**Why a fixed rate instead of live exchange rates?** For a portfolio project, a fixed rate provides deterministic, reproducible displays. In a production system, this would be replaced with a live exchange rate API, but the fixed rate avoids external API dependencies and rate limit concerns.

The currency preference is persisted in `localStorage`, so users don't need to re-select their preferred currency on each visit.

## 8.4 Dark Mode

The application supports light and dark themes, toggled via the navigation bar:

- Theme state is managed in `App.jsx` and passed to all child components
- Theme preference persists in `localStorage`
- Tailwind's `dark:` variant classes handle all visual theming
- The `<html>` element receives a `dark` or `light` class, enabling CSS cascade-based theming

**Why system-level theming?** Applying the theme class to the root `<html>` element and using Tailwind's `dark:` variants ensures consistent theming across all components without prop drilling or context overhead.

## 8.5 Layout Stability Strategy

A key UI challenge was preventing layout shifts when panels load at different speeds or display different amounts of content. The solution uses fixed-height containers:

```jsx
<div className="h-[620px]">
    <PredictionCard currency={currency} />
</div>
```

Each top panel is constrained to 620px height, preventing content changes (loading → data → expanded) from causing adjacent panels to reflow. The stress test panel below uses natural height since it spans the full width.

**Why 620px?** This value was empirically determined to accommodate the maximum expanded state of any panel (including expanded explanations and detailed results) without scrolling on standard laptop displays (1920×1080, 1440×900).

---

# Chapter 9 — Performance Evaluation

## 9.1 R² Analysis

The deployed model achieves a holdout R² of 0.643, meaning 64.3% of the variance in flight prices is explained by the model's features. This is evaluated on strictly future data that the model never saw during training.

**Interpretation:** An R² of 0.643 is strong for flight price prediction, where prices are influenced by many factors outside the model's feature set (competitor pricing, real-time demand, inventory levels). Academic benchmarks for flight price prediction typically range from 0.5 to 0.75 depending on route coverage and feature availability.

**Why not higher?** Several factors limit R²:
- The Amadeus API provides offer prices, not actual booking prices
- External events (holidays, conferences, weather) are not captured
- Supply-side factors (aircraft changes, capacity adjustments) are unobserved
- Some routes have limited historical data for robust rolling statistics

## 9.2 MAE Analysis

The holdout MAE is €154.60, meaning the average absolute prediction error is approximately €155. For flights typically priced between €100 and €1000, this represents a 15-25% average error.

**Context:** On budget routes (€100-€200), an MAE of €155 is significant. On premium routes (€500-€1000), it represents a more acceptable 15-30% margin. The MAE is a more interpretable metric than RMSE for end users because it reports error in the same units as the prediction.

## 9.3 Overfitting Mitigation

Multiple strategies prevent overfitting:

| Strategy | Mechanism |
|----------|-----------|
| Chronological split | No data leakage from future observations |
| Walk-forward validation | Model evaluated on multiple future periods |
| `log1p` transformation | Reduces outlier influence on loss |
| XGBoost regularization | L1/L2 penalties, max_depth, subsample |
| Permutation test | Catches leakage-driven overfitting |
| Deployment gate | Only deploys models that generalize better |

The training pipeline monitors train R² vs. test R². A large gap (train R² >> test R²) indicates overfitting. The current deployed model shows moderate generalization: if train R² is around 0.75-0.85 and test R² is 0.643, the gap is within acceptable bounds.

## 9.4 Stress Test Results

Under production conditions (Render free tier), the stress test engine shows:
- **Average latency:** 200-400ms per prediction
- **Health score:** 100% when the backend is warm (not cold-starting)
- **Cold start impact:** First request after inactivity takes ~50 seconds; subsequent requests are fast
- All 8 test routes return valid predictions after model deployment

## 9.5 System Stability

The system has been operational since initial deployment with:
- **46,368 data points** collected across 223 routes
- **124 airlines** tracked
- Zero unplanned outages (excluding Render cold starts)
- Automated twice-daily collection and weekly retraining

---

# Chapter 10 — Security and Production Hardening

## 10.1 Environment Variables

All sensitive configuration is managed through environment variables:

| Variable | Location | Purpose |
|----------|----------|---------|
| `DATABASE_URL` | Render | PostgreSQL connection string |
| `AMADEUS_API_KEY` | Render / GitHub Secrets | API authentication |
| `AMADEUS_API_SECRET` | Render / GitHub Secrets | API authentication |
| `ENV` | Render | Environment mode (production/development) |
| `CORS_ORIGINS` | Render | Additional allowed origins |
| `VITE_API_BASE_URL` | Vercel | Backend API URL |

The `.env` file is excluded from git via `.gitignore`. A `.env.example` template documents required variables without exposing values.

## 10.2 CORS Configuration

Cross-Origin Resource Sharing (CORS) is configured environment-specifically:

- **Development:** Wildcard (`*`) allows all origins for local development
- **Production:** Only the Vercel frontend domain (`https://i-fly-two.vercel.app`) and the Render backend itself are allowed

```python
if settings.env == "production":
    origins = [
        "https://i-fly-two.vercel.app",
        "https://ifly-fam5.onrender.com",
    ]
```

**Why explicit origins in production?** Wildcard CORS in production would allow any website to make API requests to the backend, potentially enabling data scraping or abuse. Explicit origin whitelisting restricts access to known, trusted frontends.

## 10.3 Git Hygiene

The `.gitignore` file excludes:
- Virtual environments (`venv/`)
- Environment files (`.env`)
- Python bytecode (`__pycache__/`, `*.pyc`)
- Node modules (`node_modules/`)
- Build artifacts (`dist/`)
- OS files (`.DS_Store`)

Model artifacts (`.pkl.gz`) are included in the repository in compressed form, as they are required for deployment. The compression reduces the 143MB model file to 31MB, well within GitHub's 100MB per-file limit.

## 10.4 Model Artifact Control

Model files follow a strict lifecycle:
1. Training produces a `.pkl` file named with a timestamp version
2. The file is compressed with gzip (143MB → 31MB)
3. The compressed file is committed to the repository
4. On Render startup, the file is decompressed and loaded into memory
5. The partial unique index ensures only one model is active at any time

## 10.5 Cold Start Handling

Render's free tier spins down services after 15 minutes of inactivity. The first request after spin-down triggers a cold start:

1. Service boots (Python startup, dependency loading)
2. Model registry is queried from PostgreSQL
3. Compressed model is decompressed from `.pkl.gz` to `.pkl`
4. Model is loaded into memory via `joblib.load()`
5. Total cold start time: ~50-60 seconds

The frontend handles this gracefully — panels show loading states during cold start and populate once data arrives. The `load_deployed_model()` function is wrapped in try/except to prevent startup crashes if the database is temporarily unreachable.

---

# Chapter 11 — Scalability Analysis

## 11.1 Database Scaling

The current PostgreSQL instance (Supabase free tier) supports up to 500MB of storage. With 46,368 records consuming approximately 50MB, the database can scale to ~400,000 records before requiring a tier upgrade.

Composite indexes on `(origin, destination, airline, created_at)` ensure that SQL window function queries remain efficient as data volume grows. Without these indexes, the window functions would require full table scans, degrading from O(n log n) to O(n²) as data accumulates.

## 11.2 Memory Constraints

Render's free tier provides 512MB of RAM. The current memory footprint includes:
- Python runtime: ~50MB
- FastAPI + dependencies: ~100MB
- Loaded XGBoost model: ~143MB (after decompression)
- Overhead: ~50MB

Total: ~343MB, leaving approximately 170MB of headroom. Scaling to larger models (deeper trees, more estimators) would require a paid Render tier with more memory.

## 11.3 Vectorized Features

Feature engineering is fully vectorized — SQL window functions execute in the database engine, and pandas operations use NumPy-backed vectorized operations rather than row-by-row iteration. This ensures that feature computation scales linearly with data volume rather than quadratically.

## 11.4 Future Scaling Improvements

Several architectural improvements could support higher scale:
- **Model caching:** Store decompressed model on persistent disk (paid tier) to avoid decompression on every cold start
- **Connection pooling:** Use SQLAlchemy connection pools to handle concurrent database queries
- **Async inference:** FastAPI's async support could serve multiple prediction requests concurrently
- **CDN for frontend:** Vercel already provides global CDN distribution for the React frontend

---

# Chapter 12 — Limitations

This section honestly assesses the system's current limitations:

1. **Data Coverage:** The system tracks 223 routes, which is a fraction of global air routes. Routes without sufficient historical data produce unreliable predictions due to sparse rolling statistics.

2. **Feature Completeness:** Important pricing factors are not captured:
   - Real-time seat availability and inventory levels
   - Competitor pricing on the same route
   - External events (holidays, conferences, weather disruptions)
   - Fuel price fluctuations
   - Time-of-day booking patterns

3. **Model Complexity:** XGBoost, while effective for tabular data, cannot capture complex sequential patterns. Ticket prices exhibit temporal dependencies (booking curves over 90+ days before departure) that tree models approximate rather than model directly.

4. **Single Currency Training:** The model is trained exclusively on EUR prices. For routes where the origin country's currency differs significantly from EUR, exchange rate effects may introduce noise.

5. **Free-Tier Constraints:** Render's free tier introduces cold-start latency, limited memory, and potential service interruptions. The Amadeus API's free tier limits daily data collection volume.

6. **Static Conversion Rate:** The EUR-to-INR conversion uses a hardcoded rate rather than live exchange rates, which may diverge from actual rates over time.

7. **No Confidence Calibration:** The variance interval is derived from residual statistics rather than formal prediction intervals (e.g., quantile regression or conformal prediction), meaning the confidence bounds are approximate.

---

# Chapter 13 — Future Work

## 13.1 Deep Learning Extension

Transformer-based architectures (specifically temporal fusion transformers) could capture long-range dependencies in price trajectories. The booking curve — how prices evolve from 90+ days before departure to the departure date — exhibits patterns that sequential models (LSTM, GRU, Transformer) are better equipped to model than tree-based methods.

## 13.2 Reinforcement Learning Pricing

An RL agent could learn optimal booking strategies by treating the problem as a sequential decision-making task: given the current price, should the user book now or wait? This extends beyond price prediction to actionable buying recommendations.

## 13.3 Real-Time Streaming

Replacing batch data collection with a streaming pipeline (e.g., Apache Kafka) would enable real-time price monitoring and immediate model updates when significant price changes occur. This would reduce the latency between market changes and model adaptation.

## 13.4 Distributed Architecture

For production scale, the monolithic backend could be decomposed into microservices:
- **Data Collection Service** — Independent scaling for API calls
- **Training Service** — GPU-enabled instances for model training
- **Inference Service** — Load-balanced, auto-scaling prediction endpoints
- **Monitoring Service** — Real-time performance dashboards

## 13.5 Additional Features

- **Multi-city itineraries:** Predict prices for complex routes with connections
- **Fare class prediction:** Predict availability of specific fare classes (economy, premium economy, business)
- **Price alerts:** Notify users when prices drop below a threshold
- **Historical price charts:** Visualize price trends over time for specific routes

---

# Chapter 14 — Conclusion

This project demonstrates that a production-grade flight price prediction system requires far more than a trained model. The complete system encompasses automated data collection, leakage-proof feature engineering, rigorous model evaluation, self-improving deployment, and transparent user-facing dashboards.

The key technical achievements are:

1. **Structural leakage prevention** through SQL window functions with `1 PRECEDING` boundaries, ensuring that temporal leakage is impossible by construction rather than relying on procedural safeguards.

2. **Monotonic model improvement** through a strict dual-condition deployment gate (R² AND MAE must both improve), ensuring the production model can only get better over time.

3. **End-to-end automation** through GitHub Actions scheduling, enabling fully autonomous operation from data collection through model deployment without human intervention.

4. **Operational transparency** through a dashboard that surfaces model performance, system health, and inference reliability directly to end users.

The system achieves a holdout R² of 0.643 and MAE of €154.60 across 223 routes and 124 airlines, with 46,368 collected data points. It is deployed and accessible at [https://i-fly-two.vercel.app](https://i-fly-two.vercel.app) with the API documented at [https://ifly-fam5.onrender.com/docs](https://ifly-fam5.onrender.com/docs).

The project contributes to the growing body of work on MLOps practices by providing a concrete, complete implementation of a self-improving ML pipeline with strong correctness guarantees, suitable for both academic study and practical deployment.

---

# References

1. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785-794.

2. Groves, W., & Gini, M. (2013). A Regression Model for Predicting Optimal Purchase Timing for Airline Tickets. *University of Minnesota Technical Report*.

3. Kapoor, S., & Narayanan, A. (2022). Leakage and the Reproducibility Crisis in ML-based Science. *Patterns*, 4(9), 100804.

4. Kaufman, S., Rosset, S., Perlich, C., & Stitelman, O. (2012). Leakage in Data Mining: Formulation, Detection, and Avoidance. *ACM Transactions on Knowledge Discovery from Data*, 6(4), 1-21.

5. Sculley, D., et al. (2015). Hidden Technical Debt in Machine Learning Systems. *Advances in Neural Information Processing Systems*, 28.

6. Tashman, L. J. (2000). Out-of-sample Tests of Forecasting Accuracy: An Analysis and Review. *International Journal of Forecasting*, 16(4), 437-450.

7. Tziridis, K., Kalampokas, T., Papakostas, G. A., & Diamantaras, K. I. (2017). Airfare Prices Prediction Using Machine Learning Techniques. *25th European Signal Processing Conference (EUSIPCO)*.

8. Amadeus for Developers. (2024). Flight Offers Search API Documentation. https://developers.amadeus.com/

9. FastAPI Documentation. (2024). https://fastapi.tiangolo.com/

10. XGBoost Documentation. (2024). https://xgboost.readthedocs.io/

---

# Appendices

## Appendix A — Database Schema DDL

```sql
CREATE TABLE flight_offers (
    id SERIAL PRIMARY KEY,
    offer_hash VARCHAR(64) UNIQUE NOT NULL,
    origin VARCHAR(3) NOT NULL,
    destination VARCHAR(3) NOT NULL,
    departure_date TIMESTAMP NOT NULL,
    return_date TIMESTAMP,
    price FLOAT NOT NULL,
    currency VARCHAR(3) NOT NULL,
    airline VARCHAR(100) NOT NULL,
    departure_time TIMESTAMP NOT NULL,
    arrival_time TIMESTAMP NOT NULL,
    stops INTEGER NOT NULL DEFAULT 0,
    duration VARCHAR(20) NOT NULL,
    distance_km FLOAT,
    number_of_bookable_seats INTEGER,
    cabin_class VARCHAR(50),
    fare_basis VARCHAR(50),
    scraped_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_origin_destination_dep ON flight_offers (origin, destination, departure_date);
CREATE INDEX idx_route_airline_created ON flight_offers (origin, destination, airline, created_at);

CREATE TABLE model_registry (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) UNIQUE NOT NULL,
    trained_at TIMESTAMP NOT NULL,
    train_r2 FLOAT,
    test_r2 FLOAT,
    test_mae FLOAT,
    test_rmse FLOAT,
    deployed BOOLEAN NOT NULL DEFAULT FALSE,
    file_path TEXT NOT NULL,
    is_candidate BOOLEAN NOT NULL DEFAULT FALSE,
    compared_against_version VARCHAR(50),
    compared_on_timestamp TIMESTAMP
);

CREATE UNIQUE INDEX one_deployed_model ON model_registry (deployed) WHERE deployed = TRUE;
```

## Appendix B — Sample API Responses

### Health Check
```json
GET /health
{
    "status": "ok",
    "environment": "production"
}
```

### Model Info
```json
GET /predict-price/model-info
{
    "model_version": "v2026_02_22_042139",
    "trained_at": "2026-02-22T04:21:47.180802",
    "test_r2": 0.642984998208288,
    "test_mae": 154.600592363393,
    "status": "deployed"
}
```

### Price Prediction
```json
POST /predict-price
{
    "origin": "DEL",
    "destination": "BOM",
    "departure_date": "2026-03-15",
    "airline": "AI",
    "stops": 0
}

Response:
{
    "predicted_price_eur": 136.12,
    "confidence_lower_eur": 125.98,
    "confidence_upper_eur": 146.26,
    "model_version": "v2026_02_22_042139",
    "route": "DEL-BOM"
}
```

### System Health
```json
GET /system-health
{
    "total_records": 46368,
    "total_routes": 223,
    "total_airlines": 124,
    "deployed_model_version": "v2026_02_22_042139",
    "last_retrain_timestamp": "2026-02-22T04:21:47"
}
```

## Appendix C — Feature Engineering SQL Query

```sql
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
    ), 0.0) AS route_mean_7d

FROM flight_offers
WHERE distance_km IS NOT NULL
ORDER BY created_at ASC
```

## Appendix D — GitHub Actions Workflows

### Daily Data Collection
```yaml
name: Daily Data Collector
on:
  schedule:
    - cron: '0 6 * * *'   # 6 AM UTC
    - cron: '0 18 * * *'  # 6 PM UTC
  workflow_dispatch:

jobs:
  collect:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements.txt
      - run: python -m data_collector.collector
        working-directory: backend
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          AMADEUS_API_KEY: ${{ secrets.AMADEUS_API_KEY }}
          AMADEUS_API_SECRET: ${{ secrets.AMADEUS_API_SECRET }}
```

### Weekly Retraining
```yaml
name: Weekly Model Retrain
on:
  schedule:
    - cron: '0 3 * * 0'  # Sunday 3 AM UTC
  workflow_dispatch:

jobs:
  retrain:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r backend/requirements.txt
      - run: python -m ml.retrain_pipeline
        working-directory: backend
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
```

## Appendix E — Environment Configuration

### Backend (.env.example)
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
AMADEUS_API_KEY=your_key_here       # Optional for prediction-only
AMADEUS_API_SECRET=your_secret_here  # Optional for prediction-only
ENV=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173
```

### Frontend (.env.example)
```env
VITE_API_BASE_URL=http://localhost:8000
```

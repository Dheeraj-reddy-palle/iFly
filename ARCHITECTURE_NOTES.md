# iFly — Production Architecture & Safeguard Notes

> This document describes the engineering safeguards, architectural decisions,
> and production constraints enforced across the iFly ML system.

---

## 1. Deployment Gate — Strict Performance Comparison

The retraining pipeline enforces a deterministic performance gate before
allowing any new model to become production-active.

**Deployment occurs ONLY if:**

```
new_test_r2  > deployed_test_r2
AND
new_test_mae < deployed_test_mae
```

**Guarantees:**
- Candidate and deployed models evaluated on the **exact same validation slice**
- Deployed model reloaded from disk and re-evaluated before comparison
- No tolerance margins, no rounding, no relaxed thresholds

---

## 2. Permutation Leakage Safeguard

Before any deployment gate evaluation:

- All features are randomly shuffled
- Model is evaluated on permuted test set
- **Expected:** Test R² < 0

If R² > 0.05 → **deployment aborted immediately**

Protects against: target leakage, temporal contamination, identity memorization.

---

## 3. Target Transformation (Log Scale)

Flight prices follow a right-skewed distribution.

```python
# Training
y_train_log = np.log1p(price)

# Inference
prediction = np.expm1(prediction_log)
```

Ensures: reduced heteroscedasticity, stable convergence, no numeric explosion.

---

## 4. SQL Window Feature Engineering

Rolling features computed directly in PostgreSQL:

```sql
AVG(price) OVER (
    PARTITION BY route_key
    ORDER BY created_at
    ROWS BETWEEN N PRECEDING AND 1 PRECEDING
)
```

**CURRENT ROW explicitly excluded** — only strictly past data used.

Benefits: no Python iteration bottlenecks, horizontal scalability, strict temporal integrity.

---

## 5. Model Registry & Single Active Model

The `model_registry` table acts as an immutable versioned deployment log.

- Partial unique index enforces **only one** `deployed = TRUE`
- Historical rows never deleted
- Rollback supported via controlled version switch

---

## 6. Dynamic Model Hot Reload

The API periodically polls `model_registry`.

If `deployed_version_in_db != deployed_version_in_memory`:
- Model, metadata, and residual statistics atomically swapped
- No server restart required

---

## 7. Numeric Safety Guards

Before returning predictions:

| Guard | Action |
|-------|--------|
| `!isfinite(pred)` | HTTP 500 with error log |
| `pred < 0` | Absolute value correction |
| `pred > 200000` | Warning logged |
| Confidence interval | Route-level residual std |

---

## 8. Frontend Stability

- Outer containers control height, inner containers scroll
- Panels never resize siblings
- Stress test logs hard-capped at 4 rows
- Fixed-height deterministic dashboard
- Sequential inference simulation (16–200 runs)

---

## 9. Currency Integrity

All backend prices stored and trained in **EUR**.
Frontend performs display-only conversion (EUR ↔ INR).
Currency toggle does **not** affect model output.

---

## 10. CORS & Environment Safety

| Environment | CORS Policy |
|-------------|-------------|
| Development | `allow_origins = ["*"]` |
| Production | Explicit frontend domain only |

- No secrets hardcoded
- No `.env` files tracked in Git
- All logging via Python `logging` module

---

## Design Philosophy

The system prioritizes:
- Temporal integrity
- Deterministic deployment
- Explicit safeguards
- Auditability
- Operational resilience

*This is not a demo ML project. This is a controlled self-improving production pipeline with strict architectural constraints.*

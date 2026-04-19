"""
Train XGBoost Model for Task Priority Prediction
=================================================
Script ini melatih model XGBoost menggunakan dataset sintetis
dan menyimpan model yang sudah dilatih ke file .joblib

Cara pakai:
  python arva/ml_training/train_model.py

Output:
  arva/ml_models/priority_model.joblib
  arva/ml_models/feature_names.joblib
"""

import os
import sys
import csv
import json
import random

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATASET_FILE = os.path.join(SCRIPT_DIR, 'task_priority_dataset.csv')
MODEL_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), 'ml_models')


def check_dependencies():
    """Cek apakah library yang dibutuhkan sudah terinstall."""
    missing = []
    try:
        import numpy
    except ImportError:
        missing.append('numpy')
    try:
        import sklearn
    except ImportError:
        missing.append('scikit-learn')
    try:
        import xgboost
    except ImportError:
        missing.append('xgboost')
    try:
        import joblib
    except ImportError:
        missing.append('joblib')

    if missing:
        print(f"ERROR: Library berikut belum terinstall: {', '.join(missing)}")
        print(f"Jalankan: pip install {' '.join(missing)}")
        sys.exit(1)


def load_dataset(filepath):
    """Load dataset dari CSV."""
    features = []
    targets = []
    feature_names = None

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        feature_names = [
            'days_until_due', 'is_overdue', 'has_due_date',
            'checklist_total', 'checklist_done', 'checklist_ratio',
            'priority_encoded', 'num_assignees', 'num_labels',
            'description_len', 'title_len', 'task_age_days', 'status_encoded',
        ]
        for row in reader:
            feat = [float(row[name]) for name in feature_names]
            features.append(feat)
            targets.append(float(row['priority_score']))

    return features, targets, feature_names


def main():
    print("=" * 60)
    print("  Task Priority Model - Training Pipeline")
    print("=" * 60)

    # 1. Cek dependensi
    print("\n[1/6] Checking dependencies...")
    check_dependencies()
    print("      All dependencies OK")

    import numpy as np
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    from xgboost import XGBRegressor
    import joblib

    # 2. Load dataset
    print(f"\n[2/6] Loading dataset from {DATASET_FILE}...")
    features, targets, feature_names = load_dataset(DATASET_FILE)
    X = np.array(features)
    y = np.array(targets)
    print(f"      Loaded {len(X)} rows, {len(feature_names)} features")
    print(f"      Target range: {y.min():.0f} - {y.max():.0f} (avg: {y.mean():.1f})")

    # 3. Split data
    print("\n[3/6] Splitting data (80% train, 20% test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    print(f"      Train: {len(X_train)} rows")
    print(f"      Test:  {len(X_test)} rows")

    # 4. Training XGBoost
    print("\n[4/6] Training XGBoost model...")
    model = XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    print("      Training complete!")

    # 5. Evaluasi
    print("\n[5/6] Evaluating model...")
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)

    train_mae = mean_absolute_error(y_train, train_pred)
    test_mae = mean_absolute_error(y_test, test_pred)
    train_r2 = r2_score(y_train, train_pred)
    test_r2 = r2_score(y_test, test_pred)
    test_rmse = np.sqrt(((y_test - test_pred) ** 2).mean())

    print(f"\n      {'Metric':<20} {'Train':>10} {'Test':>10}")
    print(f"      {'-' * 42}")
    print(f"      {'MAE':<20} {train_mae:>10.2f} {test_mae:>10.2f}")
    print(f"      {'R2 Score':<20} {train_r2:>10.4f} {test_r2:>10.4f}")
    print(f"      {'RMSE':<20} {'':>10} {test_rmse:>10.2f}")

    # Evaluasi per level
    print(f"\n      Per-Level Accuracy (Test Set):")
    for level, (lo, hi) in [('Critical', (80, 101)), ('High', (60, 80)), ('Medium', (40, 60)), ('Low', (0, 40))]:
        mask = (y_test >= lo) & (y_test < hi)
        if mask.sum() > 0:
            level_mae = mean_absolute_error(y_test[mask], test_pred[mask])
            # Cek berapa persen prediksi yang masuk level yang benar
            pred_levels = np.array([
                'Critical' if p >= 80 else 'High' if p >= 60 else 'Medium' if p >= 40 else 'Low'
                for p in test_pred[mask]
            ])
            correct = (pred_levels == level).sum()
            accuracy = correct / mask.sum() * 100
            print(f"      {level:<10}: MAE={level_mae:.2f}, Level Accuracy={accuracy:.1f}% ({correct}/{mask.sum()})")

    # Feature importance
    print(f"\n      Feature Importance (Top 5):")
    importances = model.feature_importances_
    indices = np.argsort(importances)[::-1]
    for i in range(min(5, len(feature_names))):
        idx = indices[i]
        print(f"      {i+1}. {feature_names[idx]:<20} {importances[idx]:.4f}")

    # 6. Save model
    print(f"\n[6/6] Saving model...")
    os.makedirs(MODEL_DIR, exist_ok=True)

    model_path = os.path.join(MODEL_DIR, 'priority_model.joblib')
    names_path = os.path.join(MODEL_DIR, 'feature_names.joblib')

    joblib.dump(model, model_path)
    joblib.dump(feature_names, names_path)

    model_size = os.path.getsize(model_path) / 1024
    print(f"      Model saved: {model_path} ({model_size:.1f} KB)")
    print(f"      Features saved: {names_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  TRAINING COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Model        : XGBoost Regressor")
    print(f"  Features     : {len(feature_names)}")
    print(f"  Train MAE    : {train_mae:.2f}")
    print(f"  Test MAE     : {test_mae:.2f}")
    print(f"  Test R2      : {test_r2:.4f}")
    print(f"  Test RMSE    : {test_rmse:.2f}")
    print(f"  Model file   : {model_path}")

    status = "PASS" if test_mae < 10 and test_r2 > 0.80 else "REVIEW"
    print(f"\n  Status: {status}")
    if status == "PASS":
        print("  Model siap di-deploy ke Django!")
    else:
        print("  Model perlu tuning lebih lanjut atau data lebih banyak.")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()

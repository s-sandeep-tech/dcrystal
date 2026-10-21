from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from ..utils.logger import logger

class TabularPredictor:
    """XGBoost-based tabular prediction engine for delay risk, lead times, and multi-feature modeling."""

    def __init__(self):
        self.model = None
        self.feature_names: List[str] = []
        self._has_xgboost = False

        try:
            import xgboost as xgb
            self.xgb = xgb
            self._has_xgboost = True
        except Exception as e:
            logger.warning(f"XGBoost unavailable ({e}). Using sklearn/heuristic fallback.")
            self.xgb = None

    def train_or_fit(
        self,
        training_records: List[Dict[str, Any]],
        target_column: str = "delay_risk",
        feature_columns: Optional[List[str]] = None,
        is_classification: bool = False
    ) -> Dict[str, Any]:
        """
        Fits an XGBoost regressor or classifier on tabular records.
        """
        if not training_records:
            return {"status": "error", "message": "No training records provided"}

        df = pd.DataFrame(training_records)
        if target_column not in df.columns:
            return {"status": "error", "message": f"Target column '{target_column}' missing from training data"}

        # Prepare features
        y = pd.to_numeric(df[target_column], errors="coerce").fillna(0.0)
        X_df = df.drop(columns=[target_column], errors="ignore")
        if feature_columns:
            X_df = X_df[[c for c in feature_columns if c in X_df.columns]]

        # Encode categorical columns
        X_encoded = pd.get_dummies(X_df, drop_first=True)
        self.feature_names = list(X_encoded.columns)

        try:
            if self._has_xgboost:
                if is_classification:
                    self.model = self.xgb.XGBClassifier(
                        n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42
                    )
                else:
                    self.model = self.xgb.XGBRegressor(
                        n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42
                    )
            else:
                from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
                if is_classification:
                    self.model = RandomForestClassifier(n_estimators=100, random_state=42)
                else:
                    self.model = RandomForestRegressor(n_estimators=100, random_state=42)

            self.model.fit(X_encoded, y)

            # Feature importances
            importances = {}
            if hasattr(self.model, "feature_importances_"):
                for name, imp in zip(self.feature_names, self.model.feature_importances_):
                    importances[name] = round(float(imp), 4)

            return {
                "status": "success",
                "sample_count": len(df),
                "feature_count": len(self.feature_names),
                "feature_importances": dict(sorted(importances.items(), key=lambda x: x[1], reverse=True)[:10]),
                "engine": "xgboost" if self._has_xgboost else "sklearn_rf"
            }
        except Exception as e:
            logger.error(f"Error fitting tabular predictor: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def predict(
        self,
        records: List[Dict[str, Any]],
        prediction_type: str = "delay_risk"
    ) -> List[Dict[str, Any]]:
        """
        Generates predictions and risk scores for a list of entity records.
        """
        if not records:
            return []

        df = pd.DataFrame(records)
        predictions = []

        if self.model and self.feature_names:
            # Model exists; align dummy columns
            X_encoded = pd.get_dummies(df, drop_first=True)
            for f in self.feature_names:
                if f not in X_encoded.columns:
                    X_encoded[f] = 0
            X_aligned = X_encoded[self.feature_names]

            raw_preds = self.model.predict(X_aligned)
            for i, row in df.iterrows():
                val = float(raw_preds[i])
                risk = min(1.0, max(0.0, val / 100.0 if val > 1.0 else val))
                predictions.append({
                    "entity_id": str(row.get("order_id", row.get("id", f"item_{i}"))),
                    "entity_type": str(row.get("entity_type", "order")),
                    "prediction_type": prediction_type,
                    "predicted_value": round(val, 2),
                    "risk_score": round(risk, 4),
                    "confidence": 0.88,
                    "features": {k: row[k] for k in ["priority", "collection_type", "origin", "destination"] if k in row}
                })
        else:
            # Heuristic calculation if model is not pre-fitted
            for i, row in df.iterrows():
                # Heuristic risk based on common attributes
                priority = str(row.get("priority", "Normal")).lower()
                origin = str(row.get("origin", ""))
                dest = str(row.get("destination", ""))
                base_risk = float(row.get("risk_level", 15.0)) / 100.0

                if "urgent" in priority or "critical" in priority:
                    base_risk = min(1.0, base_risk + 0.25)
                if origin != dest and origin and dest:
                    base_risk = min(1.0, base_risk + 0.10)

                pred_val = round(base_risk * 100.0, 1)
                predictions.append({
                    "entity_id": str(row.get("order_id", row.get("id", f"item_{i}"))),
                    "entity_type": str(row.get("entity_type", "order")),
                    "prediction_type": prediction_type,
                    "predicted_value": pred_val,
                    "risk_score": round(base_risk, 4),
                    "confidence": 0.80,
                    "features": {k: row[k] for k in ["priority", "collection_type", "origin", "destination"] if k in row}
                })

        return predictions

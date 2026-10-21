from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from importlib.metadata import version
from sklearn.feature_extraction import DictVectorizer
from .model_store import ModelStore
from ..config import settings
from ..utils.logger import logger

class TabularPredictor:
    """XGBoost-based tabular prediction engine for delay risk, lead times, and multi-feature modeling."""

    def __init__(self, model_store_dir=None):
        self.model = None
        self.feature_names: List[str] = []
        self.encoder = None
        self.input_columns = []
        self.store = ModelStore(model_store_dir or settings.MODEL_STORE_DIR)
        self._has_xgboost = False

        try:
            import xgboost as xgb
            self.xgb = xgb
            self._has_xgboost = True
        except Exception as e:
            logger.warning(f"XGBoost unavailable ({e}). Using sklearn/heuristic fallback.")
            self.xgb = None

        bundle = self.store.load()
        if bundle:
            self.model = bundle["model"]
            self.encoder = bundle["encoder"]
            self.feature_names = bundle["feature_names"]
            self.input_columns = bundle["input_columns"]
            logger.info("Loaded persisted tabular predictor")
        else:
            logger.warning("No saved predictor; predictions use the heuristic until training succeeds")

    @staticmethod
    def _features(frame, columns):
        missing = set(columns) - set(frame.columns)
        if missing:
            raise ValueError(f"Missing model features: {sorted(missing)}")
        return [{key: (0.0 if pd.isna(value) else
                      float(value) if isinstance(value, (int, float, np.number)) else str(value))
                 for key, value in row.items()}
                for row in frame[columns].to_dict("records")]

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

        try:
            if feature_columns and set(feature_columns) - set(X_df.columns):
                raise ValueError("Requested training features are missing")
            input_columns = list(X_df.columns)
            encoder = DictVectorizer(sparse=False)
            X_encoded = encoder.fit_transform(self._features(X_df, input_columns))
            feature_names = list(encoder.get_feature_names_out())
            if self._has_xgboost:
                if is_classification:
                    model = self.xgb.XGBClassifier(
                        n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42
                    )
                else:
                    model = self.xgb.XGBRegressor(
                        n_estimators=100, max_depth=5, learning_rate=0.08, random_state=42
                    )
            else:
                from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
                if is_classification:
                    model = RandomForestClassifier(n_estimators=100, random_state=42)
                else:
                    model = RandomForestRegressor(n_estimators=100, random_state=42)

            model.fit(X_encoded, y)

            # Feature importances
            importances = {}
            if hasattr(model, "feature_importances_"):
                for name, imp in zip(feature_names, model.feature_importances_):
                    importances[name] = round(float(imp), 4)

            engine = "xgboost" if self._has_xgboost else "scikit-learn"
            model_id = self.store.save({
                "schema_version": 1, "model": model, "encoder": encoder,
                "feature_names": feature_names, "input_columns": input_columns,
                "target_column": target_column, "is_classification": is_classification,
                "engine_version": [engine, version(engine)]
            })
            self.model, self.encoder = model, encoder
            self.feature_names, self.input_columns = feature_names, input_columns

            return {
                "status": "success",
                "model_id": model_id,
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
            X_aligned = self.encoder.transform(self._features(df, self.input_columns))

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

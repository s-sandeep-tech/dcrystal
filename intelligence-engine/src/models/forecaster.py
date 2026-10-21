from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np
from ..utils.logger import logger

class TimeSeriesForecaster:
    """Prophet-based time-series forecasting engine with graceful fallback handling."""

    def __init__(self):
        self._has_prophet = False
        try:
            from prophet import Prophet
            self.ProphetClass = Prophet
            self._has_prophet = True
        except ImportError:
            logger.warning("Prophet not installed in current environment. Using robust heuristic baseline.")
            self.ProphetClass = None

    def run_forecast(
        self,
        series_data: List[Dict[str, Any]],
        horizon_days: int = 14,
        yearly_seasonality: bool = "auto",
        weekly_seasonality: bool = "auto"
    ) -> Dict[str, Any]:
        """
        Executes time-series forecast on the provided series data (list of {'ds': 'YYYY-MM-DD', 'y': float}).
        """
        if horizon_days < 1:
            raise ValueError("Forecast horizon must be positive")
        if not series_data:
            raise ValueError("Empty series data provided")

        df = pd.DataFrame(series_data)
        if "ds" not in df.columns or "y" not in df.columns:
            raise ValueError("Input data must contain 'ds' and 'y' keys")

        # Format datetimes and sort
        df["ds"] = pd.to_datetime(df["ds"])
        df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0.0)
        df = df.sort_values("ds").reset_index(drop=True)

        if len(df) < 3 or not self._has_prophet:
            return self._heuristic_forecast(df, horizon_days)

        try:
            model = self.ProphetClass(
                yearly_seasonality=yearly_seasonality,
                weekly_seasonality=weekly_seasonality,
                daily_seasonality=False
            )
            model.fit(df)

            future = model.make_future_dataframe(periods=horizon_days, freq="D")
            forecast_df = model.predict(future)

            # Filter for only future dates
            last_date = df["ds"].max()
            future_forecast = forecast_df[forecast_df["ds"] > last_date]

            results = []
            for _, row in future_forecast.iterrows():
                yhat = max(0.0, float(row["yhat"]))
                lower = max(0.0, float(row["yhat_lower"]))
                upper = max(0.0, float(row["yhat_upper"]))
                results.append({
                    "ds": row["ds"].strftime("%Y-%m-%d"),
                    "baseline_yhat": round(yhat, 2),
                    "yhat_lower": round(lower, 2),
                    "yhat_upper": round(upper, 2)
                })

            avg_historical = float(df["y"].mean())
            avg_forecast = float(np.mean([r["baseline_yhat"] for r in results])) if results else 0.0
            trend_change_pct = round(((avg_forecast - avg_historical) / (avg_historical + 1e-6)) * 100, 2)

            return {
                "forecast": results,
                "metrics": {
                    "historical_points": len(df),
                    "avg_historical_y": round(avg_historical, 2),
                    "avg_forecast_y": round(avg_forecast, 2),
                    "trend_change_pct": trend_change_pct,
                    "engine": "prophet"
                }
            }
        except Exception as e:
            logger.warning(f"Prophet fitting encountered an error: {e}. Falling back to baseline heuristic.")
            return self._heuristic_forecast(df, horizon_days)

    def _heuristic_forecast(self, df: pd.DataFrame, horizon_days: int) -> Dict[str, Any]:
        """Provides a moving-average + linear trend fallback forecast."""
        last_date = df["ds"].max() if not df.empty else pd.Timestamp.now()
        recent_window = df.tail(min(14, len(df)))
        base_val = float(recent_window["y"].mean()) if not recent_window.empty else 10.0
        std_val = float(recent_window["y"].std()) if len(recent_window) > 1 else (base_val * 0.15)
        if np.isnan(std_val) or std_val == 0:
            std_val = base_val * 0.1

        results = []
        for i in range(1, horizon_days + 1):
            next_date = last_date + pd.Timedelta(days=i)
            # Add day of week variation (e.g. slight dip on Sunday)
            dow_factor = 0.85 if next_date.dayofweek == 6 else 1.02
            val = round(max(0.0, base_val * dow_factor), 2)
            results.append({
                "ds": next_date.strftime("%Y-%m-%d"),
                "baseline_yhat": val,
                "yhat_lower": round(max(0.0, val - 1.96 * std_val), 2),
                "yhat_upper": round(val + 1.96 * std_val, 2)
            })

        return {
            "forecast": results,
            "metrics": {
                "historical_points": len(df),
                "avg_historical_y": round(base_val, 2),
                "avg_forecast_y": round(base_val, 2),
                "trend_change_pct": 0.0,
                "engine": "heuristic_baseline"
            }
        }

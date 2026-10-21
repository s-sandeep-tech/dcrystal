from typing import Dict, Any, List, Optional
from ..models.forecaster import TimeSeriesForecaster
from ..external.gemini_enricher import GeminiExternalEnricher
from ..db.writer import DatabaseWriter
from ..utils.logger import logger

class HybridIntelligenceOrchestrator:
    """
    Synthesizes quantitative time-series models (Prophet) with external qualitative signals
    (Gemini API climate alerts, disruption factors).
    """

    def __init__(self):
        self.forecaster = TimeSeriesForecaster()
        self.enricher = GeminiExternalEnricher()

    def run_hybrid_forecast(
        self,
        task_id: str,
        metric_name: str,
        series_data: List[Dict[str, Any]],
        horizon_days: int = 14,
        region: str = "India",
        external_factors: Optional[List[str]] = None,
        dimension: Optional[str] = None,
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Executes Prophet forecast, fetches Gemini context, applies multipliers, and persists to DB.
        """
        logger.info(f"Running hybrid forecast for task {task_id} (metric: {metric_name}, horizon: {horizon_days}d)")

        # 1. Internal Quantitative Forecast (Prophet)
        forecast_output = self.forecaster.run_forecast(series_data, horizon_days=horizon_days)
        baseline_forecast = forecast_output.get("forecast", [])
        metrics = forecast_output.get("metrics", {})

        # 2. External Qualitative Context (Gemini API)
        external_context = self.enricher.analyze_external_context(
            region=region,
            specific_factors=external_factors
        )
        multiplier = float(external_context.get("impact_multiplier", 1.0))

        # 3. Hybrid Synthesis: Apply multiplier to baseline intervals
        adjusted_forecast = []
        for item in baseline_forecast:
            base_yhat = item["baseline_yhat"]
            adj_yhat = round(base_yhat * multiplier, 2)
            adj_lower = round(item["yhat_lower"] * multiplier, 2)
            adj_upper = round(item["yhat_upper"] * multiplier, 2)

            adjusted_forecast.append({
                "ds": item["ds"],
                "baseline_yhat": base_yhat,
                "adjusted_yhat": adj_yhat,
                "yhat_lower": adj_lower,
                "yhat_upper": adj_upper,
                "external_multiplier": multiplier
            })

        # 4. Save to Exclusive Database Tables
        if save_to_db:
            DatabaseWriter.save_forecasts(
                task_id=task_id,
                metric_name=metric_name,
                forecast_items=adjusted_forecast,
                dimension=dimension
            )
            DatabaseWriter.save_external_signal(
                event_type=external_context.get("event_type", "climate"),
                summary=external_context.get("summary", ""),
                region=region,
                severity=external_context.get("severity", "medium"),
                impact_direction=external_context.get("impact_direction", "neutral"),
                impact_multiplier=multiplier,
                raw_response=external_context
            )

        return {
            "task_id": task_id,
            "metric_name": metric_name,
            "horizon_days": horizon_days,
            "region": region,
            "forecast": adjusted_forecast,
            "external_context": external_context,
            "metrics": metrics
        }

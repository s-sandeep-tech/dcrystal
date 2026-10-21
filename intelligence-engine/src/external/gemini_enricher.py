import json
import os
from typing import Dict, Any, List, Optional
from ..config import settings
from ..utils.logger import logger

class GeminiExternalEnricher:
    """Queries Google Gemini API for external climate, seasonal, and logistics risk factors."""

    def __init__(self):
        self.api_key = (
            getattr(settings, "active_gemini_api_key", None)
            or os.getenv("INTELLIGENCE_GEMINI_API_KEY")
            or settings.GEMINI_API_KEY
            or os.getenv("GEMINI_API_KEY")
        )
        self.model_name = settings.GEMINI_MODEL
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"Gemini client initialized with model {self.model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize google.genai client: {e}")
        else:
            logger.info("INTELLIGENCE_GEMINI_API_KEY not configured. Running in offline heuristic mode.")


    def analyze_external_context(
        self,
        region: str = "India",
        industry: str = "jewelry_manufacturing_and_retail",
        specific_factors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyzes external climate and regional events impacting production, fulfillment, or demand.
        Returns a structured dictionary with impact multiplier and summary.
        """
        factors_str = ", ".join(specific_factors) if specific_factors else "weather disruptions, seasonal demand, festivals, transport bottlenecks"

        prompt = f"""
You are an expert supply chain intelligence advisor for {industry} in {region}.
Assess external climate events, weather disruptions, seasonal shopping patterns, or transit risks for the current timeframe.
Focus on: {factors_str}.

You MUST return ONLY a valid JSON object with the following schema:
{{
  "event_type": "climate" | "festival" | "logistics" | "macro",
  "region": "{region}",
  "severity": "low" | "medium" | "high" | "critical",
  "impact_direction": "positive" | "negative" | "neutral",
  "impact_multiplier": float between 0.60 and 1.40 (where 1.0 is neutral, <1.0 decreases throughput/fulfillment, >1.0 increases demand),
  "summary": "1-2 sentence executive summary of external conditions",
  "recommendation": "1 sentence operational guidance"
}}
Return raw JSON only, without markdown quotes or backticks.
"""
        if self.client:
            import time
            # Resilient fallback across active Gemini models
            candidate_models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest"]
            if self.model_name and self.model_name not in candidate_models:
                candidate_models.insert(0, self.model_name)

            for target_model in candidate_models:
                for attempt in range(2):
                    try:
                        response = self.client.models.generate_content(
                            model=target_model,
                            contents=prompt
                        )
                        text = response.text.strip()
                        # Clean up any markdown blocks if returned
                        if text.startswith("```"):
                            text = text.strip("`")
                            if text.startswith("json"):
                                text = text[4:].strip()

                        parsed = json.loads(text)
                        parsed["model_used"] = target_model
                        return parsed
                    except Exception as e:
                        if "503" in str(e) and attempt == 0:
                            time.sleep(1.5)
                            continue
                        logger.warning(f"Gemini API request with {target_model} failed: {e}. Trying next model...")
                        break

        # Default fallback context when offline or API key is not supplied
        return self._offline_fallback_context(region, specific_factors)



    def _offline_fallback_context(self, region: str, specific_factors: Optional[List[str]]) -> Dict[str, Any]:
        """Deterministic offline fallback factor calculation."""
        factors = [f.lower() for f in (specific_factors or [])]
        multiplier = 1.0
        event_type = "climate"
        severity = "medium"
        direction = "neutral"
        summary = f"Normal operational conditions observed for {region}."

        if any("monsoon" in f or "rain" in f or "storm" in f for f in factors):
            multiplier = 0.88
            event_type = "climate"
            severity = "high"
            direction = "negative"
            summary = "Monsoon weather events may cause localized transit delays of 24-48 hours."
        elif any("diwali" in f or "festival" in f or "festive" in f for f in factors):
            multiplier = 1.25
            event_type = "festival"
            severity = "high"
            direction = "positive"
            summary = "Festival seasonal surge expected; showroom order demand estimated +25%."

        return {
            "event_type": event_type,
            "region": region,
            "severity": severity,
            "impact_direction": direction,
            "impact_multiplier": multiplier,
            "summary": summary,
            "recommendation": "Maintain standard safety inventory buffers and monitor delivery SLAs.",
            "mode": "offline_fallback"
        }

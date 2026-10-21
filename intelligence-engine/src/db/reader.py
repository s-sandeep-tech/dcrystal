from datetime import datetime, date
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from ..db.connection import engine
from ..utils.logger import logger

class DatabaseReader:
    """Safely extracts historical data and features from Postgres for ML training and inference."""

    @staticmethod
    def get_order_timeseries(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        dimension: Optional[str] = None,
        dimension_value: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Fetches daily aggregated order counts suitable for Prophet forecasting ('ds', 'y').
        """
        clauses = ["created_at IS NOT NULL"]
        params = {"limit": limit}

        if start_date:
            clauses.append("created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("created_at <= :end_date")
            params["end_date"] = end_date
        if dimension and dimension_value and dimension.isalnum():
            clauses.append(f"{dimension} = :dim_val")
            params["dim_val"] = dimension_value

        where_stmt = " AND ".join(clauses)

        query = f"""
            SELECT 
                DATE(created_at) as ds,
                COUNT(*)::float as y
            FROM orders
            WHERE {where_stmt}
            GROUP BY DATE(created_at)
            ORDER BY ds ASC
            LIMIT :limit
        """

        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = [
                    {"ds": r.ds.isoformat() if isinstance(r.ds, (date, datetime)) else str(r.ds), "y": float(r.y)}
                    for r in result
                ]
                return rows
        except Exception as e:
            logger.warning(f"Error querying orders timeseries (table might be empty or unavailable): {e}")
            raise

    @staticmethod
    def get_tabular_orders_for_prediction(
        status: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Fetches tabular records from 'orders' for XGBoost feature prediction.
        """
        clauses = []
        params = {"limit": limit}

        if status:
            clauses.append("status = :status")
            params["status"] = status

        where_stmt = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        query = f"""
            SELECT 
                order_id,
                COALESCE(priority, 'Normal') as priority,
                COALESCE(collection_type, 'General') as collection_type,
                COALESCE(sub_type, 'Standard') as sub_type,
                COALESCE(origin, 'Central') as origin,
                COALESCE(destination, 'Branch') as destination,
                COALESCE(risk_level, 0) as risk_level,
                status,
                created_at
            FROM orders
            {where_stmt}
            ORDER BY id DESC
            LIMIT :limit
        """

        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = [dict(r._mapping) for r in result]
                return rows
        except Exception as e:
            logger.warning(f"Error querying tabular orders (table might be empty or schema differing): {e}")
            raise

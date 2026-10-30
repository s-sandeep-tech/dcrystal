ALTER TABLE sales_stock_composition_analysis_snapshots
    ADD COLUMN IF NOT EXISTS min_trans_date DATE;

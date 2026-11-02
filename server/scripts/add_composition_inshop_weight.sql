ALTER TABLE sales_stock_composition_analysis_snapshots
    ADD COLUMN IF NOT EXISTS inshop_weight NUMERIC(15, 4);

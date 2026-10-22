ALTER TABLE sales_turnover_daily_snapshots
ADD COLUMN IF NOT EXISTS state_name varchar(100);

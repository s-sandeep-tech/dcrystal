-- Additive migration. No existing sales history or predictions are removed.
BEGIN;
CREATE TABLE IF NOT EXISTS sales_external_features (
    id varchar(64) PRIMARY KEY,
    scope varchar(100) NOT NULL,
    feature_date date NOT NULL,
    feature_group varchar(30) NOT NULL,
    available_at timestamptz NOT NULL,
    retrieved_at timestamptz NOT NULL,
    provider varchar(100) NOT NULL,
    values_json json NOT NULL,
    source text NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sales_features_lookup
ON sales_external_features (scope, feature_group, feature_date, available_at);
CREATE TABLE IF NOT EXISTS sales_external_fetch_logs (
    id serial PRIMARY KEY,
    task_id varchar(100),
    created_at timestamptz NOT NULL,
    event_json json NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sales_external_fetch_logs_task_id ON sales_external_fetch_logs (task_id);
CREATE TABLE IF NOT EXISTS sales_forecast_feature_inputs (
    task_id varchar(100) PRIMARY KEY,
    created_at timestamptz NOT NULL,
    inputs_json json NOT NULL
);
COMMIT;

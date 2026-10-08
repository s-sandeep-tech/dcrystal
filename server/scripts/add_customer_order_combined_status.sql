ALTER TABLE public.customer_order_analysis_snapshot
ADD COLUMN IF NOT EXISTS combine_order_status TEXT;

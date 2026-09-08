-- Run against the local application database while owner-wise sync is stopped.
-- Preserves existing records. Run a full owner-wise sync afterwards.
BEGIN;
ALTER TABLE owner_wise_order_summary_snapshot
    ADD COLUMN IF NOT EXISTS customer_order_type text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS is_discount_party text NOT NULL DEFAULT '';

DO $$
DECLARE
    constraint_name text;
    key_columns text;
BEGIN
    SELECT c.conname, string_agg(quote_ident(a.attname), ', ' ORDER BY k.ordinality)
    INTO constraint_name, key_columns
    FROM pg_constraint c
    CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, ordinality)
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.conrelid = 'owner_wise_order_summary_snapshot'::regclass
      AND c.contype = 'p'
    GROUP BY c.conname;
    IF constraint_name IS NULL THEN
        RAISE EXCEPTION 'Snapshot primary key missing; inspect schema before proceeding';
    END IF;
    -- Preserve existing key columns, extending only with the missing dimensions.
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c JOIN pg_attribute a
        ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.conrelid = 'owner_wise_order_summary_snapshot'::regclass
        AND c.contype = 'p' AND a.attname = 'customer_order_type'
    ) THEN key_columns := key_columns || ', customer_order_type'; END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint c JOIN pg_attribute a
        ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.conrelid = 'owner_wise_order_summary_snapshot'::regclass
        AND c.contype = 'p' AND a.attname = 'is_discount_party'
    ) THEN key_columns := key_columns || ', is_discount_party'; END IF;
    EXECUTE format('ALTER TABLE owner_wise_order_summary_snapshot DROP CONSTRAINT %I, ADD CONSTRAINT %I PRIMARY KEY (%s)', constraint_name, constraint_name, key_columns);
END $$;
COMMIT;

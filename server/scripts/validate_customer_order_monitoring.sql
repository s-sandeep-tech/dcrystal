-- Read-only checks against the local snapshot before production sign-off.
-- Repeated SOOCs require review: exact business duplicates are deduplicated by
-- the dashboard; conflicting rows cause a validation error rather than totals.
SELECT sooc, COUNT(*) AS rows,
       COUNT(DISTINCT (branch_id, request_no)) AS request_combinations
FROM customer_order_analysis_snapshot
WHERE NULLIF(TRIM(sooc), '') IS NOT NULL
GROUP BY sooc HAVING COUNT(*) > 1
ORDER BY rows DESC;

SELECT COUNT(*) AS rows,
       COUNT(*) FILTER (WHERE NULLIF(TRIM(sooc), '') IS NULL) AS missing_sooc,
       COUNT(*) FILTER (WHERE NULLIF(TRIM(request_no), '') IS NULL) AS missing_request,
       COUNT(*) FILTER (WHERE expected_delivery_date IS NULL) AS missing_delivery_date
FROM customer_order_analysis_snapshot;

-- Keep these measures separate; this query is not a combined outstanding total.
SELECT order_status, COUNT(DISTINCT request_no) AS requests,
       SUM(total_pending_pcs) AS production_pcs,
       SUM(total_pending_wt) AS production_wt,
       SUM(customer_order_approval_pending_pcs) AS approval_pcs,
       SUM(customer_order_approval_pending_wt) AS approval_wt,
       SUM(customer_delivery_pending_pcs) AS delivery_pcs,
       SUM(customer_delivery_pending_wt) AS delivery_wt
FROM customer_order_analysis_snapshot
GROUP BY order_status ORDER BY order_status;

-- Check whether request numbers recur across branches.
SELECT request_no, COUNT(DISTINCT branch_id) AS branches
FROM customer_order_analysis_snapshot
WHERE NULLIF(TRIM(request_no), '') IS NOT NULL
GROUP BY request_no HAVING COUNT(DISTINCT branch_id) > 1;

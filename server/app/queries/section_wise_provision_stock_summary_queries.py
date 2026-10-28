class SectionWiseProvisionStockSummaryQuery:
    """SQL queries owned exclusively by the Section-wise Provision and Stock Summary report."""

    LATEST_SNAPSHOT_DATE = """
SELECT MAX(snapshot_date) AS snapshot_date
FROM provision_stock_raw_snapshot
    """

    AUTHORIZED_BRANCH_IDS = """
SELECT branch_id
FROM branch_authority_snapshot
WHERE emp_code = :emp_code
ORDER BY branch_id
    """

    FILTER_OPTIONS = """
SELECT
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT division ORDER BY division), NULL) AS divisions,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT location ORDER BY location), NULL) AS locations,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT purity ORDER BY purity), NULL) AS purities,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT classification ORDER BY classification), NULL) AS classifications,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT section ORDER BY section), NULL) AS sections,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT prov_type ORDER BY prov_type), NULL) AS prov_types,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT provision_mode_filter ORDER BY provision_mode_filter), NULL) AS provision_modes,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT branch_type ORDER BY branch_type), NULL) AS branch_types,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT branch_status ORDER BY branch_status), NULL) AS branch_statuses,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT business_head_name ORDER BY business_head_name), NULL) AS business_heads,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT state ORDER BY state), NULL) AS states
FROM provision_stock_raw_snapshot
WHERE (:branch_type IS NULL OR branch_type = :branch_type)
  AND (:business_head_emp_code IS NULL OR business_head_emp_code = :business_head_emp_code)
  AND (:authorized_branch_ids IS NULL OR branch_id = ANY(
      string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]
  ))
  AND NOT :deny_all
    """

    SEARCH_COLLECTIONS = """
SELECT DISTINCT collection AS value
FROM provision_stock_raw_snapshot
WHERE collection IS NOT NULL
  AND (:search IS NULL OR collection ILIKE :search)
  AND (:division IS NULL OR UPPER(division) = ANY(string_to_array(UPPER(CAST(:division AS text)), ',')))
  AND (:branch_type IS NULL OR branch_type = :branch_type)
  AND (:business_head_emp_code IS NULL OR business_head_emp_code = :business_head_emp_code)
  AND (:authorized_branch_ids IS NULL OR branch_id = ANY(
      string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]
  ))
  AND NOT :deny_all
ORDER BY collection
LIMIT 50
    """

    SEARCH_MAKES = """
SELECT DISTINCT make AS value
FROM provision_stock_raw_snapshot
WHERE make IS NOT NULL
  AND (:search IS NULL OR make ILIKE :search)
  AND (:division IS NULL OR UPPER(division) = ANY(string_to_array(UPPER(CAST(:division AS text)), ',')))
  AND (:branch_type IS NULL OR branch_type = :branch_type)
  AND (:business_head_emp_code IS NULL OR business_head_emp_code = :business_head_emp_code)
  AND (:authorized_branch_ids IS NULL OR branch_id = ANY(
      string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]
  ))
  AND NOT :deny_all
ORDER BY make
LIMIT 50
    """

    SUMMARY = r"""
WITH base AS (
    SELECT 
        COALESCE(section, 'Unknown') AS section,
        COALESCE(make, 'Unknown') AS make,
        COALESCE(collection, 'Unknown') AS collection,
        COALESCE(type, 'Unknown') AS type,
        COALESCE(wide_range, 'Unknown') AS wide_range,
        prov_pieces,
        prov_gr_wt,
        in_shop_wt,
        in_transit_wt,
        short_pcs,
        excess_pcs,
        not_in_prov_pcs,
        short_gr_wt,
        excess_gr_weight,
        not_in_prov_gr_weight,
        short_percent,
        order_only_wt,
        req_only
    FROM provision_stock_raw_snapshot
    WHERE 
        (:location IS NULL OR location = ANY(string_to_array(CAST(:location AS text), ',')))
        AND (:division IS NULL OR UPPER(division) = ANY(string_to_array(UPPER(CAST(:division AS text)), ',')))
        AND (:state IS NULL OR state = ANY(string_to_array(CAST(:state AS text), ',')))
        AND (:purity IS NULL OR purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
        AND (:classification IS NULL OR classification = ANY(string_to_array(CAST(:classification AS text), ',')))
        AND (:make IS NULL OR make = ANY(string_to_array(CAST(:make AS text), ',')))
        AND (:collection IS NULL OR collection = ANY(string_to_array(CAST(:collection AS text), ',')))
        AND (:section IS NULL OR section = ANY(string_to_array(CAST(:section AS text), ',')))
        AND (:prov_type IS NULL OR prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
        AND (:provision_mode IS NULL OR provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
        AND (:branch_type IS NULL OR branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
        AND (:branch_status IS NULL OR branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
        AND (:business_head IS NULL OR business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
        AND (:bh_emp_code IS NULL OR business_head_emp_code = :bh_emp_code)
        AND (:authorized_branch_ids IS NULL OR branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
)
SELECT 
    5 - (GROUPING(section) + GROUPING(make) + GROUPING(collection) + GROUPING(type) + GROUPING(wide_range)) AS level_id,
    section,
    make,
    collection,
    type,
    wide_range,
    SUM(COALESCE(prov_pieces, 0)) AS prov_pcs,
    ROUND(SUM(COALESCE(prov_gr_wt, 0)), 3) AS prov_gr_wt,
    ROUND(SUM(COALESCE(in_shop_wt, 0)), 3) AS in_shop_wt,
    ROUND(SUM(COALESCE(in_transit_wt, 0)), 3) AS in_transit_wt,
    SUM(COALESCE(short_pcs, 0)) AS short_pcs,
    SUM(COALESCE(excess_pcs, 0) + COALESCE(not_in_prov_pcs, 0)) AS excess_pcs,
    ROUND(
        CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0
        ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
    ) AS short_percent,
    ROUND(SUM(COALESCE(short_gr_wt, 0)), 3) AS short_wt,
    ROUND(SUM(COALESCE(excess_gr_weight, 0) + COALESCE(not_in_prov_gr_weight, 0)), 3) AS excess_wt,
    ROUND(SUM(COALESCE(excess_gr_weight, 0) + COALESCE(not_in_prov_gr_weight, 0)) - SUM(COALESCE(short_gr_wt, 0)), 3) AS net_short_excess,
    ROUND(SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)), 3) AS ordered_wt
FROM base
GROUP BY ROLLUP (section, make, collection, type, wide_range)
ORDER BY 
    GROUPING(section) DESC,
    section, 
    make NULLS FIRST, 
    collection NULLS FIRST, 
    type NULLS FIRST, 
    wide_range NULLS FIRST
    """


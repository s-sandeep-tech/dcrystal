class LocationProvisionStockAnalysisQuery:
    """SQL owned exclusively by the Location Provision & Stock Analysis report."""

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
    SELECT *
    FROM provision_stock_raw_snapshot
    WHERE 
        (:location IS NULL OR location = ANY(string_to_array(CAST(:location AS text), ',')))
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
),
location_summary AS (
    SELECT
        location::text AS location,
        'Location Summary'::text AS report_section,
        location::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        SUM(prov_pieces) AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(COALESCE(short_pcs, 0)) AS short_pcs,
        SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
        SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
        SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
        ROUND(
            CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
        ) AS short_percent,
        1 AS section_sort,
        1 AS row_sort
    FROM base
    GROUP BY location
),
purity_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Purity Wise'::text AS report_section,
        purity::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(COALESCE(short_pcs, 0)) AS short_pcs,
        SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
        SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
        SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
        ROUND(
            CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
        ) AS short_percent,
        2 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY purity) AS row_sort
    FROM base
    GROUP BY purity
),
classification_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        x.report_section,
        x.report_label,
        x.classification,
        x.sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        x.is_parent,
        x.prov_pcs,
        x.prov_gr_wt,
        x.in_shop_wt,
        x.ordered_wt,
        x.in_transit_wt,
        x.short_pcs,
        x.excess_pcs,
        x.short_wt,
        x.excess_wt,
        x.short_percent,
        3 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY x.classification, x.level_order, x.sub_classification NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Classification Wise'::text AS report_section,
            classification::text AS report_label,
            classification::text AS classification,
            NULL::text AS sub_classification,
            1 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(COALESCE(short_pcs, 0)) AS short_pcs,
            SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
            SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
            SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
            ROUND(
                CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
            ) AS short_percent,
            0 AS level_order
        FROM base
        GROUP BY classification

        UNION ALL

        SELECT
            'Classification Wise'::text AS report_section,
            '   ' || COALESCE(sub_classification::text, 'Unknown') AS report_label,
            classification::text AS classification,
            COALESCE(sub_classification::text, 'Unknown') AS sub_classification,
            0 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(COALESCE(short_pcs, 0)) AS short_pcs,
            SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
            SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
            SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
            ROUND(
                CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
            ) AS short_percent,
            1 AS level_order
        FROM base
        GROUP BY classification, sub_classification
    ) x
),
collection_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        x.report_section,
        x.report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        x.collection,
        x.sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        x.is_parent,
        x.prov_pcs,
        x.prov_gr_wt,
        x.in_shop_wt,
        x.ordered_wt,
        x.in_transit_wt,
        x.short_pcs,
        x.excess_pcs,
        x.short_wt,
        x.excess_wt,
        x.short_percent,
        10 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY x.collection, x.level_order, x.sub_section NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Collection Wise'::text AS report_section,
            collection::text AS report_label,
            collection::text AS collection,
            NULL::text AS sub_section,
            1 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(COALESCE(short_pcs, 0)) AS short_pcs,
            SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
            SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
            SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
            ROUND(
                CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
            ) AS short_percent,
            0 AS level_order
        FROM base
        GROUP BY collection

        UNION ALL

        SELECT
            'Collection Wise'::text AS report_section,
            '   ' || COALESCE(sub_section::text, 'Unknown') AS report_label,
            collection::text AS collection,
            COALESCE(sub_section::text, 'Unknown') AS sub_section,
            0 AS is_parent,
            NULL::numeric AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(COALESCE(short_pcs, 0)) AS short_pcs,
            SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
            SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
            SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
            ROUND(
                CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
            ) AS short_percent,
            1 AS level_order
        FROM base
        GROUP BY collection, sub_section
    ) x
),
section_details_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        x.report_section,
        x.report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        x.sec_name,
        x.typ_name,
        x.is_parent,
        x.prov_pcs,
        x.prov_gr_wt,
        x.in_shop_wt,
        x.ordered_wt,
        x.in_transit_wt,
        x.short_pcs,
        x.excess_pcs,
        x.short_wt,
        x.excess_wt,
        x.short_percent,
        9 AS section_sort,
        ROW_NUMBER() OVER (
            ORDER BY x.sec_name, x.level_order, x.typ_name NULLS FIRST
        ) AS row_sort
    FROM (
        SELECT
            'Section Details'::text AS report_section,
            section::text AS report_label,
            section::text AS sec_name,
            NULL::text AS typ_name,
            1 AS is_parent,
            SUM(prov_pieces) AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(COALESCE(short_pcs, 0)) AS short_pcs,
            SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
            SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
            SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
            ROUND(
                CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
            ) AS short_percent,
            0 AS level_order
        FROM base
        GROUP BY section

        UNION ALL

        SELECT
            'Section Details'::text AS report_section,
            '   ' || COALESCE(type::text, 'Unknown') AS report_label,
            section::text AS sec_name,
            COALESCE(type::text, 'Unknown') AS typ_name,
            0 AS is_parent,
            SUM(prov_pieces) AS prov_pcs,
            SUM(prov_gr_wt) AS prov_gr_wt,
            SUM(in_shop_wt) AS in_shop_wt,
            SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
            SUM(in_transit_wt) AS in_transit_wt,
            SUM(COALESCE(short_pcs, 0)) AS short_pcs,
            SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
            SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
            SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
            ROUND(
                CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
            ) AS short_percent,
            1 AS level_order
        FROM base
        GROUP BY section, type
    ) x
),
make_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Make Wise'::text AS report_section,
        make::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(COALESCE(short_pcs, 0)) AS short_pcs,
        SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
        SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
        SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
        ROUND(
            CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
        ) AS short_percent,
        5 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY make) AS row_sort
    FROM base
    GROUP BY make
),
prov_type_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Provision Type Wise'::text AS report_section,
        prov_type::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(COALESCE(short_pcs, 0)) AS short_pcs,
        SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
        SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
        SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
        ROUND(
            CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
        ) AS short_percent,
        6 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY prov_type) AS row_sort
    FROM base
    GROUP BY prov_type
),
section_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Section Wise'::text AS report_section,
        section::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        SUM(prov_pieces) AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(COALESCE(short_pcs, 0)) AS short_pcs,
        SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
        SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
        SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
        ROUND(
            CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
        ) AS short_percent,
        7 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY section) AS row_sort
    FROM base
    GROUP BY section
),
provision_mode_wise AS (
    SELECT
        'SUMMARY'::text AS location,
        'Provision Mode Wise'::text AS report_section,
        provision_mode_filter::text AS report_label,
        NULL::text AS classification,
        NULL::text AS sub_classification,
        NULL::text AS collection,
        NULL::text AS sub_section,
        NULL::text AS sec_name,
        NULL::text AS typ_name,
        1 AS is_parent,
        NULL::numeric AS prov_pcs,
        SUM(prov_gr_wt) AS prov_gr_wt,
        SUM(in_shop_wt) AS in_shop_wt,
        SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
        SUM(in_transit_wt) AS in_transit_wt,
        SUM(COALESCE(short_pcs, 0)) AS short_pcs,
        SUM(COALESCE(excess_pcs, 0)) AS excess_pcs,
        SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
        SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
        ROUND(
            CASE WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0 ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) / SUM(COALESCE(prov_gr_wt, 0)) END, 2
        ) AS short_percent,
        8 AS section_sort,
        ROW_NUMBER() OVER (ORDER BY provision_mode_filter) AS row_sort
    FROM base
    GROUP BY provision_mode_filter
),
combined_report AS (
    SELECT * FROM location_summary
    UNION ALL
    SELECT * FROM purity_wise
    UNION ALL
    SELECT * FROM classification_wise
    UNION ALL
    SELECT * FROM collection_wise
    UNION ALL
    SELECT * FROM make_wise
    UNION ALL
    SELECT * FROM prov_type_wise
    UNION ALL
    SELECT * FROM section_wise
    UNION ALL
    SELECT * FROM provision_mode_wise
    UNION ALL
    SELECT * FROM section_details_wise
)

SELECT
    location,
    report_section,
    report_label,
    classification,
    sub_classification,
    collection,
    sub_section,
    sec_name,
    typ_name,
    is_parent,
    prov_pcs,
    prov_gr_wt,
    in_shop_wt,
    ordered_wt,
    in_transit_wt,
    short_pcs,
    excess_pcs,
    short_wt,
    excess_wt,
    short_percent,
    section_sort,
    row_sort
FROM combined_report
ORDER BY
    location,
    section_sort,
    row_sort        """

    DRILLDOWN = r"""
WITH base AS (
    SELECT *
    FROM provision_stock_raw_snapshot
    WHERE 
        (:location IS NULL OR location = ANY(string_to_array(CAST(:location AS text), ',')))
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
        AND (:drill_section IS NULL OR section = :drill_section)
),
levels AS (
    -- Level 1: Section
    SELECT 1 as level_id, section, NULL::numeric as purity, NULL::text as type,
           NULL::text as wide_range, NULL::numeric as range_weight,
           array_to_string(array_agg(DISTINCT section_id) FILTER (WHERE section_id IS NOT NULL), ',') as section_ids,
           NULL::text as purity_ids, NULL::text as type_ids, NULL::text as wide_range_ids,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(in_shop_pcs, 0) + COALESCE(in_transit, 0) - COALESCE(prov_pieces, 0)) as short_excess_pcs,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section

    UNION ALL
    -- Level 2: Section + Purity
    SELECT 2 as level_id, section, purity, NULL::text as type,
           NULL::text as wide_range, NULL::numeric as range_weight,
           array_to_string(array_agg(DISTINCT section_id) FILTER (WHERE section_id IS NOT NULL), ',') as section_ids,
           array_to_string(array_agg(DISTINCT purity_id) FILTER (WHERE purity_id IS NOT NULL), ',') as purity_ids,
           NULL::text as type_ids, NULL::text as wide_range_ids,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(in_shop_pcs, 0) + COALESCE(in_transit, 0) - COALESCE(prov_pieces, 0)) as short_excess_pcs,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, purity

    UNION ALL
    -- Level 3: Section + Purity + Type
    SELECT 3 as level_id, section, purity, type,
           NULL::text as wide_range, NULL::numeric as range_weight,
           array_to_string(array_agg(DISTINCT section_id) FILTER (WHERE section_id IS NOT NULL), ',') as section_ids,
           array_to_string(array_agg(DISTINCT purity_id) FILTER (WHERE purity_id IS NOT NULL), ',') as purity_ids,
           array_to_string(array_agg(DISTINCT type_id) FILTER (WHERE type_id IS NOT NULL), ',') as type_ids,
           NULL::text as wide_range_ids,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(in_shop_pcs, 0) + COALESCE(in_transit, 0) - COALESCE(prov_pieces, 0)) as short_excess_pcs,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, purity, type

    UNION ALL
    -- Level 4: Section + Purity + Type + Wide Range
    SELECT 4 as level_id, section, purity, type, wide_range, NULL::numeric as range_weight,
           array_to_string(array_agg(DISTINCT section_id) FILTER (WHERE section_id IS NOT NULL), ',') as section_ids,
           array_to_string(array_agg(DISTINCT purity_id) FILTER (WHERE purity_id IS NOT NULL), ',') as purity_ids,
           array_to_string(array_agg(DISTINCT type_id) FILTER (WHERE type_id IS NOT NULL), ',') as type_ids,
           array_to_string(array_agg(DISTINCT wide_range_id) FILTER (WHERE wide_range_id IS NOT NULL), ',') as wide_range_ids,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(in_shop_pcs, 0) + COALESCE(in_transit, 0) - COALESCE(prov_pieces, 0)) as short_excess_pcs,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, purity, type, wide_range

    UNION ALL
    -- Level 5: Section + Purity + Type + Wide Range + Range Weight
    SELECT 5 as level_id, section, purity, type, wide_range, range_weight,
           array_to_string(array_agg(DISTINCT section_id) FILTER (WHERE section_id IS NOT NULL), ',') as section_ids,
           array_to_string(array_agg(DISTINCT purity_id) FILTER (WHERE purity_id IS NOT NULL), ',') as purity_ids,
           array_to_string(array_agg(DISTINCT type_id) FILTER (WHERE type_id IS NOT NULL), ',') as type_ids,
           array_to_string(array_agg(DISTINCT wide_range_id) FILTER (WHERE wide_range_id IS NOT NULL), ',') as wide_range_ids,
           SUM(prov_pieces) as prov_pcs, SUM(prov_gr_wt) as prov_gr_wt, SUM(in_shop_wt) as in_shop_wt,
           SUM(COALESCE(in_shop_pcs, 0) + COALESCE(in_transit, 0) - COALESCE(prov_pieces, 0)) as short_excess_pcs,
           SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) as ordered_wt,
           SUM(in_transit_wt) as in_transit_wt
    FROM base GROUP BY section, purity, type, wide_range, range_weight
)
SELECT 
    level_id, section, purity, type, wide_range, range_weight,
    section_ids, purity_ids, type_ids, wide_range_ids,
    prov_pcs, prov_gr_wt, in_shop_wt, short_excess_pcs, ordered_wt, in_transit_wt,
    (in_shop_wt + in_transit_wt - prov_gr_wt) as short_excess_wt,
    CASE WHEN prov_gr_wt = 0 THEN 0 ELSE (in_shop_wt + in_transit_wt - prov_gr_wt) * 100.0 / prov_gr_wt END as percent
FROM levels
ORDER BY section, purity NULLS FIRST, type NULLS FIRST, wide_range NULLS FIRST, range_weight NULLS FIRST, level_id
        """

    LOCATION_DETAILS = r"""
WITH filtered AS (
    SELECT *
    FROM provision_stock_raw_snapshot
    WHERE location = :detail_location
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
),
base AS (
    SELECT
        COALESCE("group", 'Unknown') AS group_name,
        COALESCE(purity::text, 'Unknown') AS purity,
        COALESCE(classification, 'Unknown') AS classification,
        COALESCE(sub_classification, 'Unknown') AS sub_classification,
        COALESCE(section, 'Unknown') AS section,
        COALESCE(type, 'Unknown') AS type,
        COALESCE(make, 'Unknown') AS make,
        COALESCE(master_collection, 'Unknown') AS master_collection,
        COALESCE(collection, 'Unknown') AS collection,
        COALESCE(sub_section, 'Unknown') AS sub_section,
        COALESCE(gender, 'Unknown') AS gender,
        COALESCE(wide_range, 'Unknown') AS wide_range,
        COALESCE(range_weight::text, 'Unknown') AS range_weight,
        prov_gr_wt,
        in_shop_wt,
        in_transit_wt,
        order_only_wt,
        req_only,
        short_gr_wt,
        excess_gr_weight,
        short_percent
    FROM filtered
)
SELECT
    13 - (
        GROUPING(group_name) + GROUPING(purity) + GROUPING(classification)
        + GROUPING(sub_classification) + GROUPING(section) + GROUPING(type)
        + GROUPING(make) + GROUPING(master_collection) + GROUPING(collection)
        + GROUPING(sub_section) + GROUPING(gender) + GROUPING(wide_range)
        + GROUPING(range_weight)
    ) AS level_id,
    group_name,
    purity,
    classification,
    sub_classification,
    section,
    type,
    make,
    master_collection,
    collection,
    sub_section,
    gender,
    wide_range,
    range_weight,
    SUM(COALESCE(prov_gr_wt, 0)) AS prov_gr_wt,
    SUM(COALESCE(in_shop_wt, 0)) AS in_shop_wt,
    SUM(COALESCE(in_transit_wt, 0)) AS in_transit_wt,
    SUM(COALESCE(order_only_wt, 0) + COALESCE(req_only, 0)) AS ordered_wt,
    SUM(COALESCE(short_gr_wt, 0)) AS short_wt,
    SUM(COALESCE(excess_gr_weight, 0)) AS excess_wt,
    SUM(COALESCE(excess_gr_weight, 0) - COALESCE(short_gr_wt, 0)) AS net_short_excess,
    SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0)) AS short_percent_weight,
    ROUND(
        CASE
            WHEN SUM(COALESCE(prov_gr_wt, 0)) = 0 THEN 0
            ELSE SUM(COALESCE(short_percent, 0) * COALESCE(prov_gr_wt, 0))
                 / SUM(COALESCE(prov_gr_wt, 0))
        END,
        2
    ) AS short_percent
FROM base
GROUP BY ROLLUP (
    group_name, purity, classification, sub_classification, section, type,
    make, master_collection, collection, sub_section, gender, wide_range,
    range_weight
)
HAVING GROUPING(group_name) = 0
ORDER BY
    group_name NULLS FIRST,
    purity NULLS FIRST,
    classification NULLS FIRST,
    sub_classification NULLS FIRST,
    section NULLS FIRST,
    type NULLS FIRST,
    make NULLS FIRST,
    master_collection NULLS FIRST,
    collection NULLS FIRST,
    sub_section NULLS FIRST,
    gender NULLS FIRST,
    wide_range NULLS FIRST,
    range_weight NULLS FIRST
    """

    PROVISION_DETAILS = r"""
SELECT
    p.location,
    p.division,
    p."group" AS group_name,
    p.purity,
    p.classification,
    p.sub_classification,
    p.make,
    p.collection,
    p.section,
    p.sub_section,
    p.type,
    p.wide_range,
    p.size,
    p.screw_type,
    p.range_weight AS weight,
    p.prov_pieces AS pieces,
    p.prov_gr_wt AS gross_weight,
    p.prov_type,
    COUNT(*) OVER () AS total_records,
    COALESCE(SUM(p.prov_pieces) OVER (), 0) AS total_pieces,
    COALESCE(SUM(p.prov_gr_wt) OVER (), 0) AS total_gross_wt
FROM provision_stock_raw_snapshot AS p
WHERE (:location IS NULL OR p.location = ANY(string_to_array(CAST(:location AS text), ',')))
  AND (:state IS NULL OR p.state = ANY(string_to_array(CAST(:state AS text), ',')))
  AND (:purity IS NULL OR p.purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
  AND (:classification IS NULL OR p.classification = ANY(string_to_array(CAST(:classification AS text), ',')))
  AND (:make IS NULL OR p.make = ANY(string_to_array(CAST(:make AS text), ',')))
  AND (:collection IS NULL OR p.collection = ANY(string_to_array(CAST(:collection AS text), ',')))
  AND (:section IS NULL OR p.section = ANY(string_to_array(CAST(:section AS text), ',')))
  AND (:prov_type IS NULL OR p.prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
  AND (:provision_mode IS NULL OR p.provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
  AND (:branch_type IS NULL OR p.branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
  AND (:branch_status IS NULL OR p.branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
  AND (:business_head IS NULL OR p.business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
  AND (:bh_emp_code IS NULL OR p.business_head_emp_code = :bh_emp_code)
  AND (:authorized_branch_ids IS NULL OR p.branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
  AND p.section_id = ANY(string_to_array(CAST(:drill_section_ids AS text), ',')::bigint[])
  AND (:drill_level < 2 OR p.purity_id = ANY(string_to_array(CAST(:drill_purity_ids AS text), ',')::bigint[]))
  AND (:drill_level < 3 OR p.type_id = ANY(string_to_array(CAST(:drill_type_ids AS text), ',')::bigint[]))
  AND (:drill_level < 4 OR p.wide_range_id = ANY(string_to_array(CAST(:drill_wide_range_ids AS text), ',')::bigint[]))
  AND (:drill_level < 5 OR p.range_weight = CAST(:drill_range_weight AS numeric))
ORDER BY p.location NULLS LAST, p.division NULLS LAST, p."group" NULLS LAST,
         p.classification NULLS LAST, p.make NULLS LAST, p.collection NULLS LAST, p.id
LIMIT :limit OFFSET :offset
        """

    @staticmethod
    def in_shop_details(stock_identity_columns, identity_join):
        return f"""
WITH matching_stock AS MATERIALIZED (
    SELECT DISTINCT
        {stock_identity_columns}
    FROM provision_stock_raw_snapshot AS p
    WHERE (:location IS NULL OR p.location = ANY(string_to_array(CAST(:location AS text), ',')))
          AND (:state IS NULL OR p.state = ANY(string_to_array(CAST(:state AS text), ',')))
          AND (:purity IS NULL OR p.purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
          AND (:classification IS NULL OR p.classification = ANY(string_to_array(CAST(:classification AS text), ',')))
          AND (:make IS NULL OR p.make = ANY(string_to_array(CAST(:make AS text), ',')))
          AND (:collection IS NULL OR p.collection = ANY(string_to_array(CAST(:collection AS text), ',')))
          AND (:section IS NULL OR p.section = ANY(string_to_array(CAST(:section AS text), ',')))
          AND (:prov_type IS NULL OR p.prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
          AND (:provision_mode IS NULL OR p.provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
          AND (:branch_type IS NULL OR p.branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
          AND (:branch_status IS NULL OR p.branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
          AND (:business_head IS NULL OR p.business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
          AND (:bh_emp_code IS NULL OR p.business_head_emp_code = :bh_emp_code)
          AND (:authorized_branch_ids IS NULL OR p.branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
          AND p.section_id = ANY(string_to_array(CAST(:drill_section_ids AS text), ',')::bigint[])
          AND (:drill_level < 2 OR p.purity_id = ANY(string_to_array(CAST(:drill_purity_ids AS text), ',')::bigint[]))
          AND (:drill_level < 3 OR p.type_id = ANY(string_to_array(CAST(:drill_type_ids AS text), ',')::bigint[]))
          AND (:drill_level < 4 OR p.wide_range_id = ANY(string_to_array(CAST(:drill_wide_range_ids AS text), ',')::bigint[]))
          AND (:drill_level < 5 OR p.range_weight = CAST(:drill_range_weight AS numeric))
),
matched_barcodes AS (
    SELECT b.*
    FROM matching_stock AS p
    JOIN size_level_nip_barcode_snapshot AS b
      ON TRUE
      {identity_join}
    WHERE (:drill_level < 5 OR b.weight = CAST(:drill_range_weight AS numeric))
)
SELECT
    b.*,
    COUNT(*) OVER () AS total_records,
    COALESCE(SUM(b.pieces) OVER (), 0) AS total_pieces,
    COALESCE(SUM(b.gross_wt) OVER (), 0) AS total_gross_wt
FROM matched_barcodes AS b
ORDER BY b.barcode_no NULLS LAST, b.design_no NULLS LAST, b.id
LIMIT :limit OFFSET :offset
        """

    @staticmethod
    def stock_comparison(provision_identity, nip_identity, provision_group_by, nip_group_by, provision_nip_join, comparison_join):
        return f"""
WITH provision_rows AS MATERIALIZED (
    SELECT
        {provision_identity},
        p.range_weight,
        MIN(p.location) AS location,
        MIN(p.division) AS division,
        MIN(p."group") AS group_name,
        MIN(p.purity) AS purity,
        MIN(p.classification) AS classification,
        MIN(p.sub_classification) AS sub_classification,
        MIN(p.make) AS make,
        MIN(p.collection) AS collection,
        MIN(p.section) AS section,
        MIN(p.sub_section) AS sub_section,
        MIN(p.type) AS type,
        MIN(p.wide_range) AS wide_range,
        MIN(p.size) AS size,
        MIN(p.screw_type) AS screw_type,
        MIN(p.prov_type) AS prov_type,
        COALESCE(SUM(p.prov_pieces), 0) AS provision_pieces,
        COALESCE(SUM(p.prov_gr_wt), 0) AS provision_weight
    FROM provision_stock_raw_snapshot AS p
    WHERE (:location IS NULL OR p.location = ANY(string_to_array(CAST(:location AS text), ',')))
      AND (:state IS NULL OR p.state = ANY(string_to_array(CAST(:state AS text), ',')))
      AND (:purity IS NULL OR p.purity = ANY(string_to_array(CAST(:purity AS text), ',')::numeric[]))
      AND (:classification IS NULL OR p.classification = ANY(string_to_array(CAST(:classification AS text), ',')))
      AND (:make IS NULL OR p.make = ANY(string_to_array(CAST(:make AS text), ',')))
      AND (:collection IS NULL OR p.collection = ANY(string_to_array(CAST(:collection AS text), ',')))
      AND (:section IS NULL OR p.section = ANY(string_to_array(CAST(:section AS text), ',')))
      AND (:prov_type IS NULL OR p.prov_type = ANY(string_to_array(CAST(:prov_type AS text), ',')))
      AND (:provision_mode IS NULL OR p.provision_mode_filter = ANY(string_to_array(CAST(:provision_mode AS text), ',')))
      AND (:branch_type IS NULL OR p.branch_type = ANY(string_to_array(CAST(:branch_type AS text), ',')))
      AND (:branch_status IS NULL OR p.branch_status = ANY(string_to_array(CAST(:branch_status AS text), ',')))
      AND (:business_head IS NULL OR p.business_head_name = ANY(string_to_array(CAST(:business_head AS text), ',')))
      AND (:bh_emp_code IS NULL OR p.business_head_emp_code = :bh_emp_code)
      AND (:authorized_branch_ids IS NULL OR p.branch_id = ANY(string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]))
      AND p.section_id = ANY(string_to_array(CAST(:drill_section_ids AS text), ',')::bigint[])
      AND (:drill_level < 2 OR p.purity_id = ANY(string_to_array(CAST(:drill_purity_ids AS text), ',')::bigint[]))
      AND (:drill_level < 3 OR p.type_id = ANY(string_to_array(CAST(:drill_type_ids AS text), ',')::bigint[]))
      AND (:drill_level < 4 OR p.wide_range_id = ANY(string_to_array(CAST(:drill_wide_range_ids AS text), ',')::bigint[]))
      AND (:drill_level < 5 OR p.range_weight = CAST(:drill_range_weight AS numeric))
    GROUP BY {provision_group_by}, p.range_weight
),
nip_rows AS MATERIALIZED (
    SELECT
        {nip_identity},
        b.weight AS range_weight,
        MIN(b.location) AS nip_location,
        MIN(b.classification) AS nip_classification,
        MIN(b.make) AS nip_make,
        MIN(b.collection) AS nip_collection,
        MIN(b.section) AS nip_section,
        MIN(b.sub_section) AS nip_sub_section,
        MIN(b.type) AS nip_type,
        MIN(b.wide_range) AS nip_wide_range,
        MIN(b.size) AS nip_size,
        MIN(b.screw_type) AS nip_screw_type,
        COUNT(*) AS barcode_count,
        COALESCE(SUM(b.pieces), 0) AS nip_pieces,
        COALESCE(SUM(b.gross_wt), 0) AS nip_weight
    FROM size_level_nip_barcode_snapshot AS b
    JOIN provision_rows AS p
      ON p.range_weight = b.weight
      {provision_nip_join}
    GROUP BY {nip_group_by}, b.weight
),
comparison AS (
    SELECT
        p.*,
        n.nip_location,
        n.nip_classification,
        n.nip_make,
        n.nip_collection,
        n.nip_section,
        n.nip_sub_section,
        n.nip_type,
        n.nip_wide_range,
        n.nip_size,
        n.nip_screw_type,
        COALESCE(n.barcode_count, 0) AS barcode_count,
        COALESCE(n.nip_pieces, 0) AS nip_pieces,
        COALESCE(n.nip_weight, 0) AS nip_weight,
        COALESCE(n.nip_pieces, 0) - p.provision_pieces AS pieces_difference,
        COALESCE(n.nip_weight, 0) - p.provision_weight AS weight_difference
    FROM provision_rows AS p
    LEFT JOIN nip_rows AS n
      ON p.range_weight = n.range_weight
      {comparison_join}
)
SELECT
    comparison.*,
    (ABS(pieces_difference) > 0.0005 OR ABS(weight_difference) > 0.0005) AS has_difference,
    COUNT(*) OVER () AS total_pairs,
    COUNT(*) FILTER (
        WHERE ABS(pieces_difference) > 0.0005 OR ABS(weight_difference) > 0.0005
    ) OVER () AS mismatch_pairs,
    COALESCE(SUM(provision_pieces) OVER (), 0) AS total_provision_pieces,
    COALESCE(SUM(nip_pieces) OVER (), 0) AS total_nip_pieces,
    COALESCE(SUM(provision_weight) OVER (), 0) AS total_provision_weight,
    COALESCE(SUM(nip_weight) OVER (), 0) AS total_nip_weight
FROM comparison
ORDER BY
    (ABS(pieces_difference) > 0.0005 OR ABS(weight_difference) > 0.0005) DESC,
    location NULLS LAST, classification NULLS LAST, make NULLS LAST,
    collection NULLS LAST, section NULLS LAST, range_weight NULLS LAST
LIMIT :limit OFFSET :offset
        """

    @staticmethod
    def comparison_barcodes(identity_columns, provision_identity_filters, barcode_identity_join):
        return f"""
WITH authorized_identity AS MATERIALIZED (
    SELECT DISTINCT
        {', '.join(f'p.{column}' for column in identity_columns)},
        p.range_weight
    FROM provision_stock_raw_snapshot AS p
    WHERE TRUE
      {provision_identity_filters}
      AND p.range_weight = CAST(:range_weight AS numeric)
      AND (:required_branch_type IS NULL OR p.branch_type = :required_branch_type)
      AND (:bh_emp_code IS NULL OR p.business_head_emp_code = :bh_emp_code)
      AND (:authorized_branch_ids IS NULL OR p.branch_id = ANY(
          string_to_array(CAST(:authorized_branch_ids AS text), ',')::integer[]
      ))
),
matched_barcodes AS (
    SELECT b.*
    FROM authorized_identity AS p
    JOIN size_level_nip_barcode_snapshot AS b
      ON p.range_weight = b.weight
      {barcode_identity_join}
)
SELECT
    b.*,
    COUNT(*) OVER () AS total_records,
    COALESCE(SUM(b.pieces) OVER (), 0) AS total_pieces,
    COALESCE(SUM(b.gross_wt) OVER (), 0) AS total_gross_wt
FROM matched_barcodes AS b
ORDER BY b.barcode_no NULLS LAST, b.design_no NULLS LAST, b.id
LIMIT :limit OFFSET :offset
        """

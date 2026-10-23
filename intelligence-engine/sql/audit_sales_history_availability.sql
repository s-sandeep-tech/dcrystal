-- Read-only. Dates alone do not establish when a historical feature was available.
SELECT scope, feature_group, provider, COUNT(*) AS rows,
       MIN(feature_date) AS first_date, MAX(feature_date) AS last_date,
       MIN(available_at) AS first_known_availability,
       COUNT(*) FILTER (WHERE available_at >= ((feature_date + 1)::timestamp AT TIME ZONE 'UTC'))
           AS available_after_feature_day
FROM sales_external_features
WHERE scope IN ('branch:20', 'global')
GROUP BY scope, feature_group, provider
ORDER BY scope, feature_group, provider;

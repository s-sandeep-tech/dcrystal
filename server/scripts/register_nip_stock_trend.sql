-- Register the report; assign it to roles in the RBAC screen afterwards.
INSERT INTO menus (title, url, icon, sort_order, offline_message, is_offline)
SELECT 'NIP Stock Trend Analysis', '/nip-stock-trend-analysis', 'show_chart', 70, '', false
WHERE NOT EXISTS (SELECT 1 FROM menus WHERE url = '/nip-stock-trend-analysis');

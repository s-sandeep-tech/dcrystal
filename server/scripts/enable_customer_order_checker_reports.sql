BEGIN;

INSERT INTO roles (name, description)
VALUES ('CUSTOMER OREDR CHECKER', 'View all customer order records across three customer order reports')
ON CONFLICT (name) DO NOTHING;

INSERT INTO menus (title, url, icon, sort_order, is_offline, offline_message)
SELECT title, url, icon, sort_order, FALSE, ''
FROM (VALUES
    ('Customer Order Pending Analysis', '/customer-order-analysis', 'analytics', 701),
    ('Customer Order Performance & Delivery Monitoring', '/customer-order-performance-monitoring', 'assignment', 702),
    ('Customer Order Fulfilment Summary', '/customerorderfulfilmentsummary', 'fact_check', 703)
) AS reports(title, url, icon, sort_order)
WHERE NOT EXISTS (SELECT 1 FROM menus WHERE menus.url = reports.url);

WITH RECURSIVE report_menus AS (
    SELECT id, parent_id, permission_required
    FROM menus
    WHERE url IN ('/customer-order-analysis', '/customer-order-performance-monitoring',
                  '/customerorderfulfilmentsummary', '/customer-order-fulfilment-summary')
    UNION
    SELECT m.id, m.parent_id, m.permission_required
    FROM menus m JOIN report_menus child ON child.parent_id = m.id
)
INSERT INTO role_menu (role_id, menu_id)
SELECT r.id, m.id FROM roles r CROSS JOIN report_menus m
WHERE r.name = 'CUSTOMER OREDR CHECKER'
ON CONFLICT DO NOTHING;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN role_menu rm ON rm.role_id = r.id
JOIN menus m ON m.id = rm.menu_id
JOIN permissions p ON p.name = m.permission_required
WHERE r.name = 'CUSTOMER OREDR CHECKER'
  AND p.name NOT IN ('ADMIN', 'SUPER_ADMIN', 'report.export')
ON CONFLICT DO NOTHING;

COMMIT;

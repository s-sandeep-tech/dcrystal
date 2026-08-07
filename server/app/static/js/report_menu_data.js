window.REPORT_MENU_DATA = [
    {
        id: "order-management",
        title: "Order Management",
        description: "Order lifecycle, pending stages, rejection, and fulfillment reports.",
        accent: "blue",
        reports: [
            {
                id: "order-status",
                title: "Order Status Tracking",
                href: "/orderstatus",
                icon: "query_stats",
                description: "Track order status across make, collection, and party views.",
                tags: ["order", "tracking", "status"]
            },
            {
                id: "order-delay",
                title: "Order Delay Tracking",
                href: "/orderdelaytracking",
                icon: "timer",
                description: "Review delayed orders and aging by responsibility.",
                tags: ["delay", "aging", "order"]
            },
            {
                id: "order-processing",
                title: "Order Processing Pending",
                href: "/order-processing-pending-stage-status",
                icon: "pending_actions",
                description: "Monitor processing, barcode, HM, QC, and invoice pending stages.",
                tags: ["processing", "pending", "stage"]
            },
            {
                id: "order-fulfillment-value-aging",
                title: "Order Fulfillment Value Aging Matrix",
                href: "/order_fulfillment_value_aging_matrix",
                icon: "table_chart",
                description: "Compare order value buckets against delivery value buckets.",
                tags: ["fulfillment", "aging", "matrix"]
            }
        ]
    },
    {
        id: "ownership-summary",
        title: "Ownership & Summary",
        description: "Owner, showroom, branch, and business head summary reports.",
        accent: "emerald",
        reports: [
            {
                id: "party-report-menu",
                title: "Party Report Center",
                href: "/party-report-menu",
                icon: "hub",
                description: "Open the complete collection of party design, order, quality, allocation, and delivery reports.",
                tags: ["party", "reports", "center"]
            },
            {
                id: "pending-order-details",
                title: "Pending Order Details Report",
                href: "/pendingorderdetails",
                icon: "pending_actions",
                description: "Hierarchical summary of pending counts and weights across production stages.",
                tags: ["pending", "order", "details", "owner"]
            },
            {
                id: "active-order-details",
                title: "Active Orders Report",
                href: "/activeorderdetails",
                icon: "pending_actions",
                description: "Hierarchical summary of active counts and weights across production stages.",
                tags: ["active", "order", "details", "owner"]
            },
            {
                id: "owner-wise-order",
                title: "Owner Wise Order Summary",
                href: "/ownerwiseordersummary",
                icon: "supervisor_account",
                description: "Ownership-level order summary by make, collection, and classification.",
                tags: ["owner", "summary", "orders"]
            },

            {
                id: "showroom-wise-order",
                title: "Showroom Wise Order Summary",
                href: "/showroom_wise_order_summary",
                icon: "storefront",
                description: "Order performance and drilldown by showroom.",
                tags: ["showroom", "summary", "orders"]
            },
            {
                id: "bh-showroom-wise-order",
                title: "BH Showroom Wise Order Summary",
                href: "/bh_showroom_wise_order_summary",
                icon: "account_tree",
                description: "Business head and showroom order summary.",
                tags: ["business head", "showroom", "summary"]
            },
            {
                id: "collection-wise-average-delivery-days",
                title: "Collection wise average delivery days",
                href: "/collection-wise-average-delivery-days",
                icon: "local_shipping",
                description: "Track receipt performance and average delivery days across collections.",
                tags: ["collection", "delivery", "days", "average", "receipt"]
            },
            {
                id: "party-design-delivery-performance",
                title: "Order Fulfillment Value Aging Matrix / Party Design Delivery Performance",
                href: "/party-design-delivery-performance",
                icon: "analytics",
                description: "Hierarchical delivery performance and average delivery days by party, make, classification, and sub-classification.",
                tags: ["party", "design", "delivery", "performance", "average"]
            },
            {
                id: "party-order-accept-cancel-delivery-performance",
                title: "Party Order Acceptance, Cancellation & Delivery Performance",
                href: "/party-order-accept-cancel-delivery-performance",
                icon: "fact_check",
                description: "Party level breakdown of order numbers, weights, cancellations, production, and delivery performance.",
                tags: ["party", "order", "acceptance", "cancellation", "delivery", "performance"]
            },
            {
                id: "party-design-location-allocation",
                title: "Party Design Location Allocation",
                href: "/party-design-location-allocation",
                icon: "pin_drop",
                description: "Drilldown by party, zone, and make for total design count and delivered weights.",
                tags: ["party", "design", "location", "allocation", "zone"]
            },
            {
                id: "party-order-cancellation-performance",
                title: "Party Order Cancellation Performance",
                href: "/party-order-cancellation-performance",
                icon: "cancel",
                description: "Drilldown by party and make for order weights, cancelled weights, and cancellation percentages.",
                tags: ["party", "order", "cancellation", "performance"]
            },
            {
                id: "party-mc-stone-value-allocation",
                title: "Party Making Charge & Stone Value Allocation",
                href: "/party-mc-stone-value-allocation",
                icon: "request_quote",
                description: "Drilldown by party and make for total design count, metal weights, MC values, stone weights, and stone values.",
                tags: ["party", "making charge", "mc", "stone", "value", "allocation"]
            },
            {
                id: "party-hallmark-pass-fail-performance",
                title: "Party Hallmark Pass & Fail Performance",
                href: "/party-hallmark-pass-fail-performance",
                icon: "verified",
                description: "Drilldown by party with month-wise breakdown for HM ISSUE, HM PASSED, and HM FAILED weights and pieces.",
                tags: ["party", "hallmark", "hm", "pass", "fail", "performance", "month"]
            },
            {
                id: "party-ro-wise-delivery-performance",
                title: "Party RO-Wise Delivery Performance",
                href: "/party-ro-wise-delivery-performance",
                icon: "local_shipping",
                description: "Drilldown by party and make (make owner) for delivery RO and total delivered weight.",
                tags: ["party", "ro", "delivery", "performance", "weight"]
            },
            {
                id: "party-order-lifecycle-performance",
                title: "Party Order plain and Studed info",
                href: "/party-order-lifecycle-performance",
                icon: "loop",
                description: "Drilldown by party, make (make owner), and ornament type for order numbers, order weights, cancelled weights, production weights, and delivered weights.",
                tags: ["party", "order", "lifecycle", "performance", "weight"]
            },
            {
                id: "party-qc-pass-fail-performance",
                title: "Party QC Pass & Fail Info",
                href: "/party-qc-pass-fail-performance",
                icon: "fact_check",
                description: "Drilldown by party with month-wise breakdown for QC ISSUE, QC PASSED, and QC FAILED weights and pieces.",
                tags: ["party", "qc", "quality control", "pass", "fail", "performance", "month"]
            },
            {
                id: "design-allocation-performance",
                title: "Design Allocation Performance",
                href: "/design-allocation-performance",
                icon: "category",
                description: "Drilldown by make (make owner), section, and wide range for total design count and percentage.",
                tags: ["design", "allocation", "performance", "make", "section", "wide range"]
            }
        ]
    },










    {
        id: "inventory-stock",
        title: "Inventory & Stock",
        description: "Stock position, provision, location, and allocation reports.",
        accent: "violet",
        reports: [
            {
                id: "location-physical-stock",
                title: "Location Physical Stock Status",
                href: "/location-physical-stock-status",
                icon: "inventory_2",
                description: "View physical stock status by location and collection.",
                tags: ["stock", "location", "physical"]
            },
            {
                id: "provision-stock-status",
                title: "Provision Stock Status",
                href: "/provision-stock-status",
                icon: "fact_check",
                description: "Provision stock availability and status report.",
                tags: ["provision", "stock", "status"]
            },
            {
                id: "branch-stock-provision",
                title: "Branch Stock Provision",
                href: "/branchstockprovision",
                icon: "warehouse",
                description: "Allocated and refill barcode stock views.",
                tags: ["branch", "stock", "barcode"]
            },
            {
                id: "branch-weight-allocation",
                title: "Branch Weight Allocation",
                href: "/branchweightv2",
                icon: "scale",
                description: "Weight allocation report by branch.",
                tags: ["branch", "weight", "allocation"]
            }
        ]
    },
    {
        id: "operations-delay",
        title: "Operations Delay",
        description: "Process, stage, party, QC, and hallmarking delay reports.",
        accent: "amber",
        reports: [
            {
                id: "process-level-delay",
                title: "Process Level Delay",
                href: "/processleveldelay",
                icon: "manufacturing",
                description: "Delay report by production process level.",
                tags: ["process", "delay", "operations"]
            },
            {
                id: "stage-level-delay",
                title: "Stage Level Delay",
                href: "/stageleveldelay",
                icon: "route",
                description: "Stage-wise delay tracking and exception review.",
                tags: ["stage", "delay", "operations"]
            },
            {
                id: "party-delay",
                title: "Party Delay Management",
                href: "/party-delay-management",
                icon: "groups",
                description: "Party-level aging, feedback, and delay details.",
                tags: ["party", "delay", "feedback"]
            },
            {
                id: "qc-delay",
                title: "QC Delay Management",
                href: "/qc-delay-management",
                icon: "verified",
                description: "QC delay review and follow-up report.",
                tags: ["qc", "delay", "quality"]
            },
            {
                id: "hm-delay",
                title: "HM Delay Management",
                href: "/hm-delay-management",
                icon: "workspace_premium",
                description: "Hallmarking delay management and pending details.",
                tags: ["hm", "hallmarking", "delay"]
            }
        ]
    },
    {
        id: "purchase-procurement",
        title: "Purchase & Procurement",
        description: "Purchase order and supplier-facing operational reports.",
        accent: "rose",
        reports: [
            {
                id: "outstanding-po",
                title: "Outstanding Purchase Order",
                href: "/outstanding_purchase_orders",
                icon: "receipt_long",
                description: "Outstanding purchase order status and detail drilldown.",
                tags: ["purchase", "po", "outstanding"]
            },
            {
                id: "pending-acceptance",
                title: "Pending Acceptance Feedback",
                href: "/pending-acceptance-feedback",
                icon: "assignment_late",
                description: "Pending acceptance report with feedback workflow.",
                tags: ["acceptance", "pending", "feedback"]
            },
            {
                id: "rejected-weight",
                title: "Rejected Weight",
                href: "/rejected-weight-feedback",
                icon: "do_not_disturb_on",
                description: "Rejected weight analysis and operational detail.",
                tags: ["rejection", "weight", "purchase"]
            }
        ]
    }
];

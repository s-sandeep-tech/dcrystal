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
                id: "pending-order-details",
                title: "Pending Order Details Report",
                href: "/pendingorderdetails",
                icon: "pending_actions",
                description: "Hierarchical summary of pending counts and weights across production stages.",
                tags: ["pending", "order", "details", "owner"]
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

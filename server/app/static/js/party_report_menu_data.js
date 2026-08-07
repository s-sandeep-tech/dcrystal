window.PARTY_REPORT_MENU_DATA = [
    {
        id: "party-performance-reports",
        title: "Party Performance Reports",
        description: "Design, order, allocation, quality, and delivery reports by party.",
        accent: "blue",
        reports: [
            {
                id: "party-performance-matrix",
                sequence: "00",
                title: "Party Performance Matrix",
                href: "/party-performance-matrix",
                icon: "grid_view",
                description: "Compare consolidated design, order, allocation, quality, and delivery performance.",
                tags: ["party", "matrix", "analytics"]
            },
            {
                id: "party-design-info",
                sequence: "01",
                title: "Party Design Info",
                href: "/party-design-delivery-performance?page=10",
                icon: "design_services",
                description: "Review design delivery performance and turnaround details by party.",
                tags: ["party", "design", "delivery"]
            },
            {
                id: "party-order-frequency",
                sequence: "02",
                title: "Party Order Accept, Cancel & Delivered Frequency",
                href: "/party-order-accept-cancel-delivery-performance",
                icon: "fact_check",
                description: "Compare ordered, accepted, cancelled, and delivered activity by month.",
                tags: ["order", "acceptance", "delivery"]
            },
            {
                id: "party-design-location-allocation",
                sequence: "03",
                title: "Party Design Location Allocation",
                href: "/party-design-location-allocation",
                icon: "location_on",
                description: "Analyze design allocation and delivered weight across zones and makes.",
                tags: ["design", "location", "allocation"]
            },
            {
                id: "party-order-cancellation",
                sequence: "04",
                title: "Party Order Cancellation",
                href: "/party-order-cancellation-performance",
                icon: "cancel",
                description: "Review cancelled order weight and cancellation percentage by party.",
                tags: ["order", "cancelled", "performance"]
            },
            {
                id: "party-mc-stone-value",
                sequence: "05",
                title: "Party MC & Stone Value Allocation",
                href: "/party-mc-stone-value-allocation",
                icon: "diamond",
                description: "Compare metal weight, making charge, stone weight, and stone value.",
                tags: ["making charge", "stone", "value"]
            },
            {
                id: "party-hallmark-pass-fail",
                sequence: "06",
                title: "Party Hallmark Pass & Fail",
                href: "/party-hallmark-pass-fail-performance",
                icon: "verified",
                description: "Track hallmark issue, pass, and fail results by center and month.",
                tags: ["hallmark", "pass", "fail"]
            },
            {
                id: "party-ro-wise-delivery",
                sequence: "07",
                title: "Party RO-Wise Delivery",
                href: "/party-ro-wise-delivery-performance",
                icon: "local_shipping",
                description: "Review delivered weight by regional office, party, make, and owner.",
                tags: ["regional office", "delivery", "weight"]
            },
            {
                id: "party-order-lifecycle",
                sequence: "08",
                title: "Party Order plain and Studed info",
                href: "/party-order-lifecycle-performance",
                icon: "conversion_path",
                description: "Follow order weight through cancellation, production, and delivery.",
                tags: ["order", "lifecycle", "production"]
            },
            {
                id: "party-qc-pass-fail",
                sequence: "09",
                title: "Party QC Pass & Fail",
                href: "/party-qc-pass-fail-performance",
                icon: "task_alt",
                description: "Track QC issue, passed, and failed pieces and weight by month.",
                tags: ["quality control", "pass", "fail"]
            },
            {
                id: "design-allocation-performance",
                sequence: "10",
                title: "Design Allocation Performance",
                href: "/design-allocation-performance",
                supportsPartyFilter: false,
                icon: "schema",
                description: "Review design allocation by make, owner, section, and weight range.",
                tags: ["design", "allocation", "range"]
            }
        ]
    }
];

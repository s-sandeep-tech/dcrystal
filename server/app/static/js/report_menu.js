(function () {
    const menuData = Array.isArray(window.REPORT_MENU_DATA) ? window.REPORT_MENU_DATA : [];
    const contentEl = document.getElementById("reportMenuContent");
    const searchEl = document.getElementById("reportSearch");
    const countEl = document.getElementById("reportCount");
    const emptyEl = document.getElementById("reportEmptyState");

    function normalize(value) {
        return String(value || "").trim().toLowerCase();
    }

    function matchesReport(report, query, category) {
        if (!query) return true;
        const searchable = [
            report.title,
            report.description,
            report.href,
            category.title,
            ...(report.tags || [])
        ].map(normalize).join(" ");
        return searchable.includes(query);
    }

    function countReports(categories) {
        return categories.reduce((total, category) => total + category.reports.length, 0);
    }

    function renderReport(report) {
        const tags = (report.tags || []).slice(0, 3);
        return `
            <a class="report-card" href="${report.href || "#"}" data-report-id="${report.id}">
                <span class="report-card-body">
                    <span class="report-card-heading">
                        <span class="report-card-icon material-symbols-outlined">${report.icon || "article"}</span>
                        <span class="report-card-title">
                            ${report.title}
                        </span>
                    </span>
                    <span class="report-card-description">${report.description || "Report details can be added later."}</span>
                    <span class="report-card-tags">
                        ${tags.map((tag) => `<span>${tag}</span>`).join("")}
                    </span>
                </span>
                <span class="report-card-action material-symbols-outlined">arrow_forward</span>
            </a>
        `;
    }

    function renderCategory(category) {
        return `
            <section class="report-category report-accent-${category.accent || "blue"}">
                <div class="report-category-header">
                    <div>
                        <h2>${category.title}</h2>
                        <p>${category.description || ""}</p>
                    </div>
                    <span>${category.reports.length}</span>
                </div>
                <div class="report-card-grid">
                    ${category.reports.map(renderReport).join("")}
                </div>
            </section>
        `;
    }

    function filterMenu(query) {
        return menuData
            .map((category) => ({
                ...category,
                reports: (category.reports || []).filter((report) => matchesReport(report, query, category))
            }))
            .filter((category) => category.reports.length > 0);
    }

    function render() {
        const query = normalize(searchEl.value);
        const filtered = filterMenu(query);
        const total = countReports(filtered);

        countEl.textContent = `${total} report${total === 1 ? "" : "s"}`;
        contentEl.innerHTML = filtered.map(renderCategory).join("");
        emptyEl.classList.toggle("hidden", total > 0);
    }

    searchEl.addEventListener("input", render);
    render();
})();

(function () {
    const menuData = Array.isArray(window.PARTY_REPORT_MENU_DATA)
        ? window.PARTY_REPORT_MENU_DATA
        : [];
    const contentEl = document.getElementById("partyReportMenuContent");
    const searchEl = document.getElementById("partyReportSearch");
    const countEl = document.getElementById("partyReportCount");
    const emptyEl = document.getElementById("partyReportEmptyState");

    function normalize(value) {
        return String(value || "").trim().toLowerCase();
    }

    function escapeHtml(value) {
        const element = document.createElement("div");
        element.textContent = String(value || "");
        return element.innerHTML;
    }

    function matchesReport(report, query, category) {
        if (!query) return true;
        return [
            report.title,
            report.description,
            report.href,
            category.title,
            ...(report.tags || [])
        ].map(normalize).join(" ").includes(query);
    }

    function renderReport(report) {
        const tags = (report.tags || []).slice(0, 3);
        return `
            <a class="report-card" href="${escapeHtml(report.href || "#")}" data-report-id="${escapeHtml(report.id)}">
                <span class="report-card-sequence">${escapeHtml(report.sequence)}</span>
                <span class="report-card-body">
                    <span class="report-card-heading">
                        <span class="report-card-icon material-symbols-outlined">${escapeHtml(report.icon || "article")}</span>
                        <span class="report-card-title">${escapeHtml(report.title)}</span>
                    </span>
                    <span class="report-card-description">${escapeHtml(report.description)}</span>
                    <span class="report-card-tags">
                        ${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}
                    </span>
                </span>
                <span class="report-card-action material-symbols-outlined">arrow_forward</span>
            </a>
        `;
    }

    function renderCategory(category) {
        return `
            <section class="report-category report-accent-${escapeHtml(category.accent || "blue")}">
                <div class="report-category-header">
                    <div>
                        <h2>${escapeHtml(category.title)}</h2>
                        <p>${escapeHtml(category.description)}</p>
                    </div>
                    <span>${category.reports.length}</span>
                </div>
                <div class="report-card-grid">${category.reports.map(renderReport).join("")}</div>
            </section>
        `;
    }

    function render() {
        const query = normalize(searchEl.value);
        const filtered = menuData
            .map((category) => ({
                ...category,
                reports: category.reports.filter((report) => matchesReport(report, query, category))
            }))
            .filter((category) => category.reports.length);
        const total = filtered.reduce((sum, category) => sum + category.reports.length, 0);

        countEl.textContent = `${total} report${total === 1 ? "" : "s"}`;
        contentEl.innerHTML = filtered.map(renderCategory).join("");
        emptyEl.classList.toggle("hidden", total > 0);
    }

    searchEl.addEventListener("input", render);
    render();
})();

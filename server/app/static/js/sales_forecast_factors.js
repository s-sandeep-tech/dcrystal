(() => {
    const names = {weather: 'Weather', gold: 'Gold Price', festivals: 'National Festivals',
        regional_festivals: 'Regional Festivals', weddings: 'Wedding Calendar'};
    const fields = {rain_mm: 'Rain (mm)', max_temp_c: 'Maximum temperature (C)', price_usd_oz: 'Gold (USD/troy oz)',
        dhanteras_proximity: 'Dhanteras proximity', akshaya_proximity: 'Akshaya Tritiya proximity',
        festival_day: 'Festival day', festival_lead_7: 'Festival lead (7 days)', festival_after_7: 'Festival lag (7 days)',
        wedding_season: 'Wedding season', days_to_wedding: 'Days to wedding', wedding_dates_next_7: 'Wedding dates (7 days)'};
    const modelNames = {weekday_average: 'Weekday Average', prophet: 'Prophet', external_weather: 'Weather',
        external_gold: 'Gold', external_festivals: 'National Festivals', external_combined: 'Weather + Gold + National Festivals',
        external_regional_festivals: 'Regional Festivals', external_weddings: 'Weddings',
        external_regional_calendar: 'Regional Festivals + Weddings', external_all: 'All External Factors'};
    const el = id => document.getElementById(id);
    const number = value => typeof value === 'number' && Number.isFinite(value)
        ? value.toLocaleString('en-IN', {maximumFractionDigits: 3}) : value == null ? 'Not supplied' : String(value);
    const mae = value => typeof value === 'number' ? (value / 100000).toLocaleString('en-IN', {maximumFractionDigits: 3}) : 'Not recorded';
    function line(parent, text, className) {
        const node = document.createElement('div'); node.textContent = text;
        if (className) node.className = className;
        parent.append(node); return node;
    }
    function values(cell, key, data) {
        if (!data) { line(cell, 'Not fetched / not recorded'); return; }
        if (key === 'weather') {
            for (const day of data.days || []) line(cell, `${day.date}: ${number(day.min_temp_c)}–${number(day.max_temp_c)} C · Rain ${number(day.rain_mm)} mm · Chance ${number(day.rain_chance_pct)}%`);
        } else if (key === 'gold' && data.price != null) {
            line(cell, `${data.currency || 'Currency not recorded'} ${number(data.price)} / ${data.unit || 'Unit not recorded'}`);
            line(cell, `Observed: ${data.observed_at || 'Not recorded'}`, 'sf-factor-secondary');
        } else {
            for (const event of data.events || []) line(cell, `${event.name}: ${event.date}${event.end_date && event.end_date !== event.date ? ` to ${event.end_date}` : ''}`);
        }
        if (!cell.childNodes.length) line(cell, data.message || 'No values supplied');
        if (data.provider || data.region) line(cell, [data.provider, data.region].filter(Boolean).join(' · '), 'sf-factor-secondary');
    }
    window.renderSalesForecastFactors = result => {
        const metrics = result?.metrics || {}, context = result?.external_context || {};
        const used = metrics.external_features_used || [];
        const scored = metrics.candidate_mae || {}, rejected = metrics.unavailable_methods || {};
        el('sf-decision').textContent = !result ? 'No saved forecast available.'
            : used.length ? `Selected: ${modelNames[metrics.engine] || metrics.engine}. Factors used: ${used.map(k => names[k] || k).join(', ')}.`
            : `Selected baseline: ${modelNames[metrics.engine] || metrics.engine || 'Not recorded'}. ${metrics.fallback_reason || 'The saved forecast does not record a fallback reason.'}`;
        el('sf-factor-meta').textContent = result ? `Forecast: ${result.forecast?.[0]?.ds || '—'} to ${result.forecast?.at(-1)?.ds || '—'} · Baseline MAE ${mae(metrics.baseline_mae)} lakhs · Selected MAE ${mae(metrics.backtest_mae)} lakhs · Validation ${metrics.backtest_days || 'not recorded'} days${metrics.feature_forecast_origin ? ` · Input cutoff ${metrics.feature_forecast_origin}` : ''}` : '';
        el('sf-factor-rows').replaceChildren();
        for (const [key, label] of Object.entries(names)) {
            const tr = document.createElement('tr');
            const cells = Array.from({length: 4}, () => { const td = document.createElement('td'); tr.append(td); return td; });
            line(cells[0], label, 'sf-factor-name');
            const data = context.parameters?.[key];
            values(cells[1], key, data);
            const isUsed = used.includes(key);
            line(cells[2], isUsed ? 'Used' : result ? 'Not used' : 'No forecast', isUsed ? 'sf-factor-used' : 'sf-factor-secondary');
            if (isUsed) {
                const inputs = (result.external_feature_inputs || []).filter(row => row.factor === key);
                if (inputs.length) {
                    const details = document.createElement('details'), summary = document.createElement('summary');
                    summary.textContent = 'Inputs used by date'; details.append(summary);
                    for (const input of inputs) {
                        line(details, input.date, 'sf-factor-name');
                        for (const [field, value] of Object.entries(input.values || {}))
                            line(details, `${fields[field] || field}: ${number(value)}${field === 'days_to_wedding' && value === 31 ? ' (none within 30 days)' : ''}`);
                    }
                    cells[2].append(details);
                } else line(cells[2], 'Exact inputs were not recorded in this saved forecast.', 'sf-factor-secondary');
            }
            const single = `external_${key}`;
            const reason = isUsed ? 'Selected through backtesting; required forecast inputs available.'
                : rejected[single] || (scored[single] != null ? 'Not selected: another model won or the required 5% baseline improvement was not met.'
                    : context.status === 'disabled' ? 'External data was disabled for this forecast.'
                    : metrics.fallback_reason || 'No model decision recorded for this factor.');
            line(cells[3], result ? reason : 'Generate a forecast to view factor decisions.');
            if (data?.status) line(cells[3], `Fetch coverage: ${data.status}`, 'sf-factor-secondary');
            if (data?.missing_events?.length) line(cells[3], `Missing: ${data.missing_events.join(', ')}`, 'sf-factor-secondary');
            if (data?.coverage_years) line(cells[3], `Complete calendar years: ${data.coverage_years.join(', ') || 'None'}`, 'sf-factor-secondary');
            if (data?.message && data.status !== 'available') line(cells[3], data.message, 'sf-factor-secondary');
            el('sf-factor-rows').append(tr);
        }
        el('sf-model-rows').replaceChildren();
        for (const name of new Set([...Object.keys(scored), ...Object.keys(rejected)])) {
            const tr = document.createElement('tr');
            for (const text of [modelNames[name] || name, mae(scored[name]), name === metrics.engine ? 'Selected' : rejected[name] || 'Not selected']) {
                const td = document.createElement('td'); td.textContent = text; tr.append(td);
            }
            el('sf-model-rows').append(tr);
        }
        if (!el('sf-model-rows').childNodes.length) {
            const tr = document.createElement('tr'), td = document.createElement('td'); td.colSpan = 3;
            td.textContent = 'Model comparison not recorded.'; tr.append(td); el('sf-model-rows').append(tr);
        }
    };
})();

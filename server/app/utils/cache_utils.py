REPORT_CACHE_PREFIXES = (
    'prov_alloc_', 'prov_stock_status_', 'loc_phys_stock_status_',
    'online_provision_stock_status_', 'loc_prov_stock_analysis_',
    'location_provision_stock_analysis_', 'section_wise_provision_stock_summary_',
    'opo_', 'pending_acc_', 'rejected_wt_', 'bw_',
    'order_fulfillment_aging_matrix_partial:', 'location_wise_old_gold_report:',
    'pending_order_owner_names:', 'customer_order_owner_names:',
    'akt_perf_cache_', 'sales-xyz-drilldown:', 'nip-stock-trend:', 'purchase-plan:',
)


def clear_report_cache(client):
    """Invalidate report data without deleting queues, locks, or session state."""
    batch = []
    deleted = 0
    for key in client.scan_iter(count=500):
        name = key.decode() if isinstance(key, bytes) else key
        if name.startswith(REPORT_CACHE_PREFIXES) and not name.endswith(':lock'):
            batch.append(key)
            if len(batch) == 500:
                deleted += client.delete(*batch)
                batch = []
    if batch:
        deleted += client.delete(*batch)
    return deleted


def generate_cache_key(prefix, snapshot_date=None, **kwargs):
    """
    Generates a unique cache key based on the prefix, snapshot date, and filter arguments.
    The snapshot_date ensures data invalidation when new data is uploaded.
    """
    # Sort keys to ensure consistent order
    sorted_kwargs = dict(sorted(kwargs.items()))
    # Create a string representation of the arguments
    args_str = ":".join(f"{k}={v}" for k, v in sorted_kwargs.items() if v)
    
    # Format date string for the key
    date_str = snapshot_date.strftime("%Y%m%d%H%M%S") if snapshot_date else "latest"
    
    return f"{prefix}:{date_str}:{args_str}"

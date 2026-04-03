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

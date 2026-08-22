def parse_int_safe(val):
    try:
        return int(val)
    except Exception:
        return None

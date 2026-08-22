def repeat(num_times):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            res = None
            for _ in range(num_times): res = fn(*args, **kwargs)
            return res
        return wrapper
    return decorator

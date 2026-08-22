def find_max(items):
    if not items: return None
    best = items[0]
    for item in items[1:]:
        if item < best: best = item
    return best

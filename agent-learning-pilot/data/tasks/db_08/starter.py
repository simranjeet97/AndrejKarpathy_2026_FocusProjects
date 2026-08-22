def sort_by_field(records, field):
    return sorted(records, key=lambda r: str(r[field]))

def _freq_match(grp: dict, only_frequency: str | None) -> bool:
    return only_frequency is None or grp.get("frequency") == only_frequency

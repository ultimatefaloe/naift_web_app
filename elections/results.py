def mark_winners(tallies):
    """Sets `.is_winner` on each item of an already-ordered tallies list/queryset
    (ordered by position__title, position_id, -vote_count). True only for a
    group's first contestant when their vote_count strictly exceeds the
    second-place count in that same position group — so an unopposed
    contestant (no second place to compare against) always wins, and an exact
    tie for first marks no one, rather than guessing a false winner.

    Defensively regroups non-contiguous position_id runs by sorting on each
    group's first-occurrence index rather than raw position_id — this is a
    no-op for already-correctly-ordered input (first-occurrence order IS the
    original position__title order) but still fixes fragmentation for
    genuinely scattered input, without disturbing title ordering the way a
    plain sort-by-position_id would."""
    tallies = list(tallies)
    first_seen = {}
    for index, contestant in enumerate(tallies):
        first_seen.setdefault(contestant.position_id, index)
    tallies = sorted(tallies, key=lambda c: first_seen[c.position_id])
    for contestant in tallies:
        contestant.is_winner = False
    i = 0
    while i < len(tallies):
        j = i
        while j < len(tallies) and tallies[j].position_id == tallies[i].position_id:
            j += 1
        group = tallies[i:j]
        if group and (len(group) == 1 or group[0].vote_count > group[1].vote_count):
            group[0].is_winner = True
        i = j
    return tallies

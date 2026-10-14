"""
Fuzzy matching for the command bar.

fuzzy_score("nf", "New Folder") gives a score when the query's letters appear
in order in the text; better matches (word starts, consecutive letters,
early matches) score higher.
"""


def fuzzy_score(query, text):
    """Score how well query matches text; None when it doesn't match at all."""
    query = query.lower().replace(" ", "")
    if not query:
        return 0
    lower = text.lower()
    score, position, previous = 0, 0, -2
    for char in query:
        index = lower.find(char, position)
        if index < 0:
            return None
        score += 1
        if index == previous + 1:
            score += 5  # Consecutive letters
        if index == 0 or not lower[index - 1].isalnum():
            score += 8  # Start of a word
        previous, position = index, index + 1
    if lower.startswith(query):
        score += 10
    return score - len(text) * 0.01  # Prefer shorter texts on ties


def rank(query, items, key=lambda item: item):
    """items that match query, best first (all items, unchanged, for an empty query)."""
    if not query.strip():
        return list(items)
    scored = [(fuzzy_score(query, key(item)), i, item) for i, item in enumerate(items)]
    return [item for score, _, item in sorted((s for s in scored if s[0] is not None),
                                               key=lambda s: (-s[0], s[1]))]

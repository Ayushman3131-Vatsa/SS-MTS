from typing import Literal

AccessLevel = Literal["none", "view", "modify"]

ACCESS_RANK: dict[AccessLevel, int] = {
    "none": 0,
    "view": 1,
    "modify": 2,
}


def most_permissive(*levels: AccessLevel | None) -> AccessLevel:
    winner: AccessLevel = "none"
    for level in levels:
        if level is None:
            continue
        if ACCESS_RANK[level] > ACCESS_RANK[winner]:
            winner = level
    return winner

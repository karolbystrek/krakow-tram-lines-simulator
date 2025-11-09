from math import dist
from typing import List


def route_segment_coords(s_start, s_end, route) -> List[(float, float)]:

    start = min(range(len(route)), key=lambda i: dist(s_start, route[i]))
    end = min(range(len(route)), key=lambda i: dist(s_end, route[i]))

    if start <= end:
        return route[start:end + 1]
    else:

        return route[start:end - 1:-1]

from __future__ import annotations

from math import atan2, sqrt


def displacement(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return b[0] - a[0], b[1] - a[1]


def magnitude(vector: tuple[float, float]) -> float:
    return sqrt(vector[0] * vector[0] + vector[1] * vector[1])


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return magnitude(displacement(a, b))


def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = displacement(a, b)
    if dx == 0 and dy == 0:
        raise ValueError("degenerate bearing")
    result = atan2(dy, dx)
    return 3.141592653589793 if result == -3.141592653589793 else result


def corridor(a: tuple[float, float], b: tuple[float, float]) -> tuple[tuple[float, float], ...]:
    length = distance(a, b)
    if length == 0:
        raise ValueError("degenerate corridor")
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    return ((a[0]+nx, a[1]+ny), (b[0]+nx, b[1]+ny), (b[0]-nx, b[1]-ny), (a[0]-nx, a[1]-ny), (a[0]+nx, a[1]+ny))


def point_in_corridor(point: tuple[float, float], polygon: tuple[tuple[float, float], ...]) -> bool:
    return all((polygon[i+1][0]-polygon[i][0])*(point[1]-polygon[i][1]) - (polygon[i+1][1]-polygon[i][1])*(point[0]-polygon[i][0]) <= 0 for i in range(4))


def point_segment_distance(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0]-a[0], b[1]-a[1]
    length_sq = dx*dx + dy*dy
    if length_sq == 0:
        return distance(point, a)
    t = max(0.0, min(1.0, ((point[0]-a[0])*dx + (point[1]-a[1])*dy) / length_sq))
    return distance(point, (a[0]+t*dx, a[1]+t*dy))

from __future__ import annotations

from statistics import median
from typing import Any, Iterable


def event_timestamp(event: dict[str, Any]) -> float:
    return float(event.get("timestamp") or event.get("animation_timestamp") or 0.0)


def find_nearest_event(timestamp: float, events: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    event_list = list(events)
    if not event_list:
        return None
    return min(event_list, key=lambda event: abs(event_timestamp(event) - timestamp))


def estimate_video_offset(event_times: Iterable[tuple[float, float] | dict[str, float]]) -> float:
    offsets: list[float] = []
    for item in event_times:
        if isinstance(item, dict):
            if "video_time" not in item or "event_time" not in item:
                continue
            offsets.append(float(item["video_time"]) - float(item["event_time"]))
        else:
            event_time, video_time = item
            offsets.append(float(video_time) - float(event_time))
    if not offsets:
        return 0.0
    return float(median(offsets))

"""Arrival validation; checks client sample consistency, not spoof resistance."""

import math
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from ..jobs import CONFIG
from ..social.core import SocialError, timestamp


class CaptureLocation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0)
    captured_at: AwareDatetime
    source: Literal["gps"]


def distance(a, b):
    lat1, lat2 = map(math.radians, (a["latitude"], b["latitude"]))
    dl = math.radians(b["longitude"] - a["longitude"])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dl / 2) ** 2
    )
    return 6371000 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def check_location(sample, mission, time):
    if sample is None:
        raise SocialError(422, "Capture GPS is required", "validation_error")
    loc = CaptureLocation.model_validate(sample)
    age = (time - loc.captured_at).total_seconds()
    if (
        loc.accuracy_m > CONFIG["capture_accuracy_max_m"]
        or age > CONFIG["capture_max_age_seconds"]
        or age < -CONFIG["capture_future_tolerance_seconds"]
    ):
        raise SocialError(422, "Take a fresh, accurate GPS sample", "validation_error")
    radius = mission.get("arrival_radius_m", CONFIG["arrival_radius_m"])
    meters = distance(loc.model_dump(), mission["location"])
    if meters > radius:
        raise SocialError(
            409, "Move closer to the mission location", "location_out_of_range"
        )
    return {
        "within_radius": True,
        "distance_m": meters,
        "radius_m": radius,
        "accuracy_m": loc.accuracy_m,
        "checked_at": timestamp(time),
    }

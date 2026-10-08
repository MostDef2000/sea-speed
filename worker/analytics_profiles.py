"""Deterministic analytics profiles shared by Sea Speed worker entrypoints.

Profiles translate model-native classes into domain semantics without coupling
tracking, calibration, event transport, or API storage to one detector model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AnalyticsProfile:
    name: str
    domain: str
    default_camera_id: str
    model_name: str
    image_size: int
    confidence: float
    tracker: str
    sample_fps: float
    class_map: Mapping[str, str]
    frame_width: int = 1920
    frame_height: int = 1080

    @property
    def model_classes(self) -> frozenset[str]:
        return frozenset(self.class_map)

    def env_file_defaults(self) -> dict[str, str]:
        """String-serialized env-file defaults for the protected configure step.

        Single source for the non-secret values the deploy-side configure step
        writes into worker.env/road-worker.env; secret and operator overrides
        always win over these defaults.
        """
        fps = str(int(self.sample_fps)) if float(self.sample_fps).is_integer() else str(self.sample_fps)
        return {
            "ANALYTICS_PROFILE": self.name,
            "CAMERA_ID": self.default_camera_id,
            "MODEL_NAME": self.model_name,
            "YOLO_TRACKER": self.tracker,
            "YOLO_IMAGE_SIZE": str(self.image_size),
            "YOLO_CONFIDENCE": f"{self.confidence:.2f}",
            "SAMPLE_FPS": fps,
        }


PROFILES: dict[str, AnalyticsProfile] = {
    "water-v1": AnalyticsProfile(
        name="water-v1",
        domain="water",
        default_camera_id="cam1",
        model_name="models/yolo26x.pt",
        image_size=960,
        confidence=0.10,
        tracker="bytetrack.yaml",
        sample_fps=10.0,
        class_map={"boat": "vessel"},
        frame_width=1920,
        frame_height=1080,
    ),
    "road-v1": AnalyticsProfile(
        name="road-v1",
        domain="road",
        default_camera_id="road1",
        model_name="models/yolo26x.pt",
        image_size=960,
        confidence=0.15,
        tracker="bytetrack.yaml",
        sample_fps=10.0,
        class_map={
            "car": "car",
            "truck": "truck",
            "bus": "bus",
            "motorcycle": "motorcycle",
            "bicycle": "bicycle",
            "person": "person",
        },
        frame_width=1920,
        frame_height=1080,
    ),
}
DEFAULT_PROFILE = "water-v1"


def get_profile(name: str | None = None) -> AnalyticsProfile:
    resolved = (name or DEFAULT_PROFILE).strip()
    try:
        return PROFILES[resolved]
    except KeyError as exc:
        raise ValueError(f"unsupported analytics profile: {resolved}") from exc


def normalize_model_class(model_class: str, profile_name: str | None = None) -> dict[str, str] | None:
    """Return canonical semantic fields for an accepted model class.

    `None` means the detector class is outside the selected profile and must not
    enter tracking/event semantics for that pipeline.
    """

    profile = get_profile(profile_name)
    raw = str(model_class).strip()
    object_type = profile.class_map.get(raw)
    if object_type is None:
        return None
    return {
        "analytics_profile": profile.name,
        "domain": profile.domain,
        "object_type": object_type,
        "model_class": raw,
        "class_name": object_type,
    }


def profile_defaults(profile_name: str | None = None) -> dict[str, object]:
    profile = get_profile(profile_name)
    return {
        "ANALYTICS_PROFILE": profile.name,
        "CAMERA_ID": profile.default_camera_id,
        "MODEL_NAME": profile.model_name,
        "YOLO_IMAGE_SIZE": profile.image_size,
        "YOLO_CONFIDENCE": profile.confidence,
        "YOLO_TRACKER": profile.tracker,
        "SAMPLE_FPS": profile.sample_fps,
        "FRAME_WIDTH": profile.frame_width,
        "FRAME_HEIGHT": profile.frame_height,
    }

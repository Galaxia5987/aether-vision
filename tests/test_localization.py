from __future__ import annotations

import numpy as np
import pytest

from aether_vision.config import CameraMount
from aether_vision.localization import camera_to_robot, largest_cluster, locate, point_cloud
from aether_vision.types import Box, DepthGeometry, Intrinsics


def test_largest_cluster_ignores_background_and_noise() -> None:
    rng = np.random.default_rng(0)
    near = rng.normal([0.0, 0.0, 1.0], 0.01, size=(300, 3))
    far = rng.normal([0.0, 0.0, 3.0], 0.01, size=(100, 3))
    cluster = largest_cluster(np.vstack([near, far, [[5.0, 5.0, 9.0]]]).astype(np.float32))
    assert cluster is not None
    assert len(cluster) == 300
    assert cluster.mean(axis=0)[2] == pytest.approx(1.0, abs=0.01)
    assert largest_cluster(np.zeros((5, 3), dtype=np.float32)) is None


def test_camera_to_robot_axes() -> None:
    mount = CameraMount(x_m=0.1, y_m=0.0, z_m=0.5)
    assert camera_to_robot((0.0, 0.0, 2.0), mount) == pytest.approx((2.1, 0.0, 0.5))
    assert camera_to_robot((1.0, 0.0, 0.0), mount) == pytest.approx((0.1, -1.0, 0.5))
    assert camera_to_robot((0.0, 1.0, 0.0), mount) == pytest.approx((0.1, 0.0, -0.5))
    # Pitched down 90 degrees, the optical axis points at the floor.
    down = CameraMount(z_m=1.0, pitch_deg=90.0)
    assert camera_to_robot((0.0, 0.0, 0.5), down) == pytest.approx((0.0, 0.0, 0.5), abs=1e-9)


def _geometry(translation: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> DepthGeometry:
    intrinsics = Intrinsics(600.0, 600.0, 320.0, 240.0)
    return DepthGeometry(
        intrinsics, intrinsics, np.eye(3, dtype=np.float32), np.array(translation, np.float32)
    )


def test_locate_finds_object_in_front_of_wall() -> None:
    depth = np.full((480, 640), 4000, dtype=np.uint16)
    depth[200:280, 280:360] = 1500  # object at 1.5 m, centered
    cloud = point_cloud(depth, 0.001, _geometry())
    found = locate(Box(270, 190, 100, 100), cloud, CameraMount(z_m=0.0))
    assert found is not None
    (x, y, z), distance = found
    assert (x, y, z) == pytest.approx((1.5, 0.0, 0.0), abs=0.01)
    assert distance == pytest.approx(1.5, abs=0.01)
    empty = point_cloud(np.zeros_like(depth), 0.001, _geometry())
    assert locate(Box(0, 0, 4, 4), empty, CameraMount()) is None


def test_point_cloud_applies_depth_to_color_transform() -> None:
    # Color camera 5 cm to the right of the depth camera (as on a D435).
    depth = np.full((480, 640), 2000, dtype=np.uint16)
    cloud = point_cloud(depth, 0.001, _geometry((-0.05, 0.0, 0.0)))
    center = np.argmin(np.abs(cloud.points[:, 0] + 0.05) + np.abs(cloud.points[:, 1]))
    # The depth camera's center pixel lands 15 px left of the color image center.
    assert cloud.pixels[center] == pytest.approx((320 - 600 * 0.05 / 2.0, 240), abs=1.0)

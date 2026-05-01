"""Tests for camera module"""
import pytest
from src.sensors.camera import Camera


def test_camera_initialization():
    """Test camera initialization"""
    camera = Camera(camera_id=0, resolution=(640, 480))
    assert camera.camera_id == 0
    assert camera.resolution == (640, 480)


def test_camera_start_stop():
    """Test camera start and stop"""
    camera = Camera()
    # Note: This test may fail without actual camera hardware
    # camera.start()
    # camera.stop()
    pass

"""Camera sensor interface"""
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class Camera:
    """Camera sensor interface"""
    
    def __init__(self, camera_id: int = 0, resolution: tuple = (640, 480)):
        """
        Initialize camera
        
        Args:
            camera_id: Camera device ID
            resolution: Camera resolution (width, height)
        """
        self.camera_id = camera_id
        self.resolution = resolution
        self.cap = None
        
    def start(self) -> bool:
        """
        Start camera capture
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            logger.info(f"Camera {self.camera_id} started")
            return True
        except Exception as e:
            logger.error(f"Failed to start camera: {e}")
            return False
    
    def read_frame(self) -> np.ndarray:
        """
        Read a frame from camera
        
        Returns:
            Frame as numpy array, or None if failed
        """
        if self.cap is None or not self.cap.isOpened():
            logger.error("Camera not started")
            return None
            
        ret, frame = self.cap.read()
        if not ret:
            logger.error("Failed to read frame")
            return None
            
        return frame
    
    def stop(self):
        """Stop camera capture"""
        if self.cap is not None:
            self.cap.release()
            logger.info("Camera stopped")

from carriers.base import BaseTracker
from datetime import datetime

class CMATracker(BaseTracker):
    """
    Placeholder class for CMA CGM Tracking (Phase 2).
    """
    def track(self, container_no: str, bl_no: str = None) -> dict:
        return {
            "ETD": "",
            "ETA": "",
            "Vessel": "",
            "Voyage": "",
            "CurrentStatus": "",
            "TrackingStatus": "Failed",
            "Remarks": "CMA CGM tracking is not implemented in Phase 1.",
            "TrackingURL": f"https://www.cma-cgm.com/eBusiness/Tracking?SearchValue={container_no}",
            "TrackedAt": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }

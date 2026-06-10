from carriers.base import BaseTracker
from datetime import datetime

class HapagTracker(BaseTracker):
    """
    Placeholder class for Hapag-Lloyd Tracking (Phase 5).
    """
    def track(self, container_no: str, bl_no: str = None) -> dict:
        return {
            "ETD": "",
            "ETA": "",
            "Vessel": "",
            "Voyage": "",
            "CurrentStatus": "",
            "TrackingStatus": "Failed",
            "Remarks": "Hapag-Lloyd tracking is not implemented in Phase 1.",
            "TrackingURL": f"https://www.hapag-lloyd.com/en/online-business/track/track-by-container-solution.html?container={container_no}",
            "TrackedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

from carriers.base import BaseTracker
from datetime import datetime

class ONETracker(BaseTracker):
    """
    Placeholder class for ONE Line Tracking (Phase 3).
    """
    def track(self, container_no: str, bl_no: str = None) -> dict:
        return {
            "ETD": "",
            "ETA": "",
            "Vessel": "",
            "Voyage": "",
            "CurrentStatus": "",
            "TrackingStatus": "Failed",
            "Remarks": "ONE Line tracking is not implemented in Phase 1.",
            "TrackingURL": f"https://in.one-line.com/e-subscription/tracking?containerNo={container_no}",
            "TrackedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

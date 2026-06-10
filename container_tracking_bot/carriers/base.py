from abc import ABC, abstractmethod

class BaseTracker(ABC):
    """
    Abstract Base Class for all Shipping Line Trackers.
    Forces all implementing carrier classes to expose a consistent track() interface.
    """

    @abstractmethod
    def track(self, container_no: str, bl_no: str = None) -> dict:
        """
        Tracks a container (and optional B/L number) on the carrier's portal.
        
        Args:
            container_no (str): The container number to search.
            bl_no (str, optional): The Bill of Lading number if applicable.
            
        Returns:
            dict: A dictionary containing tracking results:
                {
                    "ETD": str (YYYY-MM-DD or None),
                    "ETA": str (YYYY-MM-DD or None),
                    "Vessel": str,
                    "Voyage": str,
                    "CurrentStatus": str,
                    "TrackingStatus": str ("Success", "No Data Found", "Manual Required", "Failed"),
                    "Remarks": str,
                    "TrackingURL": str,
                    "TrackedAt": str (YYYY-MM-DD HH:MM:SS)
                }
        """
        pass

    def close(self):
        """
        Closes any underlying resources (like browser sessions).
        Implemented by subclasses if they maintain persistent connections.
        """
        pass

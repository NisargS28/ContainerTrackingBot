import time
import os
import sys
from datetime import datetime

# Adjust path to include the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import (
    INPUT_FILE, OUTPUT_DIR, OUTPUT_REFERENCE_FILE, DELAY_BETWEEN_TRACKING
)
from utils.logger import logger
from utils.excel_handler import (
    read_input_workbook,
    sync_input_to_output,
    extract_candidates_for_carrier,
    write_results_to_reference,
)
from utils.text_utils import extract_date_from_text
from carriers.msc import MSCTracker
from carriers.maersk import MaerskTracker
from carriers.one import ONETracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _determine_delivery_status(res, original_del_status):
    """
    Derives a final DeliveryStatus string from the tracking result.

    Rules:
      - Success + ETA in the future  → "NotDelivered"
      - Success + ETA in the past    → "Delivered"
      - Success + no ETA             → "Not Updated"
      - Failed / Manual / No Data    → "Not Updated"
      - Anything else                → keep the original value from Excel
    """
    tracking_status = res.get("TrackingStatus", "")
    if tracking_status == "Success":
        eta_val = res.get("ETA", "")
        if eta_val:
            eta_dt = extract_date_from_text(eta_val)
            if eta_dt:
                return "Delivered" if eta_dt < datetime.now() else "NotDelivered"
        return "Not Updated"
    elif tracking_status in ("Failed", "Manual Required", "No Data Found"):
        return original_del_status if original_del_status else "Not Updated"
    return original_del_status


def _make_error_result(container_no, error_msg):
    """Returns a failure result dict for a container that raised an exception."""
    return {
        "ETD": "",
        "ETA": "",
        "Vessel": "",
        "Voyage": "",
        "CurrentStatus": "",
        "TrackingStatus": "Failed",
        "Remarks": error_msg,
        "TrackingURL": "",
        "TrackedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# Per-sheet tracking
# ---------------------------------------------------------------------------

def _track_sheet(sheet_name, candidates, tracker, containers_tracked_so_far, carrier_name):
    """
    Tracks all containers for one sheet and returns the result list.

    `containers_tracked_so_far` drives the inter-request delay: the very first
    container ever (across all sheets) skips the delay so the run starts quickly.
    """
    sheet_results = []

    for local_idx, item in enumerate(candidates, 1):
        container_no = item["ContainerNo"]
        bl_no        = item["BLNo"]
        row_idx      = item["OriginalExcelRow"]
        del_status   = item["DeliveryStatus"]
        s_line       = item["SLine"]

        overall_count = containers_tracked_so_far + local_idx
        logger.info(
            f"  [{local_idx}/{len(candidates)}] Container: {container_no} "
            f"(Row {row_idx})"
        )

        if not container_no:
            res = {
                "ETD": "", "ETA": "", "Vessel": "", "Voyage": "",
                "CurrentStatus": "", "TrackingStatus": "Skipped (Blank)",
                "Remarks": "Container number is blank in Excel.",
                "TrackingURL": "",
                "TrackedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            try:
                # Apply inter-request delay after the first container
                if overall_count > 1:
                    logger.info(
                        f"  Waiting {DELAY_BETWEEN_TRACKING}s before next request..."
                    )
                    time.sleep(DELAY_BETWEEN_TRACKING)
                res = tracker.track(container_no, bl_no)
            except Exception as exc:
                logger.error(f"  Unexpected error tracking {container_no}: {exc}")
                res = _make_error_result(container_no, str(exc))

        # Enrich result with source metadata
        res["SheetName"]        = sheet_name
        res["OriginalExcelRow"] = row_idx
        res["SLine"]            = s_line
        res["Carrier"]          = carrier_name
        res["BLNo"]             = bl_no
        res["ContainerNo"]      = container_no
        res["DeliveryStatus"]   = _determine_delivery_status(res, del_status)

        sheet_results.append(res)

    return sheet_results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_tracking():
    logger.info("=" * 60)
    logger.info("Starting Container Tracking Automation")
    logger.info("=" * 60)

    # 1. Verify input file
    if not os.path.exists(INPUT_FILE):
        logger.error(f"Input Excel file not found: {INPUT_FILE}")
        logger.error("Place Export.xlsx in the 'input/' folder or update config.py.")
        sys.exit(1)

    # 2. Open workbook
    try:
        wb = read_input_workbook(INPUT_FILE)
    except Exception as exc:
        logger.error(f"Failed to open workbook: {exc}")
        sys.exit(1)

    # 3. Determine which sheets to process (skip Excel default temp sheets)
    sheets_to_process = [
        s for s in wb.sheetnames if not s.lower().startswith("sheet")
    ]
    if not sheets_to_process:
        logger.warning("No processable sheets found in the workbook.")
        sys.exit(0)

    logger.info(f"Sheets to process: {sheets_to_process}")
    logger.info(f"Reference output file: {OUTPUT_REFERENCE_FILE}")

    # 4. Initialise trackers
    trackers = {
        "MSC": MSCTracker(),
        "MAERSK": MaerskTracker(),
        "ONE": ONETracker()
    }
    total_tracked = 0

    try:
        for sheet_name in sheets_to_process:
            logger.info("=" * 60)
            logger.info(f"Processing sheet: {sheet_name}")
            logger.info("=" * 60)

            # 1. Sync S/Line and Container No from input file to output file first
            sync_ok = sync_input_to_output(INPUT_FILE, OUTPUT_REFERENCE_FILE, sheet_name)
            if not sync_ok:
                logger.error(f"Sync failed for sheet '{sheet_name}'. Skipping tracking for this sheet.")
                continue

            for carrier_name, tracker in trackers.items():
                candidates = extract_candidates_for_carrier(OUTPUT_REFERENCE_FILE, sheet_name, carrier_name)

                if not candidates:
                    logger.warning(
                        f"No {carrier_name} containers to track in '{sheet_name}' "
                        f"(already Delivered or no {carrier_name} rows found). Skipping."
                    )
                    continue

                logger.info(f"Found {len(candidates)} {carrier_name} containers to track in '{sheet_name}'.")

                sheet_results = []
                try:
                    sheet_results = _track_sheet(
                        sheet_name, candidates, tracker, total_tracked, carrier_name
                    )
                    total_tracked += len(sheet_results)
                except KeyboardInterrupt:
                    logger.warning(
                        f"Interrupted during '{sheet_name}' ({carrier_name}). Saving partial results."
                    )
                    if sheet_results:
                        write_results_to_reference(
                            sheet_results, OUTPUT_REFERENCE_FILE, sheet_name
                        )
                    raise  # re-raise to hit the outer handler

                # Write results for this sheet/carrier
                if sheet_results:
                    write_results_to_reference(
                        sheet_results, OUTPUT_REFERENCE_FILE, sheet_name
                    )
                    logger.info(
                        f"Sheet '{sheet_name}' ({carrier_name}) complete — "
                        f"{len(sheet_results)} containers processed."
                    )

    except KeyboardInterrupt:
        logger.warning("Tracking aborted by user.")
    finally:
        for tracker in trackers.values():
            tracker.close()

    # 6. Final summary
    logger.info("=" * 60)
    logger.info("Tracking run finished.")
    logger.info(f"Total containers tracked across all sheets: {total_tracked}")
    logger.info(f"Reference file: {OUTPUT_REFERENCE_FILE}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_tracking()

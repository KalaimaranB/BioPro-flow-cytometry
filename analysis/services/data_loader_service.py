"""Data loader service for handling FCS file loading and compensation.

Encapsulates data ingestion to adhere to SRP and DIP, preventing
high-level services like WorkflowService from depending directly
on concrete io functions.
"""

from pathlib import Path

from biopro_sdk.plugin import get_logger

from ..compensation import apply_compensation
from ..fcs_io import load_fcs

logger = get_logger(__name__, "flow_cytometry")


class DataLoaderService:
    """Service responsible for loading Flow Cytometry Standard data."""

    def reload_sample(self, sample, path: Path, compensation_matrix=None) -> bool:
        """Reload FCS event data for a given sample.

        Args:
            sample: The sample object to reload data into.
            path: Path to the FCS file.
            compensation_matrix: Optional compensation matrix to re-apply.

        Returns:
            bool: True if reload was successful, False otherwise.
        """
        if not path.exists():
            logger.warning(
                f"FCS file no longer exists: {path} (sample: {sample.display_name})"
            )
            return False

        try:
            fcs_data = load_fcs(path)

            # Re-apply compensation if it was active when saved
            if sample.is_compensated and compensation_matrix is not None:
                if not fcs_data.is_compensated:
                    fcs_data.events = apply_compensation(fcs_data, compensation_matrix)
                    fcs_data.is_compensated = True
                    logger.info(
                        f"Re-applied BioPro compensation matrix to reloaded sample '{sample.display_name}'"
                    )

            sample.fcs_data = fcs_data
            logger.info(
                f"Reloaded FCS data for '{sample.display_name}': {fcs_data.num_events} events"
            )
            return True
        except Exception as exc:
            logger.warning(f"Failed to reload FCS for '{sample.display_name}': {exc}")
            return False

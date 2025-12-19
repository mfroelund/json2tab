"""Module for auto-increment type index generator based on match result."""


import pandas as pd

from .logs import logger


class AutoIncrementTypeIndexGenerator:
    """The auto-increment type index generator based on match result."""

    def __init__(self, matched_line_index_key: str, type_idx_key: str = "type_idx"):
        """Initialize auto-increment type index generator.

        Args:
            matched_line_index_key (str): Column name with matched_line_index
            type_idx_key (str):           Column name to write type_index to
        """
        self.line_index_key = matched_line_index_key
        self.type_idx_key = type_idx_key
        self.unique_matched_lines = []

    def apply(self, turbines: pd.DataFrame) -> pd.DataFrame:
        """Apply the auto-increment type index generator to turbine location data.

        Args:
            turbines (pd.DataFrame): pandas.DataFrame with turbine location data

        Returns:
            pandas.DataFrame with turbine location data enriched with type_idx
        """
        # Store unique matched lines
        self.unique_matched_lines = turbines[self.line_index_key].unique().tolist()
        logger.info(f"Found {len(self.unique_matched_lines)} unique turbine types")

        turbines[self.type_idx_key] = turbines[self.line_index_key].apply(
            self.matched_line_index_to_type_idx
        )

        return turbines

    def matched_line_index_to_type_idx(self, matched_line_index: int) -> int:
        """Convert matched_line_index to type_idx.

        Args:
            matched_line_index (int): The line index in the turbine type database

        Returns:
            type_idx (int): One-based auto increment index for unique model_designation
        """
        return self.unique_matched_lines.index(matched_line_index) + 1

    def type_idx_to_matched_line_index(self, type_idx: int) -> int:
        """Convert type_idx to matched_line_index.

        Args:
            type_idx (int): One-based auto increment index for unique model_designation

        Returns:
            matched_line_index (int): The line index in the turbine type database
        """
        return self.unique_matched_lines[type_idx - 1]

    def max_type_idx(self) -> int:
        """Gets max value of auto-increment index type_idx."""
        return len(self.unique_matched_lines)

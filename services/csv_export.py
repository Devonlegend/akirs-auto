"""CSV export service."""

import csv
from pathlib import Path
from typing import List
from models import AdDetails


class CSVExportService:
    """Service to export ad data to CSV."""

    def __init__(self, output_path: str = "output/ads_social_links.csv"):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def export_ads(self, ads: List[AdDetails]) -> None:
        """Export ads with their social links to CSV."""
        rows = []

        # Flatten ads with multiple social links into multiple CSV rows
        for ad in ads:
            rows.extend(ad.to_csv_row())

        if not rows:
            print("No data to export.")
            return

        # Get all unique field names
        fieldnames = list(rows[0].keys()) if rows else []

        # Write to CSV
        with open(self.output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(
            f"✓ Exported {len(ads)} ads with {len(rows)} social links to {self.output_path}"
        )

    def append_ads(self, ads: List[AdDetails]) -> None:
        """Append ads to existing CSV file."""
        rows = []

        for ad in ads:
            rows.extend(ad.to_csv_row())

        if not rows:
            return

        fieldnames = list(rows[0].keys())

        # Check if file exists
        file_exists = self.output_path.exists()

        with open(self.output_path, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header only if file is new
            if not file_exists:
                writer.writeheader()

            writer.writerows(rows)

        print(f"✓ Appended {len(ads)} ads to {self.output_path}")

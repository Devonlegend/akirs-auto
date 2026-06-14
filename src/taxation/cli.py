"""CLI entry point: ``python -m taxation --limit N``."""

from __future__ import annotations

import argparse
import asyncio
import logging

from .processor import run_tax_classification


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify scraped advertisers for taxability via Ollama phi4-mini."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max advertisers to process."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging."
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    summary = asyncio.run(run_tax_classification(limit=args.limit))
    print(
        f"Processed: {summary['processed']} | "
        f"Taxable: {summary['taxable']} | "
        f"Errors: {len(summary['errors'])} | "
        f"{summary['elapsed_ms']:.0f} ms"
    )
    for err in summary["errors"]:
        print(f"  ! {err}")


if __name__ == "__main__":
    main()

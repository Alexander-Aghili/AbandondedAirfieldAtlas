"""Discover and extract the entire airfield catalog from linked source pages."""

import argparse

if not __package__:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.source import BASE, allowed, discover
from pipeline.parser import parse, coordinate_values
from pipeline.fetcher import Fetcher
from pipeline.crawler import crawl
from pipeline.reconciliation import retain_index_only, catalog_membership
from pipeline.publisher import DatasetPublisher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=".cache/source")
    parser.add_argument("--output", default="web/data")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--refresh", action="store_true", help="Refetch cached pages")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Rebuild from cache without any network requests",
    )
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    if args.refresh and args.offline:
        parser.error("--refresh and --offline cannot be combined")
    fetcher = Fetcher(args.cache, args.delay, args.refresh, args.offline)
    features, pages, failures, inventory, advertised = crawl(fetcher, args.pilot)
    DatasetPublisher(args.output, args.pilot, args.allow_partial).publish(
        features, pages, failures, inventory, advertised
    )


if __name__ == "__main__":
    main()

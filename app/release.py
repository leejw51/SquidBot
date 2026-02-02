#!/usr/bin/env python3
"""
Release script for SquidBot.
Creates a zip archive of the app folder for distribution.
"""

import os
import sys
import zipfile
from pathlib import Path


def should_exclude(path: Path, base_path: Path) -> bool:
    """Check if a file/directory should be excluded from the archive."""
    rel_path = path.relative_to(base_path)
    rel_str = str(rel_path)

    # Exclude patterns
    exclude_patterns = [
        "__pycache__",
        ".pytest_cache",
        ".git",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.egg-info",
        ".env",
        ".coverage",
        "htmlcov",
        "dist",
        "build",
        "*.spec",
        ".claude",
        "poetry.lock",
    ]

    for pattern in exclude_patterns:
        if pattern.startswith("*"):
            # Wildcard pattern - check extension
            if path.name.endswith(pattern[1:]):
                return True
        elif pattern in rel_str.split(os.sep):
            return True
        elif rel_str == pattern:
            return True

    return False


def create_release_zip(output_dir: Path = None, version: str = None) -> Path:
    """
    Create a zip archive of the app folder.

    Args:
        output_dir: Directory to save the zip file (default: parent of app folder)
        version: Version string for the archive name (default: timestamp)

    Returns:
        Path to the created zip file
    """
    # Get paths
    app_dir = Path(__file__).parent.resolve()
    if output_dir is None:
        output_dir = app_dir / "dist"

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate archive name
    if version:
        archive_name = f"squidbot-{version}.zip"
    else:
        archive_name = "squidbot.zip"

    archive_path = output_dir / archive_name

    print(f"Creating release archive: {archive_path}")
    print(f"Source: {app_dir}")

    # Create zip file
    file_count = 0
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(app_dir):
            root_path = Path(root)

            # Filter directories in-place to skip excluded ones
            dirs[:] = [d for d in dirs if not should_exclude(root_path / d, app_dir)]

            for file in files:
                file_path = root_path / file

                if should_exclude(file_path, app_dir):
                    continue

                # Archive path: app/...
                arc_path = Path("app") / file_path.relative_to(app_dir)
                zipf.write(file_path, arc_path)
                file_count += 1

    # Get file size
    size_mb = archive_path.stat().st_size / (1024 * 1024)

    print(f"Archive created successfully!")
    print(f"  Files: {file_count}")
    print(f"  Size: {size_mb:.2f} MB")
    print(f"  Path: {archive_path}")

    return archive_path


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Create SquidBot release archive")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output directory for the archive"
    )
    parser.add_argument(
        "-v", "--version",
        type=str,
        help="Version string for the archive name"
    )

    args = parser.parse_args()

    try:
        archive_path = create_release_zip(
            output_dir=args.output,
            version=args.version
        )
        print(f"\nRelease ready: {archive_path}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Pull all Docker images referenced in swe-bench-verified Dockerfiles."""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def get_images(dataset: Path):
    images = []
    for dockerfile in sorted(dataset.glob("*/environment/Dockerfile")):
        text = dockerfile.read_text()
        match = re.search(r"^FROM\s+(\S+)", text, re.MULTILINE)
        if match:
            images.append(match.group(1))
    return images


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    dataset: Path = args.dataset
    dataset = dataset.expanduser().resolve()
    
    if not dataset.exists():
        raise ValueError(f"Dataset {dataset} does not exist")
    
    images = get_images(dataset=dataset)
    print(f"Found {len(images)} images to pull\n")

    failed = []
    for i, image in enumerate(images, 1):
        print(f"[{i}/{len(images)}] Pulling {image}")
        result = subprocess.run(["docker", "pull", image], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  FAILED: {result.stderr.strip()}")
            failed.append(image)
        else:
            print(f"  OK")

    print(f"\nDone: {len(images) - len(failed)} succeeded, {len(failed)} failed")
    if failed:
        print("\nFailed images:")
        for img in failed:
            print(f"  {img}")
        sys.exit(1)


if __name__ == "__main__":
    main()

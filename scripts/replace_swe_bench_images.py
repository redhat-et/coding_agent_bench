"""Replace FROM images in swe-bench-verified Dockerfiles with ghcr.io/epoch-research images."""

import argparse
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("dataset", type=Path)
args = parser.parse_args()
dataset: Path = args.dataset
dataset = dataset.expanduser().resolve()

ARCH = "x86_64"

for dockerfile in sorted(dataset.glob("*/environment/Dockerfile")):
    instance_id = dockerfile.parent.parent.name
    new_image = f"ghcr.io/epoch-research/swe-bench.eval.{ARCH}.{instance_id}"

    text = dockerfile.read_text()
    new_text = re.sub(
        r"^(FROM\s+)\S+", rf"\1{new_image}", text, count=1, flags=re.MULTILINE
    )

    if text != new_text:
        dockerfile.write_text(new_text)
        print(f"Updated: {instance_id}")
    else:
        print(f"No FROM found: {instance_id}")

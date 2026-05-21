from pathlib import Path
import argparse
from coding_agent_bench.helpers.codex import codex_create_toml


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a Codex config.toml file for the model provider"
    )
    parser.add_argument("model_name", type=str, help="Name of the model")
    parser.add_argument("server_url", type=str, help="URL of the server")
    parser.add_argument(
        "-o",
        "--outdir",
        type=Path,
        help="Output directory. Defaults to current directory.",
        default=Path.cwd(),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    outpath = args.outdir / "config.toml"
    codex_create_toml(args.model_name, args.server_url, outpath)


if __name__ == "__main__":
    main()

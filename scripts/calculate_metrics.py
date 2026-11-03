"""Calculate Harbor metrics and prepare manually reviewed leaderboard candidates."""

# Keep the historical script entry point while sharing its implementation with
# the installed CLI and resumed job pods.
from coding_agent_bench.metrics import *  # noqa: F403


if __name__ == "__main__":
    main()  # noqa: F405

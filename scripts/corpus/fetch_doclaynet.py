"""Fetch the pinned DocLayNet seed pages into the ignored corpus tree."""

from pathlib import Path

from doclaynet.fetch import fetch


if __name__ == "__main__":
    fetch(Path(".delta/corpus/doclaynet"))

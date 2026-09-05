import re
import tomllib
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"


def load_config(path=CONFIG_PATH):
    with open(path, "rb") as f:
        return tomllib.load(f)


class TitleFilter:
    def __init__(self, config):
        self.include = re.compile("|".join(config["titles"]["include"]), re.I)
        self.exclude = re.compile("|".join(config["titles"]["exclude"]), re.I)

    def matches(self, title):
        return bool(self.include.search(title)) and not self.exclude.search(title)

import re
import tomllib
from datetime import date
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


class LocationFilter:
    """Locations are free text from each board, so this is a string rule and
    never proof of work eligibility - the posting itself decides."""

    def __init__(self, config):
        rules = config["locations"]
        self.include = re.compile("|".join(rules["include"]), re.I)
        self.exclude = re.compile("|".join(rules["exclude"]), re.I)

    def matches(self, location):
        if not location:
            return False
        return bool(self.include.search(location)) and not self.exclude.search(location)


class AgeFilter:
    def __init__(self, config, today=None):
        rules = config["freshness"]
        self.max_age = rules["max_age_days"]
        self.keep_undated = rules["keep_undated"]
        self.today = today or date.today()

    def matches(self, posted_at):
        if posted_at is None:
            return self.keep_undated
        return (self.today - posted_at).days <= self.max_age

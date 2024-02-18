import re
from typing import Any

import PTN
import structlog
from pydantic import BaseModel, Field, field_validator

# Constants for scoring
# Existing definitions with updated SEASON_MATCH_SCORES
RESOLUTION_SCORES = {"720p": 1, "1080p": 2, "2160p": 3, "4K": 3}

# Update bit positions if necessary, based on previous example they remain the same
NAME_MATCH_BIT_POS = 10  # Highest priority, using 3 bits
SEASON_MATCH_BIT_POS = 7  # Less than name match but higher than resolution, using 3 bits
RESOLUTION_BIT_POS = 4  # Next priority
AUDIO_BIT_POS = 2  # Lower priority
YEAR_MATCH_BIT_POS = 1  # Lowest priority, using 1 bit


class Torrent(BaseModel):
    title: str
    info_hash: str = ""
    episode: list[int] = []
    season: list[int] = []
    resolution: str = ""
    quality: str = ""
    codec: str = ""
    audio: str = ""
    filetype: str = ""
    encoder: str = ""
    language: list[str] = ["English"]
    bitDepth: int = 8
    hdr: bool = False
    year: int = 0
    raw_title: str = ""

    @field_validator("season", "episode", mode="before")
    @classmethod
    def ensure_is_list(cls: Any, v: Any):
        if v == None:
            return []
        if isinstance(v, int):
            return [v]
        return v

    @staticmethod
    def parse_title(title: str) -> "Torrent":
        meta: dict[Any, Any] = PTN.parse(title, standardise=True)
        meta["raw_title"] = title
        return Torrent(**meta)

    def score_series(self, season: int, episode: int) -> int:
        """
        Score a torrent based on season and episode where the rank is as follows:
        3 -> Whole series matches (len(self.season) > 0 and season in self.season and not self episode)
        2 -> Whole season matches (len(self.season) == 1 and season in self.season and not self.episode or episode in self.episode)
        1 -> Single episode matches (season in self.season and episode in self.episode)
        0 -> No match at all (not self.season and not self.episode)
        -1 -> Mismatch Season or episode ((self.season and season not in self.season) or (self.episode and episode not in self.episode))
        """
        if self.season and season not in self.season:
            # season mismatch
            return -10
        if self.episode and episode not in self.episode:
            # episode mismatch
            return -10
        if not self.season and not self.episode:
            # no season or episode
            return 0
        if len(self.season) > 1 and season in self.season:
            # series matches
            return 3
        if season in self.season and not self.episode:
            # whole season matches
            return 2
        if season in self.season and episode in self.episode:
            # single episode matches
            return 1
        return -10

    def score_name(self, title: str) -> int:
        sanitized_name: str = re.sub(r"\W+", r"\\W+", title)
        if re.search(rf"^{sanitized_name}$", self.title, re.IGNORECASE):
            # name match at the beginning of the string is the best
            return 2
        return -10

    def score_with(self, title: str, year: int, season: int = 0, episode: int = 0) -> int:
        name_match_score = self.score_name(title) << NAME_MATCH_BIT_POS
        if name_match_score < 0:
            return -1000

        season_match_score = (
            self.score_series(season=season, episode=episode) << SEASON_MATCH_BIT_POS
            if season and episode
            else 0
        )
        if season_match_score < 0:
            return -1000
        resolution_score = (
            RESOLUTION_SCORES[self.resolution] << RESOLUTION_BIT_POS if self.resolution else 0
        )
        audio_score = (
            2 if "7.1" in self.audio else 1 if "5.1" in self.audio else 0
        ) << AUDIO_BIT_POS

        year_match_score = (1 if self.year and self.year == year else 0) << YEAR_MATCH_BIT_POS
        result: int = (
            name_match_score
            | season_match_score
            | resolution_score
            | audio_score
            | year_match_score
        )
        return result


HIGHEST_NO_NAME_SCORE = Torrent.parse_title(
    title="Friends S01-S10 1994 COMPLETE 7.1 4k",
).score_with(title="Frazier", year=1994, season=5, episode=10)

HIGHEST_SCORE = Torrent.parse_title(
    title="Friends S01-S10 1994 COMPLETE 7.1 4k",
).score_with(title="Friends", year=1994, season=5, episode=10)


def max_score_for(resolution: str) -> int:
    return Torrent.parse_title(
        title=f"Friends S01-S10 1994 7.1 COMPLETE {resolution}",
    ).score_with(title="Friends", year=1994, season=5, episode=10)


def lowest_score_for(resolution: str) -> int:
    return Torrent.parse_title(
        title=f"Oppenheimer {resolution}",
    ).score_with(title="Oppenheimer", year=2022, season=1, episode=1)


def score_range_for(resolution: str) -> range:
    return range(lowest_score_for(resolution), max_score_for(resolution) + 1)

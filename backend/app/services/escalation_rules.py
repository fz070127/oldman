from datetime import datetime
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.models import Alarm

Target = Literal["family_primary", "guardian", "community_admin", "admin"]
ChannelName = Literal["PUSH", "SMS", "CALL", "WS", "INBOX"]


class Rule(BaseModel, frozen=True, extra="forbid"):
    after_sec: int = Field(gt=0, strict=True)
    to: Target
    channels: tuple[ChannelName, ...] = Field(min_length=1)


class RuleFile(BaseModel, extra="forbid"):
    default: tuple[Rule, ...] = Field(min_length=1)
    levels: dict[Literal["P0", "P1", "P2"], Literal["default"] | tuple[Rule, ...]]


class EscalationRules:
    def __init__(self, settings: Settings):
        self.path = settings.escalate_config_path
        self.time_scale = settings.escalate_time_scale
        self.revision = 0
        self.reload()

    def reload(self) -> None:
        config = RuleFile.model_validate(yaml.safe_load(self.path.read_text(encoding="utf-8")))
        levels = {
            level: config.default if rules == "default" else rules
            for level, rules in config.levels.items()
        }
        for rules in (config.default, *levels.values()):
            times = [rule.after_sec for rule in rules]
            if not times or times != sorted(set(times)):
                raise ValueError(
                    "after_sec must be strictly increasing within each escalation level"
                )
            if any(len(set(rule.channels)) != len(rule.channels) for rule in rules):
                raise ValueError("channels must be unique within each escalation rule")
        self.default, self.levels = config.default, levels
        self.revision += 1

    def for_level(self, level: str) -> tuple[Rule, ...]:
        return self.levels.get(level, self.default)

    def window(self, level: str, step: int) -> float | None:
        rules = self.for_level(level)
        if 1 <= step <= len(rules):
            return rules[step - 1].after_sec * self.time_scale
        return None

    def due(self, alarm: Alarm, step: int) -> float | None:
        window = self.window(alarm.level, step)
        if window is not None:
            # after_sec is cumulative from notified_at, never an interval from the prior step.
            return notified_at(alarm).timestamp() + window
        return None

    def target(self, level: str, step: int) -> Rule:
        rules = self.for_level(level)
        # Step zero is initial delivery. The last deadline reminds the final recipient.
        return rules[min(step, len(rules) - 1)]


def notified_at(alarm: Alarm) -> datetime:
    return alarm.notified_at or alarm.created_at

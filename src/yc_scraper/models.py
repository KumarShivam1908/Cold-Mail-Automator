from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Founder:
    name: str
    linkedin: str | None = None


@dataclass
class Company:
    name: str
    yc_url: str
    batch: str | None = None
    website: str | None = None
    industries: list[str] = field(default_factory=list)
    one_liner: str | None = None
    description: str | None = None
    founders: list[Founder] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

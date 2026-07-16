from dataclasses import dataclass, field


DEFAULT_BATCHES = [
    "Summer 2015",
    "Winter 2016",
    "Summer 2016",
    "Winter 2017",
    "Summer 2017",
    "Winter 2018",
    "Summer 2018",
    "Winter 2019",
    "Summer 2019",
    "Summer 2020",
    "Winter 2020",
    "Winter 2021",
    "Summer 2021",
    "Winter 2022",
    "Summer 2022",
    "Winter 2023",
    "Summer 2023",
    "Winter 2024",
    "Summer 2024",
    "Fall 2024",
    "Winter 2025",
    "Spring 2025",
    "Summer 2025",
    "Fall 2025",
    "Winter 2026",
    "Spring 2026",
    "Summer 2026",
]


@dataclass(frozen=True)
class ScrapeConfig:
    directory_url: str = "https://www.ycombinator.com/companies"
    hiring_only: bool = True
    batches: list[str] = field(default_factory=lambda: list(DEFAULT_BATCHES))
    request_timeout: int = 30
    delay_seconds: float = 0.5

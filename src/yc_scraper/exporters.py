import csv
import json
from pathlib import Path

from .models import Company


def write_json(companies: list[Company], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps([company.to_dict() for company in companies], indent=2), encoding="utf-8")


def write_csv(companies: list[Company], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = ["company", "batch", "website", "industries", "one_liner", "description", "founder_name", "founder_linkedin", "yc_url"]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for company in companies:
            for founder in company.founders or [None]:
                writer.writerow({
                    "company": company.name,
                    "batch": company.batch or "",
                    "website": company.website or "",
                    "industries": "; ".join(company.industries),
                    "one_liner": company.one_liner or "",
                    "description": company.description or "",
                    "founder_name": founder.name if founder else "",
                    "founder_linkedin": founder.linkedin if founder else "",
                    "yc_url": company.yc_url,
                })

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CollectedHTML:
    html: str
    status_code: int | None
    final_url: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        yield self.html
        yield self.status_code

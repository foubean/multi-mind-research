from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def make_lineage(
    *,
    provider: str,
    adapter: str,
    raw_source: str,
    transforms: list[dict[str, Any]],
    used_by: str,
    raw_ref: str | None = None,
) -> dict[str, Any]:
    lineage = {
        "provider": provider,
        "adapter": adapter,
        "raw_source": raw_source,
        "fetched_at": datetime.now(UTC).isoformat(),
        "transforms": transforms,
        "used_by": used_by,
    }
    if raw_ref:
        lineage["raw_ref"] = raw_ref
    return lineage

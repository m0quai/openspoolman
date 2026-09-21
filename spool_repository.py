"""OpenSpoolMan's narrow data-access boundary for spool inventory.

Application code should use this module instead of constructing SpoolMan API
requests or depending on SpoolMan's complete object model.  The implementation
currently delegates to :mod:`spoolman_client`; replacing that adapter later
with a local database does not require changing the callers.
"""

from typing import Any

import spoolman_client as _spoolman_api


def list_spools(*, include_archived: bool = False) -> list[dict[str, Any]]:
    """Return the inventory records needed by OpenSpoolMan."""
    return _spoolman_api.fetchSpoolList(include_archived=include_archived)


def get_spool(spool_id: int | str) -> dict[str, Any]:
    return _spoolman_api.getSpoolById(spool_id)


def record_consumption(
    spool_id: int | str,
    *,
    weight_grams: float | None = None,
    length_mm: float | None = None,
    occurred_at: str | None = None,
) -> bool:
    """Record one usage event in the inventory backend."""
    return _spoolman_api.consumeSpool(
        spool_id,
        use_weight=weight_grams,
        use_length=length_mm,
        occurred_at=occurred_at,
    )


def update_spool_extra(spool_id: int | str, old_extra: dict[str, Any] | None, **values: Any) -> None:
    """Update only OpenSpoolMan-owned spool metadata."""
    _spoolman_api.patchExtraTags(spool_id, dict(old_extra or {}), values)


def update_filament_metadata(
    filament_id: int | str,
    old_extra: dict[str, Any] | None,
    values: dict[str, Any],
) -> dict[str, Any]:
    return _spoolman_api.patchFilamentExtra(filament_id, old_extra, values)


def get_settings() -> dict[str, Any]:
    return _spoolman_api.fetchSettings()

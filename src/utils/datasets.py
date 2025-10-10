"""Utility helpers for working with dataset metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def load_snapshot_metadata(qlib_dir: Path) -> Dict[str, Any]:
    """Load snapshot metadata for a dataset if the file is present."""

    meta_file = qlib_dir / "snapshot_meta.json"
    if not meta_file.exists():
        return {}

    try:
        with open(meta_file) as f:
            return json.load(f)
    except json.JSONDecodeError as decode_error:
        logger.warning(
            "Failed to parse snapshot metadata at %s: %s", meta_file, decode_error
        )
    except OSError as os_error:
        logger.warning(
            "Could not read snapshot metadata at %s: %s", meta_file, os_error
        )

    return {}

"""Shared tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

# API unit tests deliberately do not require a complete Home Assistant install.
package = types.ModuleType("custom_components.rainforest_eagle_local")
package.__path__ = [str(ROOT / "custom_components" / "rainforest_eagle_local")]
sys.modules["custom_components.rainforest_eagle_local"] = package

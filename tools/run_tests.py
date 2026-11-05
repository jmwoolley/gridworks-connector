"""Import HA before pytest plugins so its HTTPX/Probatio aliases are installed."""
import homeassistant  # noqa: F401
import pytest

raise SystemExit(pytest.main())

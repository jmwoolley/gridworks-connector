"""Admin commissioning page, served locally by Home Assistant."""

import asyncio
from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN, VERSION


async def async_register_commissioning_panel(hass):
    state = hass.data.setdefault(DOMAIN + "_panel", {"lock": asyncio.Lock()})
    async with state["lock"]:
        if state.get("registered"):
            return
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/gridworks_connector_assets", str(Path(__file__).parent / "frontend"), False
                )
            ]
        )
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path="gridworks-connector",
            webcomponent_name="gridworks-commissioning",
            sidebar_title="GridWorks Connector",
            sidebar_icon="mdi:transmission-tower",
            require_admin=True,
            module_url=f"/gridworks_connector_assets/commissioning.js?v={VERSION}",
            config_panel_domain=DOMAIN,
            embed_iframe=False,
        )
        state["registered"] = True

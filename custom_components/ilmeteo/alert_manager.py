"""Alert evaluation, dedup/persistence, and Home Assistant notification dispatch."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .alerts import (
    AlertProvider,
    DpcSensorAlertProvider,
    DpcVigilanceProvider,
    HeuristicAlertProvider,
    WeatherAlert,
)
from .const import DEFAULT_INFO_URL, DOMAIN, EVENT_WEATHER_ALERT, ILMETEO_LOGO_URL
from .coordinator import IlMeteoCoordinator

_LOGGER = logging.getLogger(__name__)

_STORAGE_VERSION = 1


class IlMeteoAlertManager:
    """Watches a coordinator's data, detects alerts, notifies on change.

    Dedup is signature-based (alert_id + severity): a persistent_notification
    and an EVENT_WEATHER_ALERT event are only emitted when an alert is new or
    its severity changed, not on every coordinator refresh. Active alert IDs
    are persisted across restarts so a HA reboot doesn't re-fire notifications
    for alerts that were already notified.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: IlMeteoCoordinator,
        entry_id: str,
        citta: str,
        place_name: str,
        dpc_entity_id: str | None = None,
        dpc_vigilance_entity_id: str | None = None,
        notify_targets: list[str] | None = None,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.entry_id = entry_id
        self.citta = citta
        self.place_name = place_name
        self.notify_targets = notify_targets or []
        # Add future providers here (official iLMeteo feed, if/when offered).
        self.providers: list[AlertProvider] = [HeuristicAlertProvider()]
        if dpc_entity_id:
            self.providers.append(DpcSensorAlertProvider(hass, dpc_entity_id))
        if dpc_vigilance_entity_id:
            self.providers.append(DpcVigilanceProvider(hass, dpc_vigilance_entity_id))

        self._store: Store[dict[str, str]] = Store(
            hass, _STORAGE_VERSION, f"{DOMAIN}_{entry_id}_alerts"
        )
        self._active: dict[str, str] = {}  # alert_id -> signature
        self._unsub: callable | None = None

    async def async_start(self) -> None:
        """Load persisted state, subscribe to the coordinator, evaluate once."""
        self._active = await self._store.async_load() or {}
        self._unsub = self.coordinator.async_add_listener(self._handle_update)
        await self._evaluate()

    def async_stop(self) -> None:
        """Unsubscribe from the coordinator. Does not clear persisted state."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_update(self) -> None:
        self.hass.async_create_task(self._evaluate())

    async def _evaluate(self) -> None:
        data = self.coordinator.data or {}
        alerts: list[WeatherAlert] = []
        for provider in self.providers:
            try:
                alerts += await provider.async_get_alerts(
                    data, self.citta, self.place_name
                )
            except Exception:  # noqa: BLE001 - one bad provider must not break others
                _LOGGER.exception(
                    "Alert provider %s failed for %s", provider.name, self.place_name
                )

        current = {alert.alert_id: alert for alert in alerts}
        link = self._link_for(data)

        for alert_id, alert in current.items():
            if self._active.get(alert_id) != alert.signature:
                await self._notify(alert, link)
                self._active[alert_id] = alert.signature

        for alert_id in list(self._active):
            if alert_id not in current:
                await self._dismiss(alert_id)
                del self._active[alert_id]

        await self._store.async_save(self._active)

    @staticmethod
    def _link_for(data: dict[str, Any]) -> str:
        """Prefer the comune-specific iLMeteo URL captured from the tri1 box."""
        days = data.get("days") or []
        if days and days[0].get("url"):
            return days[0]["url"]
        return DEFAULT_INFO_URL

    async def _notify(self, alert: WeatherAlert, link: str) -> None:
        notification_id = f"{DOMAIN}_{self.entry_id}_{alert.alert_id}"
        title = f"⚠️ {self.place_name}: {alert.title}"

        # persistent_notification renders HTML/Markdown in the HA frontend.
        # Table layout keeps the logo small (72px) with text alongside.
        panel_message = (
            f"<table><tr>"
            f"<td><img src='{ILMETEO_LOGO_URL}' width='72'></td>"
            f"<td>&nbsp;&nbsp;</td>"
            f"<td><b>{alert.title}</b><br>{alert.message}<br><br>"
            f"🔗 <a href='{link}'>Dettagli e previsioni complete su iLMeteo.it</a></td>"
            f"</tr></table>"
        )
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {"notification_id": notification_id, "title": title, "message": panel_message},
            blocking=False,
        )

        # Fire the event unconditionally — automations can listen regardless
        # of whether push targets are configured.
        self.hass.bus.async_fire(
            EVENT_WEATHER_ALERT,
            {
                "entry_id": self.entry_id,
                "place_name": self.place_name,
                "alert_id": alert.alert_id,
                "severity": alert.severity,
                "kind": alert.kind,
                "title": alert.title,
                "message": alert.message,
                "source": alert.source,
                "link": link,
                "cleared": False,
            },
        )

        # Native mobile push via the legacy notify.mobile_app_* service — the
        # only channel that supports companion-app data (image, URI action button).
        # New-style notify entities (HA 2026.5+) don't support these fields yet
        # — see HA discussion #3684. The selector in config_flow.py restricts
        # targets to mobile_app_* only.
        for target in self.notify_targets:
            self.hass.async_create_task(
                self._push_with_retry(target, title, alert.message, link)
            )

    async def _push_with_retry(
        self, target: str, title: str, message: str, link: str, attempt: int = 0
    ) -> None:
        """Push to a notify.mobile_app_* target, retrying if not yet registered.

        The companion app service registers a few seconds after HA setup —
        retrying up to 5 times (10s apart) covers the typical boot window.
        """
        domain, service = target.split(".", 1)
        if not self.hass.services.has_service(domain, service):
            if attempt < 5:
                delay = 10 * (attempt + 1)
                _LOGGER.debug(
                    "Notify target %s not yet available, retrying in %ds (attempt %d/5)",
                    target, delay, attempt + 1,
                )
                async def _retry(_attempt=attempt):
                    await self._push_with_retry(target, title, message, link, _attempt + 1)
                self.hass.loop.call_later(
                    delay, lambda: self.hass.async_create_task(_retry())
                )
            else:
                _LOGGER.warning(
                    "Notify target %s not available after 5 attempts, giving up", target
                )
            return
        try:
            await self.hass.services.async_call(
                domain,
                service,
                {
                    "title": title,
                    "message": message,
                    "data": {
                        "image": ILMETEO_LOGO_URL,
                        "actions": [
                            {"action": "URI", "title": "Apri iLMeteo.it", "uri": link}
                        ],
                    },
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Push to %s failed", target)

    async def _dismiss(self, alert_id: str) -> None:
        notification_id = f"{DOMAIN}_{self.entry_id}_{alert_id}"
        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": notification_id},
            blocking=False,
        )
        self.hass.bus.async_fire(
            EVENT_WEATHER_ALERT,
            {
                "entry_id": self.entry_id,
                "place_name": self.place_name,
                "alert_id": alert_id,
                "cleared": True,
            },
        )
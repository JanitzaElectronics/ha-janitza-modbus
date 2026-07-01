"""Sensors for the Janitza Modbus integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JanitzaConfigEntry
from .const import CONF_UNIT_ID, DOMAIN
from .coordinator import JanitzaCoordinator
from .registers import JanitzaRegister


async def async_setup_entry(
    hass,
    entry: JanitzaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Janitza Modbus sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        JanitzaSensor(coordinator, entry, register) for register in coordinator.registers
    )


class JanitzaSensor(CoordinatorEntity[JanitzaCoordinator], SensorEntity):
    """Representation of a Janitza Modbus sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JanitzaCoordinator,
        entry: JanitzaConfigEntry,
        register: JanitzaRegister,
    ) -> None:
        """Initialize the Janitza sensor."""
        super().__init__(coordinator)
        self._register = register
        self.entity_description = SensorEntityDescription(
            key=register.key,
            translation_key=register.translation_key,
            name=register.name,
            native_unit_of_measurement=register.native_unit_of_measurement,
            device_class=register.device_class,
            state_class=register.state_class,
            suggested_display_precision=register.suggested_display_precision,
            entity_registry_enabled_default=register.entity_registry_enabled_default,
        )
        self._attr_unique_id = (
            f"{entry.entry_id}_{entry.data[CONF_UNIT_ID]}_{register.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Janitza",
            name=entry.title,
            configuration_url=f"http://{entry.data['host']}",
        )

    @property
    def native_value(self) -> float | None:
        """Return the latest native value."""
        return self.coordinator.data.get(self._register.key)

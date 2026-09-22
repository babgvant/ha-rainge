"""Local XML API client for Rainforest Automation EAGLE gateways."""

from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from base64 import b64encode
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from aiohttp import ClientConnectionError, ClientResponseError, ClientSession

_MAX_RESPONSE_SIZE = 1024 * 1024
_UNSAFE_XML = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_QUANTITY = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([^\s]+)?\s*$")


class EagleError(Exception):
    """Base EAGLE API error."""


class EagleAuthenticationError(EagleError):
    """Credentials were rejected."""


class EagleConnectionError(EagleError):
    """The gateway could not be reached."""


class EagleTimeoutError(EagleConnectionError):
    """The gateway did not answer in time."""


class EagleResponseError(EagleError):
    """The gateway returned an invalid or unsupported response."""


@dataclass(frozen=True, slots=True)
class Meter:
    """Metadata for an attached electric meter."""

    name: str
    hardware_address: str
    manufacturer: str
    model_id: str
    protocol: str
    connection_status: str
    last_contact: str
    network_address: str

    def as_dict(self) -> dict[str, str]:
        """Return serializable metadata."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MeterReading:
    """A value and its API-provided unit."""

    value: Decimal | str
    unit: str | None = None


def _child_text(element: ET.Element, name: str, default: str = "") -> str:
    child = element.find(name)
    return default if child is None or child.text is None else child.text.strip()


def _parse_xml(payload: bytes) -> ET.Element:
    if len(payload) > _MAX_RESPONSE_SIZE:
        raise EagleResponseError("Response is too large")
    if _UNSAFE_XML.search(payload):
        raise EagleResponseError("Unsafe XML declaration")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as err:
        raise EagleResponseError("Invalid XML response") from err


def _parse_reading(value: str) -> MeterReading:
    match = _QUANTITY.match(value)
    if not match:
        return MeterReading(value=value)
    try:
        number = Decimal(match.group(1))
    except InvalidOperation:
        return MeterReading(value=value)
    return MeterReading(value=number, unit=match.group(2))


class EagleLocalApi:
    """Talk to an EAGLE exclusively through its LAN API."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        cloud_id: str,
        install_code: str,
        *,
        protocol: str = "https",
        verify_ssl: bool = False,
        timeout: float = 15,
    ) -> None:
        self._session = session
        self._host = host.strip().rstrip("/")
        token = b64encode(f"{cloud_id}:{install_code}".encode("latin1")).decode("ascii")
        self._authorization = f"Basic {token}"
        self._protocol = protocol
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self.last_response_root: str | None = None
        self.last_response_bytes: int | None = None

    @property
    def endpoint(self) -> str:
        """Return the local endpoint without credentials."""
        return f"{self._protocol}://{self._host}/cgi-bin/post_manager"

    async def async_command(self, command_name: str, **params: Any) -> ET.Element:
        """Execute a generic XML command."""
        command = ET.Element("Command")
        ET.SubElement(command, "Name").text = command_name
        self._append_params(command, params)
        body = ET.tostring(command, encoding="utf-8", xml_declaration=False)
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.post(
                    self.endpoint,
                    data=body,
                    headers={
                        "Authorization": self._authorization,
                        "Content-Type": "text/xml",
                    },
                    ssl=self._verify_ssl,
                ) as response:
                    if response.status == 401:
                        raise EagleAuthenticationError("Authentication failed")
                    if response.status < 200 or response.status >= 300:
                        raise EagleConnectionError(
                            f"Gateway returned HTTP {response.status}"
                        )
                    payload = await response.read()
        except TimeoutError as err:
            raise EagleTimeoutError("Gateway request timed out") from err
        except (ClientConnectionError, ClientResponseError, OSError) as err:
            raise EagleConnectionError("Unable to connect to gateway") from err

        root = _parse_xml(payload)
        self.last_response_root = root.tag
        self.last_response_bytes = len(payload)
        return root

    def _append_params(self, parent: ET.Element, params: Mapping[str, Any]) -> None:
        for key, value in params.items():
            node = ET.SubElement(parent, key)
            if isinstance(value, Mapping):
                self._append_params(node, value)
            elif isinstance(value, list):
                parent.remove(node)
                for item in value:
                    repeated = ET.SubElement(parent, key)
                    if isinstance(item, Mapping):
                        self._append_params(repeated, item)
                    else:
                        repeated.text = str(item)
            else:
                node.text = str(value)

    async def async_get_devices(self) -> list[Meter]:
        """Return attached electric meters."""
        root = await self.async_command("device_list")
        if root.tag != "DeviceList":
            raise EagleResponseError(f"Expected DeviceList, got {root.tag}")
        meters: list[Meter] = []
        for device in root.findall("Device"):
            if _child_text(device, "ModelId") != "electric_meter":
                continue
            address = _child_text(device, "HardwareAddress")
            if not address:
                raise EagleResponseError("Electric meter has no hardware address")
            meters.append(
                Meter(
                    name=_child_text(device, "Name", "Power Meter"),
                    hardware_address=address,
                    manufacturer=_child_text(device, "Manufacturer"),
                    model_id=_child_text(device, "ModelId"),
                    protocol=_child_text(device, "Protocol"),
                    connection_status=_child_text(device, "ConnectionStatus"),
                    last_contact=_child_text(device, "LastContact"),
                    network_address=_child_text(device, "NetworkAddress"),
                )
            )
        if not meters:
            raise EagleResponseError("No supported electric meter found")
        return meters

    async def async_get_meter_data(
        self, meter: Meter
    ) -> tuple[Meter, dict[str, MeterReading]]:
        """Query all locally buffered variables for one meter."""
        root = await self.async_command(
            "device_query",
            DeviceDetails={"HardwareAddress": meter.hardware_address},
            Components={"All": "Y"},
        )
        if root.tag != "Device":
            raise EagleResponseError(f"Expected Device, got {root.tag}")
        details = root.find("DeviceDetails")
        if details is None:
            raise EagleResponseError("Device response has no metadata")
        updated = Meter(
            name=_child_text(details, "Name", meter.name),
            hardware_address=_child_text(
                details, "HardwareAddress", meter.hardware_address
            ),
            manufacturer=_child_text(details, "Manufacturer", meter.manufacturer),
            model_id=_child_text(details, "ModelId", meter.model_id),
            protocol=_child_text(details, "Protocol", meter.protocol),
            connection_status=_child_text(
                details, "ConnectionStatus", meter.connection_status
            ),
            last_contact=_child_text(details, "LastContact", meter.last_contact),
            network_address=_child_text(
                details, "NetworkAddress", meter.network_address
            ),
        )
        readings: dict[str, MeterReading] = {}
        for variable in root.findall("./Components/Component/Variables/Variable"):
            name = _child_text(variable, "Name")
            value = _child_text(variable, "Value")
            if name and value:
                readings[name] = _parse_reading(value)
        return updated, readings

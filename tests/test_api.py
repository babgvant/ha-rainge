"""Tests for the local EAGLE API client."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from custom_components.rainforest_eagle_local.api import (
    EagleAuthenticationError,
    EagleLocalApi,
    EagleResponseError,
    EagleTimeoutError,
)

DEVICE_LIST = b"""<DeviceList><Device><Name>Power Meter</Name>
<HardwareAddress>0x001350050047376f</HardwareAddress><Manufacturer>Generic</Manufacturer>
<ModelId>electric_meter</ModelId><Protocol>Zigbee</Protocol><LastContact>0x6ab1bb0d</LastContact>
<ConnectionStatus>Connected</ConnectionStatus><NetworkAddress>0xffff</NetworkAddress>
</Device></DeviceList>"""

QUERY = b"""<Device><DeviceDetails><Name>Power Meter</Name>
<HardwareAddress>0x001350050047376f</HardwareAddress><Manufacturer>Generic</Manufacturer>
<ModelId>electric_meter</ModelId><Protocol>Zigbee</Protocol><LastContact>0x6ab1bb0e</LastContact>
<ConnectionStatus>Connected</ConnectionStatus><NetworkAddress>0xffff</NetworkAddress>
</DeviceDetails><Components><Component><Name>Main</Name><Variables>
<Variable><Name>zigbee:InstantaneousDemand</Name><Value>-1.250 kW</Value></Variable>
<Variable><Name>zigbee:CurrentSummationDelivered</Name>
<Value>1234.500 kWh</Value></Variable>
<Variable><Name>zigbee:CurrentSummationReceived</Name>
<Value>456.750 kWh</Value></Variable>
</Variables></Component></Components></Device>"""


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def read(self) -> bytes:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_https_device_list_and_no_verify() -> None:
    session = FakeSession([FakeResponse(DEVICE_LIST)])
    api = EagleLocalApi(session, "192.0.2.1", "cloud", "secret")  # type: ignore[arg-type]
    meters = await api.async_get_devices()
    assert meters[0].hardware_address == "0x001350050047376f"
    assert session.calls[0]["url"] == "https://192.0.2.1/cgi-bin/post_manager"
    assert session.calls[0]["ssl"] is False
    assert b"device_list" in session.calls[0]["data"]


@pytest.mark.asyncio
async def test_authentication_failure() -> None:
    api = EagleLocalApi(FakeSession([FakeResponse(b"", 401)]), "host", "id", "code")  # type: ignore[arg-type]
    with pytest.raises(EagleAuthenticationError):
        await api.async_get_devices()


class TimeoutSession(FakeSession):
    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        raise TimeoutError


@pytest.mark.asyncio
async def test_timeout() -> None:
    api = EagleLocalApi(TimeoutSession([]), "host", "id", "code")  # type: ignore[arg-type]
    with pytest.raises(EagleTimeoutError):
        await api.async_get_devices()


@pytest.mark.asyncio
async def test_device_query_keeps_import_export_separate() -> None:
    session = FakeSession([FakeResponse(DEVICE_LIST), FakeResponse(QUERY)])
    api = EagleLocalApi(session, "host", "id", "code")  # type: ignore[arg-type]
    meter = (await api.async_get_devices())[0]
    updated, readings = await api.async_get_meter_data(meter)
    assert updated.last_contact == "0x6ab1bb0e"
    assert readings["zigbee:InstantaneousDemand"].value == Decimal("-1.250")
    assert readings["zigbee:CurrentSummationDelivered"].value == Decimal("1234.500")
    assert readings["zigbee:CurrentSummationReceived"].value == Decimal("456.750")
    assert readings["zigbee:CurrentSummationDelivered"].unit == "kWh"


@pytest.mark.asyncio
async def test_rejects_unsafe_xml() -> None:
    payload = b'<!DOCTYPE x [<!ENTITY bad SYSTEM "file:///etc/passwd">]><DeviceList/>'
    api = EagleLocalApi(FakeSession([FakeResponse(payload)]), "host", "id", "code")  # type: ignore[arg-type]
    with pytest.raises(EagleResponseError, match="Unsafe XML"):
        await api.async_get_devices()

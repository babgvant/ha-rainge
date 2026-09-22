# Rainforest EAGLE Local

A local-only Home Assistant custom integration for Rainforest Automation EAGLE gateways, with EAGLE 3 HTTPS support. It talks directly to `/cgi-bin/post_manager` on your LAN and does not use Rainforest, Rainge, or any other cloud service.

## Installation

### HACS

1. In HACS, open **Integrations**, choose the menu, then **Custom repositories**.
2. Add this repository URL as an **Integration** repository.
3. Install **Rainforest EAGLE Local** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select **Rainforest EAGLE Local**.

### Manual fallback

Copy `custom_components/rainforest_eagle_local` into the `custom_components` directory under your Home Assistant configuration directory, restart Home Assistant, and add the integration from **Settings → Devices & services**.

## Configuration

You need the EAGLE's host/IP, Cloud ID (username), and Install Code (password). Defaults are tailored to current EAGLE 3 firmware:

- Protocol: HTTPS
- Verify SSL certificate: off (the gateway commonly has a self-signed/local certificate)
- Polling interval: 10 seconds (minimum 5 seconds)

Protocol, verification, and interval can be changed later with **Configure**. Credentials remain in the Home Assistant config entry and are never logged. The integration supports Home Assistant reauthentication when the EAGLE rejects saved credentials.

## Entities

The integration issues one `device_query` with `<All>Y</All>` per polling cycle. It exposes:

- instantaneous demand/current power;
- separate delivered/imported and received/exported cumulative energy;
- connection status and last contact;
- voltage, current, frequency, price, and rate label when the meter reports those variables.

Power and energy values use the units returned by the EAGLE API. The documented meter response returns formatted values such as `21.499 kW`; the integration does not reapply Zigbee multiplier/divisor values. Import and export are deliberately never combined into an ambiguous net-energy total.

The stock Home Assistant integration's principal EAGLE-200 behavior is preserved: meter discovery, current demand, delivered energy, received energy, local polling, stable hardware-address IDs, and device metadata. This custom integration adds explicit HTTPS/certificate options, more precise setup errors, reauthentication, diagnostics, and additional optional variables.

## Troubleshooting

- A timeout using HTTP with an EAGLE 3 usually means the protocol should be HTTPS.
- Leave certificate verification disabled for the EAGLE's self-signed certificate. Enable it only if your device presents a certificate trusted by Home Assistant.
- `Invalid authentication` means either the Cloud ID or Install Code was rejected.
- `Invalid response` means the endpoint answered but did not return the expected EAGLE XML or no `electric_meter` was listed.
- Confirm that Home Assistant can route to the EAGLE IP and that TCP port 443 (HTTPS) or 80 (HTTP) is reachable.

Diagnostics redact the Install Code, partially mask the Cloud ID, and contain no authorization header.

## API scope and known limitations

Implemented commands are `device_list` and `device_query`; the transport exposes a generic `async_command()` for future commands. `device_details`, device control, smart plugs, thermostats, historical/uploader data, and cloud APIs are not currently exposed. The first attached `electric_meter` is used. Optional sensors remain unavailable when the meter does not publish their corresponding variable.

The Rainforest local API documentation is available from the [Rainforest developer resources](https://www.rainforestautomation.com/support/developer/).


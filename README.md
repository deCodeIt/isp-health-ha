# ISP Health Monitor for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Monitor multiple ISP FTTH/ONT devices on your LAN and automatically determine which ISP has a working internet connection.

## Features

- **Device reachability** — ICMP ping to each ISP device to check if it's powered on
- **Per-ISP internet check** — Tests internet connectivity through each specific ISP gateway using temporary route injection
- **Fallback DNS targets** — Tries Cloudflare (1.1.1.1), Google (8.8.8.8), Quad9 (9.9.9.9), and OpenDNS (208.67.222.222) before declaring internet down
- **Priority-based ISP selection** — Automatically selects the highest-priority healthy ISP
- **Configurable polling** — Adjust poll interval and ping timeout via the UI
- **Dynamic ISP management** — Add, remove, or reorder ISPs without restarting HA

## Installation

### HACS (Custom Repository)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **⋮** (top right) → **Custom repositories**
3. Add this repository URL with category **Integration**
4. Click **Download**
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/isp_health/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ISP Health Monitor**
3. Enter your first ISP's name, IP address, and priority (1 = highest)
4. Optionally add more ISPs
5. Done — entities will appear immediately

## Entities

Each ISP device gets its own HA device with these entities:

| Entity | Type | Description |
|--------|------|-------------|
| `Device Online` | Binary sensor | ISP device responds to ICMP ping |
| `Internet Online` | Binary sensor | Internet reachable through this ISP's gateway |
| `Latency` | Sensor (ms) | Ping round-trip time to the device |

Global entities:

| Entity | Type | Description |
|--------|------|-------------|
| `ISP Selected` | Sensor | Name of the highest-priority healthy ISP (IP in attributes) |

## Options

Go to the integration's **Configure** page to adjust:

| Option | Default | Range | Description |
|--------|---------|-------|-------------|
| Poll interval | 30s | 5–300s | How often to check ISP health |
| Ping timeout | 3s | 1–10s | Timeout for each ping probe |

You can also add or remove ISPs from the options flow.

## How It Works

### Device Check
Simple ICMP ping to the ISP device's IP address.

### Internet Check (Per-ISP)
For each ISP, the integration temporarily injects a host route to send test traffic through that specific gateway:

```
ip route add <target>/32 via <isp_gateway_ip>
ping -c 1 -W <timeout> <target>
ip route del <target>/32 via <isp_gateway_ip>
```

It tries up to 4 DNS targets (Cloudflare, Google, Quad9, OpenDNS) before marking internet as down. Each ISP is tested sequentially to avoid route conflicts.

### ISP Selection
ISPs are sorted by priority (1 = highest). The first ISP where both device and internet checks pass becomes the selected ISP.

## Requirements

- Home Assistant OS or Supervised (the HA container needs `NET_ADMIN` capability for route injection, which is standard on HA OS)
- ISP devices must be on the same LAN subnet as Home Assistant
- ISP devices must be configured as gateways (traffic can be routed through them)

## Network Setup Example

```
Internet ─── ISP 1 (ONT) ─── 192.168.1.251 ───┐
                                                 ├─── LAN (192.168.1.0/24) ─── HA (192.168.1.x)
Internet ─── ISP 2 (ONT) ─── 192.168.1.252 ───┘
```

## License

MIT

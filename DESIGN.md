# ISP Health Monitor — Home Assistant HACS Integration

## Goal
Monitor multiple ISP FTTH devices on the LAN and expose their health as HA entities.
Users configure ISPs (name, IP, priority), and the integration shows which ISPs are
healthy and which one is currently the best choice.

## Architecture

```
┌─────────────────────────────────────────────┐
│            Home Assistant                    │
│                                              │
│  Config Flow (UI)                            │
│  ├─ Add ISP: name, IP, priority, poll interval│
│  ├─ Edit / Remove ISPs                       │
│  └─ Options: global poll interval override   │
│                                              │
│  Coordinator (DataUpdateCoordinator)         │
│  ├─ Runs every <poll_interval> seconds       │
│  └─ For each ISP:                            │
│      ├─ ICMP ping → device_reachable (bool)  │
│      ├─ Internet probe → internet_ok (bool)  │
│      └─ Latency (ms)                         │
│                                              │
│  Entities exposed:                           │
│  ├─ binary_sensor.<isp>_device_online        │
│  ├─ binary_sensor.<isp>_internet_online      │
│  ├─ sensor.<isp>_latency                     │
│  ├─ sensor.isp_selected  (highest-priority   │
│  │      healthy ISP name + IP)               │
│  └─ sensor.isp_health_summary (all statuses) │
└─────────────────────────────────────────────┘
```

## Health Check Methods

### 1. Device Reachable (MVP — simple, no privileges needed)
- ICMP ping to device IP (e.g. 192.168.1.251)
- Uses `asyncio.subprocess` → `ping -c 1 -W <timeout> <ip>`
- Result: up/down + round-trip latency

### 2. Internet Through ISP (MVP — needs investigation)

**Problem:** HA integration runs inside the HA Python process. To test if
internet works *through a specific ISP*, we need to route a probe packet
via that ISP's gateway. On Linux this requires either:
- (a) Modifying the routing table (`ip route add ... via <gw>`) — needs
      NET_ADMIN / root. HA integrations typically don't have this.
- (b) Using SO_BINDTODEVICE or policy routing — same privilege issue.
- (c) Scraping the device admin panel for WAN status — device-specific,
      captcha risk.

**MVP approach chosen:** Ping an external target (1.1.1.1, 8.8.8.8) from
HA without source routing. This tests that *some* internet path works but
does NOT tell us *which* ISP is carrying the traffic. Combined with device
ping, we get:
- Device ping fails → that ISP device is down
- Device ping succeeds + external ping fails → either that ISP's internet
  is down OR traffic is routed through the other ISP
- Device ping succeeds + external ping succeeds → at least one ISP works

For MVP, this is the honest limit. The "internet_online" sensor will
reflect whether the external target is reachable from HA *at all*, not
per-ISP. We surface this clearly in the UI.

**Post-MVP options to get per-ISP internet status:**
1. Run as an HA add-on (Docker container with NET_ADMIN) and do policy routing
2. SNMP polling on devices that support it (check: `snmpwalk -v2c -c public <ip>`)
3. Admin panel scraping with captcha solving (last resort)
4. DNS-based probe: resolve a known domain using the ISP's DNS server
   (if known) — partial signal that the ISP uplink works

### 3. SNMP (Post-MVP, if devices support it)

To check SNMP support on a device, run from a machine on the same LAN:
```bash
# Install snmp tools if needed
sudo apt install snmp

# Try SNMPv2 with default "public" community string
snmpwalk -v2c -c public 192.168.1.251 1.3.6.1.2.1.1.1.0

# If that fails, try SNMPv1
snmpget -v1 -c public 192.168.1.251 1.3.6.1.2.1.1.1.0
```

If either returns a system description, the device supports SNMP and we
can poll interface counters, WAN link status, signal strength, etc.

## Data Model

```python
@dataclass
class ISPConfig:
    name: str           # "Sikka ISP"
    ip: str             # "192.168.1.251"
    priority: int       # 1 = highest priority
    poll_interval: int  # seconds, default 30

@dataclass
class ISPStatus:
    device_reachable: bool
    latency_ms: float | None
    internet_reachable: bool   # global check, not per-ISP in MVP
    last_checked: datetime
```

## Priority / Selected ISP Logic

1. Sort configured ISPs by priority (ascending, 1 = highest)
2. Walk the list: first ISP where `device_reachable is True` becomes selected
3. Expose `sensor.isp_selected` → name and IP of selected ISP
4. If none reachable → sensor shows "No healthy ISP"

## File Structure

```
custom_components/isp_health/
├── __init__.py          # Setup, coordinator
├── manifest.json        # HACS metadata
├── config_flow.py       # UI config + options flow
├── coordinator.py       # DataUpdateCoordinator, ping logic
├── binary_sensor.py     # Device online, internet online
├── sensor.py            # Latency, selected ISP, summary
├── const.py             # Domain, defaults, config keys
├── strings.json         # UI strings
└── translations/
    └── en.json          # English translations
```

## MVP Scope

| Feature | In MVP | Verify how |
|---------|--------|------------|
| Add ISP via UI (name, IP, priority) | ✅ | Config flow works |
| Remove / edit ISP | ✅ | Options flow works |
| ICMP ping per device | ✅ | Binary sensor toggles |
| Latency sensor | ✅ | Shows ms value |
| Global internet check | ✅ | Ping 1.1.1.1 from HA |
| Selected ISP sensor | ✅ | Shows highest-priority healthy ISP |
| Configurable poll interval | ✅ | Options flow, coordinator respects it |
| Per-ISP internet check | ❌ | Needs add-on or SNMP |
| SNMP counters | ❌ | Needs device support verification |
| Auto-discover ISPs | ❌ | Future |
| Admin panel scraping | ❌ | Future, needs captcha work |

## MVP Success Criteria

1. Install integration via HACS → appears in HA integrations list
2. Add ISP "Sikka" at 192.168.1.251 priority 1 → config flow completes
3. Add ISP "Airtel" at 192.168.1.252 priority 2 → second ISP added
4. Dashboard shows: two device_online binary sensors, two latency sensors
5. Unplug one ISP device → binary sensor goes off within one poll cycle
6. sensor.isp_selected switches to the other ISP
7. Change poll interval in options → coordinator adjusts

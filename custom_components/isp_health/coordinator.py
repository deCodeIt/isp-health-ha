import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_EXTERNAL_TARGETS, DEFAULT_PING_TIMEOUT

_LOGGER = logging.getLogger(__name__)


@dataclass
class ISPStatus:
    device_reachable: bool = False
    internet_reachable: bool = False
    latency_ms: float | None = None
    last_checked: float = 0


@dataclass
class ISPHealthData:
    statuses: dict[str, ISPStatus] = field(default_factory=dict)
    selected_isp: str | None = None
    selected_ip: str | None = None


async def _run_cmd(cmd: str, timeout: int = 5) -> tuple[int, str]:
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return proc.returncode, stdout.decode()
    except (asyncio.TimeoutError, OSError) as err:
        _LOGGER.debug("Command failed: %s — %s", cmd, err)
        return 1, ""


async def _ping(ip: str, timeout: int) -> tuple[bool, float | None]:
    code, output = await _run_cmd(
        f"ping -c 1 -W {timeout} {ip}", timeout=timeout + 2
    )
    if code != 0:
        return False, None
    for line in output.splitlines():
        if "time=" in line:
            try:
                ms = float(line.split("time=")[1].split()[0])
                return True, ms
            except (IndexError, ValueError):
                pass
    return True, None


async def _check_internet_via_gateway(
    gateway_ip: str,
    targets: list[str],
    timeout: int,
) -> bool:
    for target in targets:
        await _run_cmd(f"ip route add {target}/32 via {gateway_ip}", timeout=3)
        try:
            reachable, _ = await _ping(target, timeout)
            if reachable:
                return True
        finally:
            await _run_cmd(f"ip route del {target}/32 via {gateway_ip}", timeout=3)
    return False


class ISPHealthCoordinator(DataUpdateCoordinator[ISPHealthData]):

    def __init__(
        self,
        hass: HomeAssistant,
        isps: list[dict],
        poll_interval: int,
        ping_timeout: int = DEFAULT_PING_TIMEOUT,
        external_targets: list[str] | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="isp_health",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.isps = sorted(isps, key=lambda x: x["priority"])
        self.ping_timeout = ping_timeout
        self.external_targets = external_targets or DEFAULT_EXTERNAL_TARGETS
        self._route_lock = asyncio.Lock()

    async def _async_update_data(self) -> ISPHealthData:
        data = ISPHealthData()

        for isp in self.isps:
            name = isp["isp_name"]
            ip = isp["isp_ip"]

            try:
                reachable, latency = await _ping(ip, self.ping_timeout)
            except Exception:
                _LOGGER.exception("Ping failed for %s (%s)", name, ip)
                reachable, latency = False, None

            internet_ok = False
            if reachable:
                try:
                    async with self._route_lock:
                        internet_ok = await _check_internet_via_gateway(
                            ip, self.external_targets, self.ping_timeout
                        )
                except Exception:
                    _LOGGER.exception(
                        "Internet check failed for %s (%s)", name, ip
                    )

            status = ISPStatus(
                device_reachable=reachable,
                internet_reachable=internet_ok,
                latency_ms=latency,
                last_checked=time.time(),
            )
            data.statuses[name] = status
            _LOGGER.debug(
                "ISP %s: reachable=%s, internet=%s, latency=%s",
                name, reachable, internet_ok, latency,
            )

            if data.selected_isp is None and reachable and internet_ok and isp.get("enabled", True):
                data.selected_isp = name
                data.selected_ip = ip

        _LOGGER.debug("Selected ISP: %s (%s)", data.selected_isp, data.selected_ip)
        return data

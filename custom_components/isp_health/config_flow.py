import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_EXTERNAL_TARGETS,
    CONF_ISP_ENABLED,
    CONF_ISP_IP,
    CONF_ISP_NAME,
    CONF_ISP_PRIORITY,
    CONF_ISPS,
    CONF_PING_TIMEOUT,
    CONF_POLL_INTERVAL,
    DEFAULT_EXTERNAL_TARGETS,
    DEFAULT_PING_TIMEOUT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)


def _check_duplicate_priority(
    isps: list[dict], new_priority: int, exclude_idx: int | None = None,
) -> str | None:
    for i, isp in enumerate(isps):
        if i == exclude_idx:
            continue
        if isp[CONF_ISP_PRIORITY] == new_priority:
            return f"Priority {new_priority} is already used by {isp[CONF_ISP_NAME]}"
    return None


class ISPHealthConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._isps: list[dict] = []

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            err = _check_duplicate_priority(
                self._isps, user_input[CONF_ISP_PRIORITY]
            )
            if err:
                errors["base"] = "duplicate_priority"
            else:
                self._isps.append(
                    {
                        CONF_ISP_NAME: user_input[CONF_ISP_NAME],
                        CONF_ISP_IP: user_input[CONF_ISP_IP],
                        CONF_ISP_PRIORITY: user_input[CONF_ISP_PRIORITY],
                        CONF_ISP_ENABLED: True,
                    }
                )
                return await self.async_step_add_more()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ISP_NAME): str,
                    vol.Required(CONF_ISP_IP): str,
                    vol.Required(CONF_ISP_PRIORITY, default=len(self._isps) + 1): int,
                }
            ),
            errors=errors,
        )

    async def async_step_add_more(self, user_input=None):
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_user()
            return self.async_create_entry(
                title="ISP Health Monitor",
                data={
                    CONF_ISPS: self._isps,
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                    CONF_PING_TIMEOUT: DEFAULT_PING_TIMEOUT,
                    CONF_EXTERNAL_TARGETS: DEFAULT_EXTERNAL_TARGETS,
                },
            )

        return self.async_show_form(
            step_id="add_more",
            data_schema=vol.Schema(
                {
                    vol.Required("add_another", default=False): bool,
                }
            ),
            description_placeholders={
                "count": str(len(self._isps)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ISPHealthOptionsFlow(config_entry)


class ISPHealthOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._isps: list[dict] = list(config_entry.data.get(CONF_ISPS, []))
        self._edit_idx: int | None = None

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            new_data = {
                **self._config_entry.data,
                CONF_POLL_INTERVAL: user_input[CONF_POLL_INTERVAL],
                CONF_PING_TIMEOUT: user_input[CONF_PING_TIMEOUT],
            }
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return await self.async_step_manage_isps()

        current = self._config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_POLL_INTERVAL,
                        default=current.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(int, vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_PING_TIMEOUT,
                        default=current.get(
                            CONF_PING_TIMEOUT, DEFAULT_PING_TIMEOUT
                        ),
                    ): vol.All(int, vol.Range(min=1, max=10)),
                }
            ),
        )

    async def async_step_manage_isps(self, user_input=None):
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_isp()
            if action == "done":
                new_data = {**self._config_entry.data, CONF_ISPS: self._isps}
                self.hass.config_entries.async_update_entry(
                    self._config_entry, data=new_data
                )
                return self.async_create_entry(title="", data={})
            if action.startswith("remove:"):
                idx = int(action.split(":")[1])
                if 0 <= idx < len(self._isps):
                    self._isps.pop(idx)
                return await self.async_step_manage_isps()
            if action.startswith("edit:"):
                self._edit_idx = int(action.split(":")[1])
                return await self.async_step_edit_isp()

        isp_actions = {}
        for i, isp in enumerate(self._isps):
            status = "enabled" if isp.get(CONF_ISP_ENABLED, True) else "disabled"
            label = f"{isp[CONF_ISP_NAME]} ({isp[CONF_ISP_IP]}) — priority {isp[CONF_ISP_PRIORITY]} [{status}]"
            isp_actions[f"edit:{i}"] = f"Edit {label}"
            isp_actions[f"remove:{i}"] = f"Remove {label}"
        actions = {"add": "Add new ISP", **isp_actions, "done": "Done"}

        return self.async_show_form(
            step_id="manage_isps",
            data_schema=vol.Schema(
                {vol.Required("action"): vol.In(actions)}
            ),
        )

    async def async_step_add_isp(self, user_input=None):
        errors = {}
        if user_input is not None:
            err = _check_duplicate_priority(
                self._isps, user_input[CONF_ISP_PRIORITY]
            )
            if err:
                errors["base"] = "duplicate_priority"
            else:
                self._isps.append(
                    {
                        CONF_ISP_NAME: user_input[CONF_ISP_NAME],
                        CONF_ISP_IP: user_input[CONF_ISP_IP],
                        CONF_ISP_PRIORITY: user_input[CONF_ISP_PRIORITY],
                        CONF_ISP_ENABLED: True,
                    }
                )
                return await self.async_step_manage_isps()

        return self.async_show_form(
            step_id="add_isp",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ISP_NAME): str,
                    vol.Required(CONF_ISP_IP): str,
                    vol.Required(CONF_ISP_PRIORITY, default=len(self._isps) + 1): int,
                }
            ),
            errors=errors,
        )

    async def async_step_edit_isp(self, user_input=None):
        idx = self._edit_idx
        isp = self._isps[idx]
        errors = {}

        if user_input is not None:
            err = _check_duplicate_priority(
                self._isps, user_input[CONF_ISP_PRIORITY], exclude_idx=idx
            )
            if err:
                errors["base"] = "duplicate_priority"
            else:
                self._isps[idx] = {
                    CONF_ISP_NAME: user_input[CONF_ISP_NAME],
                    CONF_ISP_IP: user_input[CONF_ISP_IP],
                    CONF_ISP_PRIORITY: user_input[CONF_ISP_PRIORITY],
                    CONF_ISP_ENABLED: isp.get(CONF_ISP_ENABLED, True),
                }
                return await self.async_step_manage_isps()

        return self.async_show_form(
            step_id="edit_isp",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ISP_NAME, default=isp[CONF_ISP_NAME]): str,
                    vol.Required(CONF_ISP_IP, default=isp[CONF_ISP_IP]): str,
                    vol.Required(CONF_ISP_PRIORITY, default=isp[CONF_ISP_PRIORITY]): int,
                }
            ),
            errors=errors,
        )

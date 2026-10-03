from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Mapping

import json5
from pydantic import TypeAdapter, ValidationError

from .config import (
    NodeDefinition,
    NodeDisqualification,
    NodeGroupDefinition,
    NodeLocationDefinition,
    Settings,
)
from .core.logging import get_logger

logger = get_logger(__name__)

CONFIG_FILE_ENV = "MONSTR_CONFIG_FILE"
CONFIG_JSON_ENV = "MONSTR_CONFIG_JSON"

_SECTION_FIELDS: dict[str, dict[str, str]] = {
    "api": {
        "host": "api_host",
        "port": "api_port",
        "reload": "api_reload",
        "log_level": "api_log_level",
        "cors_allow_origins": "cors_allow_origins",
    },
    "database": {
        "url": "database_url",
        "sql_echo": "sql_echo",
        "write_suspend_seconds": "db_write_suspend_seconds",
    },
    "nodeapi": {
        "poll_interval": "log_poll_interval",
        "batch_size": "log_batch_size",
        "unprocessed_dir": "unprocessed_log_dir",
        "poll_interval_seconds": "nodeapi_poll_interval_seconds",
        "estimated_payout_interval_seconds": "nodeapi_estimated_payout_interval_seconds",
        "held_history_interval_seconds": "nodeapi_held_history_interval_seconds",
        "satellite_details_interval_seconds": "nodeapi_satellite_details_interval_seconds",
        "paystub_interval_seconds": "nodeapi_paystub_interval_seconds",
    },
    "maintenance": {
        "cleanup_interval_seconds": "cleanup_interval_seconds",
        "grouping_interval_seconds": "grouping_interval_seconds",
    },
    "frontend": {
        "dist_dir": "frontend_dist_dir",
    },
}

_RETENTION_FIELDS = {
    "default_minutes": "retention_minutes",
    "transfers_minutes": "retention_transfers_minutes",
    "log_entries_minutes": "retention_log_entries_minutes",
    "transfer_grouped_minutes": "retention_transfer_grouped_minutes",
    "hashstore_compaction_minutes": "retention_hashstore_compaction_minutes",
}
_PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")
_MDI_ICON_RE = re.compile(r"^mdi:[a-z0-9]+(?:-[a-z0-9]+)*$")


class ConfigError(ValueError):
    """A JSONC configuration error with a path-qualified diagnostic."""


def load_settings(
    *,
    config_file: str | Path | None = None,
    config_json: str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Settings:
    """Load environment-backed settings and overlay JSONC and explicit CLI values."""
    base = Settings()
    source_kind, source_value = _select_config_source(
        config_file,
        config_json,
        base.config_file,
        base.config_json,
    )
    document = _load_document(source_kind, source_value) if source_kind else {}
    settings_updates, nodegroups_present = _settings_updates(document)
    settings_values = base.model_dump()
    settings_values.update(settings_updates)
    settings_values.update(overrides or {})

    try:
        settings = Settings(
            _env_file=None,
            config_file=None,
            config_json=None,
            **settings_values,
        )
    except ValidationError as exc:
        field = exc.errors(include_input=False)[0].get("loc", ("",))[0]
        config_path = _setting_path(str(field))
        raise ConfigError(f"Invalid value at '{config_path}'") from None

    if nodegroups_present:
        settings._nodegroups_sources_active = "sources" not in (overrides or {})
        settings._nodegroups_ip24_active = "ip24" not in (overrides or {})
        settings._nodegroups_disqual_active = "disqual" not in (overrides or {})
    return settings


def apply_configured_logger_overrides(settings: Settings) -> None:
    """Apply configured logger levels when Uvicorn does not build the logging config."""
    for logger_name, level in settings.logging_overrides.items():
        logging.getLogger(logger_name).setLevel(level)


def _select_config_source(
    config_file: str | Path | None,
    config_json: str | None,
    env_file: str | None,
    env_json: str | None,
) -> tuple[str | None, str | Path | None]:
    if config_file is not None and config_json is not None:
        raise ConfigError("Specify only one of --config-file and --config-json")
    if config_file is not None:
        return "file", config_file
    if config_json is not None:
        return "inline", config_json

    if env_file is not None and env_json is not None:
        raise ConfigError(f"Set only one of {CONFIG_FILE_ENV} and {CONFIG_JSON_ENV}")
    if env_file is not None:
        return "file", env_file
    if env_json is not None:
        return "inline", env_json
    return None, None


def _load_document(
    source_kind: str,
    source_value: str | Path | None,
) -> dict[str, Any]:
    if source_kind == "file":
        path = Path(source_value).expanduser()
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ConfigError(f"Cannot read JSONC config file '{path}': {exc.strerror}") from None
        source_name = f"file '{path}'"
    else:
        content = str(source_value)
        source_name = "inline JSONC"

    try:
        document = json5.loads(content, allow_duplicate_keys=False)
    except (ValueError, TypeError) as exc:
        line = getattr(exc, "lineno", None)
        column = getattr(exc, "colno", None)
        position = f" at line {line}, column {column}" if line and column else ""
        raise ConfigError(f"Invalid JSONC in {source_name}{position}") from None

    if not isinstance(document, dict):
        raise ConfigError(f"Invalid JSONC in {source_name}: expected an object at the root")
    return document


def _settings_updates(document: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    updates: dict[str, Any] = {}
    known_top_level = {*_SECTION_FIELDS, "maintenance", "nodegroups", "logging"}
    _warn_unknown(document, known_top_level, "")

    for section, fields in _SECTION_FIELDS.items():
        if section not in document:
            continue
        values = _require_object(document[section], section)
        _warn_unknown(values, set(fields), section)
        for config_key, settings_field in fields.items():
            if config_key in values:
                _validate_and_store(
                    updates,
                    settings_field,
                    values[config_key],
                    f"{section}.{config_key}",
                )

    if "maintenance" in document:
        values = _require_object(document["maintenance"], "maintenance")
        known_maintenance = {"cleanup_interval_seconds", "grouping_interval_seconds", "retention"}
        _warn_unknown(values, known_maintenance, "maintenance")
        for key in ("cleanup_interval_seconds", "grouping_interval_seconds"):
            if key in values:
                _validate_and_store(updates, key, values[key], f"maintenance.{key}")
        if "retention" in values:
            retention = _require_object(values["retention"], "maintenance.retention")
            _warn_unknown(retention, set(_RETENTION_FIELDS), "maintenance.retention")
            for config_key, settings_field in _RETENTION_FIELDS.items():
                if config_key in retention:
                    _validate_and_store(
                        updates,
                        settings_field,
                        retention[config_key],
                        f"maintenance.retention.{config_key}",
                    )

    if "logging" in document:
        logging_config = _require_object(document["logging"], "logging")
        _warn_unknown(logging_config, {"overrides"}, "logging")
        if "overrides" in logging_config:
            updates["logging_overrides"] = _logger_overrides(logging_config["overrides"])

    nodegroups_present = "nodegroups" in document
    if nodegroups_present:
        if not isinstance(document["nodegroups"], list):
            raise ConfigError("Invalid value at 'nodegroups': expected an array")
        nodegroups, sources, ip24, disqual = _parse_nodegroups(document["nodegroups"])
        updates["nodegroups"] = nodegroups
        updates["sources"] = sources
        updates["ip24"] = ip24
        updates["disqual"] = disqual

    return updates, nodegroups_present


def _parse_nodegroups(
    raw_nodegroups: list[Any],
) -> tuple[list[NodeGroupDefinition], list[str], list[str], list[str]]:
    nodegroups: list[NodeGroupDefinition] = []
    sources: list[str] = []
    ip24: list[str] = []
    disqual: list[str] = []
    group_names: dict[str, str] = {}
    node_names: dict[str, str] = {}

    for group_index, raw_group in enumerate(raw_nodegroups):
        group_path = f"nodegroups[{group_index}]"
        if not isinstance(raw_group, dict):
            _warn_skipped(group_path, "expected an object")
            continue
        _warn_unknown(raw_group, {"name", "locations", "icon"}, group_path)
        icon = _nodegroup_icon(raw_group, group_path)
        name = _non_empty_string(raw_group.get("name"), f"{group_path}.name")
        if name is not None:
            normalized_name = name.casefold()
            if normalized_name == "all" or name == "<groups>":
                raise ConfigError(f"Reserved nodegroup name at '{group_path}.name'")
            previous_path = group_names.get(normalized_name)
            if previous_path is not None:
                raise ConfigError(
                    f"Duplicate nodegroup name at '{group_path}.name' "
                    f"(already declared at '{previous_path}')"
                )
            group_names[normalized_name] = f"{group_path}.name"
        locations_raw = raw_group.get("locations")
        if "locations" in raw_group and not isinstance(locations_raw, list):
            raise ConfigError(f"Invalid value at '{group_path}.locations': expected an array")
        if name is None or not isinstance(locations_raw, list):
            _warn_skipped(group_path, "missing or invalid required fields")
            continue

        locations: list[NodeLocationDefinition] = []
        for location_index, raw_location in enumerate(locations_raw):
            location_path = f"{group_path}.locations[{location_index}]"
            if not isinstance(raw_location, dict):
                _warn_skipped(location_path, "expected an object")
                continue
            if "icon" in raw_location:
                raise ConfigError(
                    f"Invalid value at '{location_path}.icon': group icons must be set at "
                    f"'{group_path}.icon'"
                )
            _warn_unknown(raw_location, {"alias", "ip", "nodes"}, location_path)
            alias = _non_empty_string(raw_location.get("alias"), f"{location_path}.alias")
            ip = _non_empty_string(raw_location.get("ip"), f"{location_path}.ip")
            nodes_raw = raw_location.get("nodes")
            if "nodes" in raw_location and not isinstance(nodes_raw, list):
                raise ConfigError(f"Invalid value at '{location_path}.nodes': expected an array")
            if not isinstance(nodes_raw, list):
                _warn_skipped(location_path, "missing or invalid required fields")
                continue
            if alias is None or ip is None:
                _warn_skipped(location_path, "missing or invalid required fields")
                continue

            nodes: list[NodeDefinition] = []
            for node_index, raw_node in enumerate(nodes_raw):
                node_path = f"{location_path}.nodes[{node_index}]"
                node = _parse_node(raw_node, node_path)
                if node is not None:
                    previous_path = node_names.get(node.name)
                    if previous_path is not None:
                        raise ConfigError(
                            f"Duplicate node name at '{node_path}.name' "
                            f"(already declared at '{previous_path}')"
                        )
                    node_names[node.name] = f"{node_path}.name"
                    nodes.append(node)
                    sources.append(_source_to_legacy_string(node))
                    disqual.extend(_disqualifications_to_legacy_strings(node))

            locations.append(NodeLocationDefinition(alias=alias, ip=ip, nodes=tuple(nodes)))
            ip24.append(f"{alias}|{ip}:{len(nodes)}")

        nodegroups.append(NodeGroupDefinition(name=name, locations=tuple(locations), icon=icon))

    return nodegroups, sources, ip24, disqual


def _nodegroup_icon(raw_group: Mapping[str, Any], path: str) -> str | None:
    if "icon" not in raw_group:
        return None
    icon = raw_group["icon"]
    if not isinstance(icon, str) or not _MDI_ICON_RE.fullmatch(icon):
        raise ConfigError(
            f"Invalid value at '{path}.icon': expected a non-empty MDI icon identifier "
            "such as 'mdi:home'"
        )
    return icon


def _parse_node(raw_node: Any, path: str) -> NodeDefinition | None:
    if not isinstance(raw_node, dict):
        _warn_skipped(path, "expected an object")
        return None
    allowed = {"name", "type", "path", "host", "port", "nodeapi_url", "disqualifications"}
    _warn_unknown(raw_node, allowed, path)

    name = _non_empty_string(raw_node.get("name"), f"{path}.name")
    kind = raw_node.get("type")
    if not name or ":" in name or "|" in name:
        _warn_skipped(f"{path}.name", "expected a non-empty source name without ':' or '|'")
        return None
    if name.casefold() == "all":
        raise ConfigError(f"Reserved node name at '{path}.name'")
    if kind not in ("file", "tcp"):
        _warn_skipped(f"{path}.type", "expected 'file' or 'tcp'")
        return None

    nodeapi_value = raw_node.get("nodeapi_url")
    if nodeapi_value is not None and not isinstance(nodeapi_value, str):
        _warn_skipped(f"{path}.nodeapi_url", "expected a string")
        return None
    nodeapi = nodeapi_value.strip() or None if isinstance(nodeapi_value, str) else None

    if kind == "file":
        source_path = _non_empty_string(raw_node.get("path"), f"{path}.path")
        if source_path is None or "host" in raw_node or "port" in raw_node:
            _warn_skipped(path, "file nodes require path and cannot define host or port")
            return None
        node_path: str | None = source_path
        host: str | None = None
        port: int | None = None
    else:
        host = _non_empty_string(raw_node.get("host"), f"{path}.host")
        port_value = raw_node.get("port")
        if (
            host is None
            or type(port_value) is not int
            or "path" in raw_node
            or port_value < 0
            or port_value > 65535
        ):
            _warn_skipped(path, "TCP nodes require a host and port from 0 to 65535")
            return None
        node_path = None
        port = port_value

    disqualifications_raw = raw_node.get("disqualifications", [])
    if not isinstance(disqualifications_raw, list):
        raise ConfigError(f"Invalid value at '{path}.disqualifications': expected an array")
    disqualifications = _parse_disqualifications(disqualifications_raw, f"{path}.disqualifications")

    return NodeDefinition(
        name=name,
        kind=kind,
        path=node_path,
        host=host,
        port=port,
        nodeapi=nodeapi,
        disqualifications=tuple(disqualifications),
    )


def _parse_disqualifications(raw_entries: list[Any], path: str) -> list[NodeDisqualification]:
    parsed: list[NodeDisqualification] = []
    for index, raw_entry in enumerate(raw_entries):
        entry_path = f"{path}[{index}]"
        if not isinstance(raw_entry, dict):
            _warn_skipped(entry_path, "expected an object")
            continue
        _warn_unknown(raw_entry, {"satellite_id", "period"}, entry_path)

        period = _non_empty_string(raw_entry.get("period"), f"{entry_path}.period")
        if period is None or not _PERIOD_RE.fullmatch(period):
            _warn_skipped(f"{entry_path}.period", "expected YYYY-MM")
            continue

        satellite = raw_entry.get("satellite_id")
        if satellite is None or satellite == "all":
            satellite_id = None
        elif isinstance(satellite, str) and satellite.strip():
            satellite_id = satellite.strip()
        else:
            _warn_skipped(
                f"{entry_path}.satellite_id",
                "expected a non-empty string, null, omitted, or 'all'",
            )
            continue
        parsed.append(NodeDisqualification(satellite_id=satellite_id, period=period))
    return parsed


def _source_to_legacy_string(node: NodeDefinition) -> str:
    if node.kind == "file":
        spec = node.path or ""
    elif node.host and node.port is not None:
        host = f"[{node.host}]" if ":" in node.host and not node.host.startswith("[") else node.host
        spec = f"{host}:{node.port}"
    else:
        raise ConfigError(f"Invalid node source '{node.name}'")
    source = f"{node.name}:{spec}"
    if node.nodeapi:
        source += f"|{node.nodeapi}"
    return source


def _disqualifications_to_legacy_strings(node: NodeDefinition) -> list[str]:
    return [
        f"{node.name}:{disqualification.satellite_id or ''}:{disqualification.period}"
        for disqualification in node.disqualifications
    ]


def _logger_overrides(raw_overrides: Any) -> dict[str, str]:
    overrides = _require_object(raw_overrides, "logging.overrides")
    parsed: dict[str, str] = {}
    for name, raw_level in overrides.items():
        path = f"logging.overrides.{name}"
        if not isinstance(name, str) or not name.strip():
            _warn_skipped(path, "logger name must be a non-empty string")
            continue
        if not isinstance(raw_level, str):
            _warn_skipped(path, "logger level must be a string")
            continue
        level = raw_level.strip().strip('"').strip("'").upper()
        try:
            logging._checkLevel(level)
        except (TypeError, ValueError):
            _warn_skipped(path, "invalid logging level")
            continue
        parsed[name.strip()] = level
    return parsed


def _validate_and_store(
    updates: dict[str, Any],
    settings_field: str,
    value: Any,
    config_path: str,
) -> None:
    field_type = Settings.model_fields[settings_field].annotation
    try:
        TypeAdapter(field_type).validate_python(value, strict=True)
    except ValidationError:
        raise ConfigError(f"Invalid value at '{config_path}'") from None
    updates[settings_field] = value


def _setting_path(field: str) -> str:
    for section, fields in _SECTION_FIELDS.items():
        for config_key, settings_field in fields.items():
            if settings_field == field:
                return f"{section}.{config_key}"
    for config_key, settings_field in _RETENTION_FIELDS.items():
        if settings_field == field:
            return f"maintenance.retention.{config_key}"
    if field == "cleanup_interval_seconds" or field == "grouping_interval_seconds":
        return f"maintenance.{field}"
    return field


def _require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"Invalid value at '{path}': expected an object")
    return value


def _non_empty_string(value: Any, path: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        _warn_skipped(path, "expected a non-empty string")
        return None
    return value.strip()


def _warn_unknown(values: Mapping[Any, Any], allowed: set[str], path: str) -> None:
    for key in values:
        if key not in allowed:
            key_path = f"{path}.{key}" if path else str(key)
            logger.warning("Ignoring unknown configuration key '%s'", key_path)


def _warn_skipped(path: str, reason: str) -> None:
    logger.warning("Skipping invalid configuration entry at '%s': %s", path, reason)

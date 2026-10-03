from __future__ import annotations

import argparse
import logging

import pytest

from server.src.cli import build_settings
from server.src.config_loader import (
    CONFIG_FILE_ENV,
    CONFIG_JSON_ENV,
    ConfigError,
    load_settings,
)


@pytest.fixture(autouse=True)
def clear_config_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)
    monkeypatch.delenv(CONFIG_JSON_ENV, raising=False)
    for key in (
        "MONSTR_API_PORT",
        "MONSTR_API_HOST",
        "MONSTR_SOURCES",
        "MONSTR_IP24",
        "MONSTR_DISQUAL",
        "MONSTR_LOG_OVERRIDES",
    ):
        monkeypatch.delenv(key, raising=False)


def test_loads_jsonc_and_flattens_nodegroups_in_declaration_order(tmp_path):
    settings = load_settings(config_json="""{
          // JSONC comments and trailing commas are supported.
          "api": { "port": 8123, },
          "nodeapi": {
            "poll_interval": 0.5,
            "batch_size": 8,
            "unprocessed_dir": "./unprocessed",
          },
          "nodegroups": [
            {
              "name": "group-a",
              "locations": [
                {
                  "alias": "site-a",
                  "ip": "192.0.2.10",
                  "nodes": [
                    {
                      "name": "node-a",
                      "type": "tcp",
                      "host": "logs.example.net",
                      "port": 9001,
                      "nodeapi_url": "https://node-a.example.net:14001/",
                      "disqualifications": [
                        { "period": "2025-10" },
                        { "satellite_id": "all", "period": "2025-11" },
                        { "satellite_id": "sat-a", "period": "2025-12" },
                      ],
                    },
                    {
                      "name": "node-b",
                      "type": "file",
                      "path": "./logs/node-b.log",
                    },
                  ],
                },
                { "alias": "empty-site", "ip": "192.0.2.11", "nodes": [] },
              ],
            },
          ],
        }""")

    assert settings.api_port == 8123
    assert settings.log_poll_interval == 0.5
    assert settings.log_batch_size == 8
    assert settings.unprocessed_log_dir == "./unprocessed"
    assert [group.name for group in settings.nodegroups] == ["group-a"]
    assert [source.name for source in settings.parsed_sources] == ["node-a", "node-b"]
    assert settings.parsed_sources[0].host == "logs.example.net"
    assert settings.parsed_sources[0].nodeapi == "https://node-a.example.net:14001/"
    assert settings.parsed_sources[1].path == (tmp_path / "logs" / "node-b.log").resolve()
    assert [
        (entry.alias, entry.ip, entry.expected_instances) for entry in settings.parsed_ip24
    ] == [
        ("site-a", "192.0.2.10", 2),
        ("empty-site", "192.0.2.11", 0),
    ]
    assert [
        (entry.source, entry.satellite_id, entry.period) for entry in settings.parsed_disqual
    ] == [
        ("node-a", "", "2025-10"),
        ("node-a", "", "2025-11"),
        ("node-a", "sat-a", "2025-12"),
    ]


def test_maps_all_grouped_settings_to_existing_settings():
    settings = load_settings(config_json="""{
          "api": {
            "host": "0.0.0.0",
            "port": 8124,
            "reload": true,
            "log_level": "debug",
            "cors_allow_origins": ["https://ui.example"],
          },
          "database": {
            "url": "sqlite+aiosqlite:///./test.db",
            "sql_echo": true,
            "write_suspend_seconds": 7,
          },
          "nodeapi": {
            "poll_interval": 2.5,
            "batch_size": 64,
            "unprocessed_dir": "./unprocessed",
            "poll_interval_seconds": 70,
            "estimated_payout_interval_seconds": 320,
            "held_history_interval_seconds": 321,
            "satellite_details_interval_seconds": 322,
            "paystub_interval_seconds": 323,
          },
          "maintenance": {
            "cleanup_interval_seconds": 44,
            "grouping_interval_seconds": 45,
            "retention": {
              "default_minutes": 46,
              "transfers_minutes": 47,
              "log_entries_minutes": 48,
              "transfer_grouped_minutes": 49,
              "hashstore_compaction_minutes": 50,
            },
          },
          "frontend": { "dist_dir": null },
        }""")

    assert (
        settings.api_host,
        settings.api_port,
        settings.api_reload,
        settings.api_log_level,
        settings.cors_allow_origins,
    ) == ("0.0.0.0", 8124, True, "debug", ["https://ui.example"])
    assert (settings.database_url, settings.sql_echo, settings.db_write_suspend_seconds) == (
        "sqlite+aiosqlite:///./test.db",
        True,
        7,
    )
    assert (
        settings.log_poll_interval,
        settings.log_batch_size,
        settings.unprocessed_log_dir,
        settings.nodeapi_poll_interval_seconds,
        settings.nodeapi_estimated_payout_interval_seconds,
        settings.nodeapi_held_history_interval_seconds,
        settings.nodeapi_satellite_details_interval_seconds,
        settings.nodeapi_paystub_interval_seconds,
    ) == (2.5, 64, "./unprocessed", 70, 320, 321, 322, 323)
    assert (
        settings.cleanup_interval_seconds,
        settings.grouping_interval_seconds,
        settings.retention_minutes,
        settings.retention_transfers_minutes,
        settings.retention_log_entries_minutes,
        settings.retention_transfer_grouped_minutes,
        settings.retention_hashstore_compaction_minutes,
    ) == (44, 45, 46, 47, 48, 49, 50)
    assert settings.frontend_dist_dir is None


def test_partial_jsonc_overrides_environment_and_legacy_cli_overrides_jsonc(monkeypatch):
    monkeypatch.setenv("MONSTR_API_PORT", "7000")
    monkeypatch.setenv("MONSTR_SOURCES", "legacy:logs.example.net:9001")
    args = argparse.Namespace(
        config_file=None,
        config_json='{"api":{"port":7100},"nodegroups":[{"name":"g","locations":[]}]}',
        sources=["cli:logs.example.net:9002"],
        ip24=[],
        disqual=[],
        host=None,
        port=None,
        log_level=None,
    )

    settings = build_settings(args)

    assert settings.api_port == 7100
    assert [source.name for source in settings.parsed_sources] == ["cli"]
    assert settings._nodegroups_sources_active is False
    assert settings._nodegroups_ip24_active is True


def test_config_nodegroups_override_legacy_lists_and_keep_all_invalid_list_empty(
    monkeypatch, caplog
):
    monkeypatch.setenv("MONSTR_SOURCES", "legacy:logs.example.net:9001")
    monkeypatch.setenv("MONSTR_IP24", "legacy-site|192.0.2.10:1")

    with caplog.at_level(logging.WARNING):
        settings = load_settings(config_json="""{
              "nodegroups": [{
                "name": "g",
                "locations": [{
                  "alias": "site-a",
                  "ip": "192.0.2.10",
                  "nodes": [{ "name": "bad", "type": "tcp", "port": 9001 }],
                }],
              }],
            }""")

    assert settings.parsed_sources == []
    assert settings.parsed_ip24[0].expected_instances == 0
    assert "nodegroups[0].locations[0].nodes[0]" in caplog.text


def test_invalid_list_entries_are_skipped_without_discarding_valid_entries(caplog):
    with caplog.at_level(logging.WARNING):
        settings = load_settings(config_json="""{
              "nodegroups": [{
                "name": "g",
                "locations": [{
                  "alias": "site-a",
                  "ip": "192.0.2.10",
                  "nodes": [
                    { "name": "good", "type": "tcp", "host": "logs.example.net", "port": 9001 },
                    { "name": "bad", "type": "tcp", "host": "logs.example.net", "port": "9002" },
                  ],
                }],
              }],
            }""")

    assert [source.name for source in settings.parsed_sources] == ["good"]
    assert settings.parsed_ip24[0].expected_instances == 1
    assert "Skipping invalid configuration entry" in caplog.text


def test_unknown_keys_warn_and_are_ignored(caplog):
    with caplog.at_level(logging.WARNING):
        settings = load_settings(config_json='{"api":{"port":8123,"porrt":1},"unknwon":true}')

    assert settings.api_port == 8123
    assert "api.porrt" in caplog.text
    assert "unknwon" in caplog.text


@pytest.mark.parametrize(
    ("config_json", "message"),
    [
        ('{"api":{"port":"not-a-port"}}', "api.port"),
        ('{"nodegroups":{}}', "nodegroups"),
        ('{"nodegroups":[{"name":"g","locations":"not-an-array"}]}', "locations"),
        (
            '{"nodegroups":[{"name":"g","locations":[{"alias":"a","ip":"192.0.2.1","nodes":"bad"}]}]}',
            "nodes",
        ),
    ],
)
def test_invalid_scalars_and_list_containers_stop_startup(config_json, message):
    with pytest.raises(ConfigError, match=message):
        load_settings(config_json=config_json)


def test_invalid_document_and_missing_file_stop_startup(tmp_path):
    malformed = tmp_path / "malformed.jsonc"
    malformed.write_text('{"api": {', encoding="utf-8")
    missing = tmp_path / "missing.jsonc"

    with pytest.raises(ConfigError, match="Invalid JSONC"):
        load_settings(config_file=malformed)
    with pytest.raises(ConfigError, match="Cannot read JSONC config file"):
        load_settings(config_file=missing)


def test_environment_selector_and_explicit_cli_selector_precedence(tmp_path, monkeypatch):
    config_file = tmp_path / "settings.jsonc"
    config_file.write_text('{"api":{"port":7200}}', encoding="utf-8")
    monkeypatch.setenv(CONFIG_FILE_ENV, str(config_file))
    assert load_settings().api_port == 7200

    assert load_settings(config_json='{"api":{"port":7300}}').api_port == 7300

    monkeypatch.setenv(CONFIG_JSON_ENV, '{"api":{"port":7400}}')
    with pytest.raises(ConfigError, match=CONFIG_FILE_ENV):
        load_settings()


def test_inline_environment_selector_loads_config(monkeypatch):
    monkeypatch.setenv(CONFIG_JSON_ENV, '{"api":{"port":7500}}')

    assert load_settings().api_port == 7500


def test_dotenv_config_selector_loads_inline_jsonc(tmp_path):
    (tmp_path / ".env").write_text(
        """MONSTR_CONFIG_JSON='{"api":{"port":7550}}'""",
        encoding="utf-8",
    )

    assert load_settings().api_port == 7550


def test_logger_overrides_are_normalized_and_invalid_entries_skipped(caplog):
    with caplog.at_level(logging.WARNING):
        settings = load_settings(
            config_json='{"logging":{"overrides":{"api.call":"debug","bad":"NOPE"}}}'
        )

    assert settings.logging_overrides == {"api.call": "DEBUG"}
    assert "logging.overrides.bad" in caplog.text


def test_direct_asgi_factory_uses_shared_settings_loader(monkeypatch):
    from server.src import main

    configured = load_settings(config_json='{"api":{"port":7600}}')
    monkeypatch.setattr(main, "load_settings", lambda: configured)
    monkeypatch.setattr(main, "create_app", lambda settings: settings)

    assert main.get_application() is configured


def test_cli_logger_overrides_take_precedence_over_json_and_environment(monkeypatch):
    from server.src import cli

    configured = load_settings(config_json='{"logging":{"overrides":{"test.logger":"INFO"}}}')
    monkeypatch.setenv("MONSTR_LOG_OVERRIDES", "test.logger:WARNING")
    captured: dict[str, object] = {}
    args = argparse.Namespace(log_overrides=["test.logger:ERROR"])
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    monkeypatch.setattr(cli, "build_settings", lambda _args: configured)
    monkeypatch.setattr(cli, "create_app", lambda _settings: object())
    monkeypatch.setattr(cli.logging.config, "dictConfig", lambda value: captured.update(value))
    monkeypatch.setattr(
        cli.uvicorn,
        "run",
        lambda _app, **kwargs: captured.update(log_config=kwargs["log_config"]),
    )

    cli.main()

    log_config = captured["log_config"]
    assert isinstance(log_config, dict)
    assert log_config["loggers"]["test.logger"]["level"] == "ERROR"

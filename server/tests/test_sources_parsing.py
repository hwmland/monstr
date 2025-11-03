from __future__ import annotations

from server.src.config import Settings


def test_sources_comma_separated():
    # Simulate env string like: "Node1:host:9001,Node2:host:9002"
    s = Settings(sources="Node1:192.168.10.21:9001,Node2:192.168.10.21:9002")
    assert isinstance(s.sources, list)
    assert s.sources == [
        "Node1:192.168.10.21:9001",
        "Node2:192.168.10.21:9002",
    ]


def test_sources_newline_separated():
    s = Settings(sources="Node1:192.168.10.21:9001\nNode2:192.168.10.21:9002")
    assert s.sources == [
        "Node1:192.168.10.21:9001",
        "Node2:192.168.10.21:9002",
    ]


def test_sources_list_input():
    s = Settings(sources=["Node1:192.168.10.21:9001", "Node2:192.168.10.21:9002"])
    assert s.sources == [
        "Node1:192.168.10.21:9001",
        "Node2:192.168.10.21:9002",
    ]


def test_sources_json_array_string():
    # If the environment provided a JSON array string, pydantic-settings would
    # decode it into a list before passing it to the validator; we also accept
    # that shape.
    json_array = '["Node1:192.168.10.21:9001", "Node2:192.168.10.21:9002"]'
    s = Settings(sources=json_array)
    assert s.sources == [
        "Node1:192.168.10.21:9001",
        "Node2:192.168.10.21:9002",
    ]

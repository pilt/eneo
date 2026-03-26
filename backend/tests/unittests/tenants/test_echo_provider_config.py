"""Unit tests for the simulator provider field configuration."""

from types import SimpleNamespace

import pytest

from intric.tenants.provider_field_config import (
    get_field_definitions,
    get_required_fields,
    validate_provider_credentials,
)


def test_simulator_has_no_required_fields():
    assert get_required_fields("simulator") == set()


def test_simulator_field_definitions_expose_strategy():
    fields = get_field_definitions("simulator")
    names = [f["name"] for f in fields]
    assert "strategy" in names


def test_simulator_strategy_field_is_not_required():
    fields = get_field_definitions("simulator")
    strategy_field = next(f for f in fields if f["name"] == "strategy")
    assert strategy_field["required"] is False


def test_simulator_strategy_field_is_in_config():
    fields = get_field_definitions("simulator")
    strategy_field = next(f for f in fields if f["name"] == "strategy")
    assert strategy_field["in_"] == "config"


def test_simulator_validates_with_empty_credentials():
    req = SimpleNamespace(api_key=None)
    errors = validate_provider_credentials("simulator", req, strict_mode=False)
    assert errors == []


def test_simulator_validates_in_strict_mode():
    req = SimpleNamespace(api_key=None)
    errors = validate_provider_credentials("simulator", req, strict_mode=True)
    assert errors == []


def test_simulator_case_insensitive():
    assert get_required_fields("Simulator") == set()
    assert get_required_fields("SIMULATOR") == set()

"""Unit tests for the echo provider field configuration."""

from types import SimpleNamespace

import pytest

from intric.tenants.provider_field_config import (
    get_field_definitions,
    get_required_fields,
    validate_provider_credentials,
)


def test_echo_has_no_required_fields():
    assert get_required_fields("echo") == set()


def test_echo_field_definitions_are_empty():
    assert get_field_definitions("echo") == []


def test_echo_validates_with_empty_credentials():
    req = SimpleNamespace(api_key=None)
    errors = validate_provider_credentials("echo", req, strict_mode=False)
    assert errors == []


def test_echo_validates_in_strict_mode():
    req = SimpleNamespace(api_key=None)
    errors = validate_provider_credentials("echo", req, strict_mode=True)
    assert errors == []


def test_echo_case_insensitive():
    assert get_required_fields("Echo") == set()
    assert get_required_fields("ECHO") == set()

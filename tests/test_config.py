import json
from pathlib import Path

from openglider.utils.config import ConfigNew, UserConfig


class ExampleConfig(ConfigNew):
    known: int = 0


def test_config_read_ignores_unknown_fields(tmp_path: Path) -> None:
    filename = tmp_path / "config.json"
    payload = {
        "data": {
            "data": {
                "dct": {"known": 7, "unexpected": "ignored"}
            }
        }
    }
    filename.write_text(json.dumps(payload))

    config = ExampleConfig.read(filename)

    assert config.known == 7


def test_config_read_returns_empty_config_for_invalid_payload_shape(tmp_path: Path) -> None:
    filename = tmp_path / "config.json"
    filename.write_text(json.dumps({"data": {"data": ["not", "a", "dict"]}}))

    config = ExampleConfig.read(filename)

    assert config.known == 0


def test_user_config_read_returns_empty_config_for_invalid_payload_shape(tmp_path: Path) -> None:
    filename = tmp_path / "user_config.json"
    filename.write_text(json.dumps({"data": {"data": ["not", "a", "dict"]}}))

    config = UserConfig.read()

    assert config.model_dump() == {}

from __future__ import annotations

import json
import html
from pathlib import Path
from typing import Any, ClassVar, Self
from collections.abc import Iterator

from pydantic import ConfigDict
import logging

from openglider.utils.dataclass import BaseModel

logger = logging.getLogger(__name__)

from openglider.utils.config_old import Config

class ConfigBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    @staticmethod
    def _extract_payload(data: Any) -> Any:
        if not isinstance(data, dict):
            return {}

        outer = data.get("data")
        if not isinstance(outer, dict):
            return {}

        inner = outer.get("data")
        if not isinstance(inner, dict):
            return {}

        payload = inner.get("dct")
        return payload if isinstance(payload, dict) else {}


class ConfigNew(ConfigBase):

    def __json__(self) -> dict[str, Any]:
        return {
            "dct": self.__dict__
        }

    def _repr_html_(self) -> str:
        html_str = """<table>\n"""
        for key, value in self.__dict__.items():
            html_str += f"""    <tr>
                <td>{key}</td>
                <td>{html.escape(repr(value))}</td>
                </tr>
            """
        
        html_str += "</table>"

        return html_str

    def write(self, filename: str) -> None:
        import openglider.jsonify
        with open(filename, "w") as jsonfile:
            openglider.jsonify.dump(self, jsonfile)

    @classmethod
    def read(cls, filename: str | Path) -> ConfigNew:
        with open(filename) as jsonfile:
            data = json.load(jsonfile)

        payload = cls._extract_payload(data)
        if not isinstance(payload, dict):
            return cls()

        clean_payload = {
            key: value
            for key, value in payload.items()
            if key in cls.model_fields and not key.startswith("_")
        }
        return cls.model_validate(clean_payload)

class UserConfig(ConfigBase):
    """
    User configuration for OpenGlider.
    This class is used to store user-specific settings and preferences.
    They will be persisted in a JSON file located in the user's openglider home directory.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")

    filename: ClassVar[str] = "user_config.json"

    def __json__(self) -> dict[str, Any]:
        return {
            "dct": self.model_dump(exclude_none=True)
        }

    def _repr_html_(self) -> str:
        html_str = """<table>\n"""
        for key, value in self.__dict__.items():
            html_str += f"""    <tr>
                <td>{key}</td>
                <td>{html.escape(repr(value))}</td>
                </tr>
            """
        
        html_str += "</table>"

        return html_str

    def write(self) -> None:
        import openglider.jsonify
        user_config_path = Path.home() / "openglider" / self.__class__.filename
        user_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(user_config_path, "w") as jsonfile:
            openglider.jsonify.dump(self, jsonfile)

    @classmethod
    def read(cls) -> Self:
        user_config_path = Path.home() / "openglider" / cls.filename
        if not user_config_path.exists():
            return cls()

        with open(user_config_path) as jsonfile:
            data = json.load(jsonfile)

        payload = cls._extract_payload(data)
        if not isinstance(payload, dict):
            return cls()

        clean_payload = {
            key: value
            for key, value in payload.items()
            if key in cls.model_fields and not key.startswith("_")
        }
        return cls.model_validate(clean_payload)
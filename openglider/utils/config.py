from __future__ import annotations

import json
import html
from pathlib import Path
from typing import Any
from collections.abc import Iterator

from pydantic import ConfigDict, parse_obj_as
import logging

from openglider.utils.dataclass import BaseModel

logger = logging.getLogger(__name__)

from openglider.utils.config_old import Config

class ConfigNew(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

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

        return parse_obj_as(cls, data["data"]["data"]["dct"])

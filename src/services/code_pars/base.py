from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ParseCode:
    language: str
    code: str

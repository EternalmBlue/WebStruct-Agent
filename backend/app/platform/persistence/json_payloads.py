from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def jsonable_state(state: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, BaseModel):
            payload[key] = value.model_dump(mode="json")
        elif isinstance(value, list):
            payload[key] = [
                item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                for item in value
            ]
        elif isinstance(value, dict):
            payload[key] = jsonable_mapping(value)
        else:
            payload[key] = value
    return payload


def jsonable_mapping(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item.model_dump(mode="json") if isinstance(item, BaseModel) else item
        for key, item in value.items()
    }

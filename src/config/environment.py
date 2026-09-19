"""Canonical LifeWeave configuration, with the original installation aliases."""
import os
from typing import Mapping


def compatible_environment(values: Mapping[str, str]) -> dict[str, str]:
    result = dict(values)
    for key, value in values.items():
        if key.startswith('GONGZUO_'):
            result.setdefault('LIFEWEAVE_' + key[len('GONGZUO_'):], value)
    return result


def get_env(name: str, default: str | None = None) -> str | None:
    return compatible_environment(os.environ).get(name, default)

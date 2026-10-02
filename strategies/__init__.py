# -*- coding: utf-8 -*-
from .base_strategy import BaseAssayStrategy, StrategyError
from .math_models import (
    BlankSubtractionStrategy,
    FourPLStrategy,
    CellViabilityStrategy
)

ALL_STRATEGIES = [
    BlankSubtractionStrategy(),
    FourPLStrategy(),
    CellViabilityStrategy()
]

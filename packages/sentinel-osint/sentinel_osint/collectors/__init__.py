

from .base import BaseCollector
from .fitness import FitnessCollector
from .property import PropertyCollector
from .reviews import ReviewsCollector
from .username import UsernameCollector
from .wigle import WiGLECollector

ALL_COLLECTORS: list[type[BaseCollector]] = [
    FitnessCollector,
    WiGLECollector,
    ReviewsCollector,
    PropertyCollector,
    UsernameCollector,
]

__all__ = [
    "ALL_COLLECTORS",
    "BaseCollector",
    "FitnessCollector",
    "PropertyCollector",
    "ReviewsCollector",
    "UsernameCollector",
    "WiGLECollector",
]

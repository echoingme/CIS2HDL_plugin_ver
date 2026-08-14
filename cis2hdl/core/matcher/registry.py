"""MatcherRegistry — class-level registry for all matcher instances.

Provides register/get/list_all/get_by_priority for management.
"""

from __future__ import annotations


class MatcherRegistry:
    """Class-level registry for MatcherBase instances.

    All methods are class methods — the registry is a single shared store
    accessible anywhere without instantiation.

    Usage:
        MatcherRegistry.register(ExactMatcher())
        matcher = MatcherRegistry.get("exact")
        for m in MatcherRegistry.get_by_priority():
            ...
    """

    _matchers: dict[str, "MatcherBase"] = {}
    """Class-level storage: {MATCHER_NAME: matcher_instance}."""

    @classmethod
    def register(cls, matcher: "MatcherBase") -> None:
        """Register a matcher instance.

        If a matcher with the same name already exists, it is overwritten.

        Args:
            matcher: A MatcherBase instance to register.
        """
        cls._matchers[matcher.MATCHER_NAME] = matcher

    @classmethod
    def get(cls, name: str) -> "MatcherBase":
        """Retrieve a registered matcher by name.

        Args:
            name: The MATCHER_NAME of the desired matcher.

        Returns:
            The MatcherBase instance.

        Raises:
            KeyError: If no matcher with the given name is registered.
        """
        if name not in cls._matchers:
            raise KeyError(
                f"Matcher '{name}' not registered. "
                f"Available: {list(cls._matchers.keys())}"
            )
        return cls._matchers[name]

    @classmethod
    def list_all(cls) -> list["MatcherBase"]:
        """Return all registered matchers in insertion order.

        Returns:
            List of MatcherBase instances.
        """
        return list(cls._matchers.values())

    @classmethod
    def get_by_priority(cls) -> list["MatcherBase"]:
        """Return all registered matchers sorted by MATCHER_PRIORITY (ascending).

        Lower priority numbers appear first.

        Returns:
            Sorted list of MatcherBase instances.
        """
        return sorted(cls._matchers.values(), key=lambda m: m.MATCHER_PRIORITY)

    @classmethod
    def clear(cls) -> None:
        """Remove all registered matchers (useful for testing)."""
        cls._matchers.clear()

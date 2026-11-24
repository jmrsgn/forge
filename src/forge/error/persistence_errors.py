"""Errors raised while persisting discovery state."""


class DiscoveryPersistenceError(ValueError):
    """A discovery state file cannot be safely created, read, or updated."""

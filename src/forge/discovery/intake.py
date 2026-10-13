"""Capture the original idea for a new project discovery."""

from forge.discovery.models import ProjectDiscovery


def intake_idea(idea: str) -> ProjectDiscovery:
    """Create an initial discovery from the user's unmodified idea."""
    return ProjectDiscovery(original_idea=idea)

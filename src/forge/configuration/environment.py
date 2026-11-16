"""Load local development environment values without overriding the process environment."""

from pathlib import Path

from dotenv import load_dotenv

# Anchor local credentials to this Forge source checkout, never to a target project.
LOCAL_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def load_local_environment() -> None:
    """Load the Forge checkout's optional .env file for local development."""
    load_dotenv(dotenv_path=LOCAL_ENV_PATH, override=False, interpolate=False)

"""Tests for loading project configuration from YAML."""

from pathlib import Path

import pytest

from forge.configuration import ConfigurationError, ProjectConfig, load_project_config


def test_load_valid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "project.yaml"
    path.write_text("schema_version: 1\nname: Fitness App\n", encoding="utf-8")

    assert load_project_config(path) == ProjectConfig(schema_version=1, name="Fitness App")


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("name: Forge\n", "schema_version"),
        ("schema_version: 1\n", "name"),
        ("schema_version: 2\nname: Forge\n", "Unsupported schema version"),
        ("schema_version: 1\nname: [unclosed\n", "Malformed YAML"),
        ("", "configuration"),
    ],
)
def test_load_rejects_invalid_yaml_or_configuration(
    tmp_path: Path, contents: str, message: str
) -> None:
    path = tmp_path / "project.yaml"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigurationError, match=message):
        load_project_config(path)


def test_load_reports_file_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.yaml"

    with pytest.raises(ConfigurationError, match="Cannot read configuration"):
        load_project_config(path)

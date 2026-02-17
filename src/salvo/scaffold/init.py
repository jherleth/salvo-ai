"""Project scaffolding for `salvo init`.

Generates a complete Salvo project with config, example scenario,
shared tool definitions, and .gitignore -- all non-interactive with
sensible defaults.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

console = Console()

# Template files to generate: (template_name, output_path)
_FILE_MAP: list[tuple[str, str]] = [
    ("salvo.yaml", "salvo.yaml"),
    ("example.yaml", "scenarios/example.yaml"),
    ("tools/example_tool.yaml", "tools/example_tool.yaml"),
]


class ProjectExistsError(Exception):
    """Raised when scaffold_project would overwrite existing files."""

    def __init__(self, conflicting_files: list[str]) -> None:
        self.conflicting_files = conflicting_files
        files_str = ", ".join(conflicting_files)
        super().__init__(f"Files already exist: {files_str}")


def _get_templates_dir() -> Path:
    """Return the path to the templates directory within the package."""
    return Path(__file__).parent / "templates"


def scaffold_project(directory: Path, force: bool = False) -> list[str]:
    """Generate a complete Salvo project in the given directory.

    Creates salvo.yaml config, an example scenario with tool definitions,
    and a .gitignore. Non-interactive with sensible defaults.

    Args:
        directory: Target directory for the project.
        force: If True, overwrite existing files. If False, raise
            ProjectExistsError when any target file already exists.

    Returns:
        List of created file paths (relative to directory).

    Raises:
        ProjectExistsError: If target files exist and force is False.
    """
    directory = directory.resolve()
    templates_dir = _get_templates_dir()

    # Check for conflicting files (unless force is True)
    if not force:
        conflicts: list[str] = []
        for _, output_path in _FILE_MAP:
            target = directory / output_path
            if target.exists():
                conflicts.append(output_path)
        if conflicts:
            raise ProjectExistsError(conflicts)

    # Create directories
    (directory / "scenarios").mkdir(parents=True, exist_ok=True)
    (directory / "tools").mkdir(parents=True, exist_ok=True)

    # Copy template files
    created: list[str] = []
    for template_name, output_path in _FILE_MAP:
        template_file = templates_dir / template_name
        target = directory / output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(template_file.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(output_path)

    # Handle .gitignore
    gitignore_path = directory / ".gitignore"
    salvo_entry = ".salvo/"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        if salvo_entry not in content.splitlines():
            # Append .salvo/ to existing .gitignore
            if content and not content.endswith("\n"):
                content += "\n"
            content += salvo_entry + "\n"
            gitignore_path.write_text(content, encoding="utf-8")
            created.append(".gitignore (updated)")
    else:
        gitignore_path.write_text(salvo_entry + "\n", encoding="utf-8")
        created.append(".gitignore")

    # Print success message
    console.print("[green][bold]Project initialized successfully![/bold][/green]")
    for path in created:
        console.print(f"  [green]\u2713[/green] {path}")

    return created

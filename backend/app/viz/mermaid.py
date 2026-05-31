"""Mermaid diagram rendering to PNG/SVG."""

import subprocess
import tempfile
from pathlib import Path


def render_mermaid(
    diagram: str,
    output_path: Path,
    format: str = "png",
    width: int = 1200,
) -> Path:
    """Render a Mermaid diagram to PNG or SVG.

    Args:
        diagram: Mermaid diagram syntax
        output_path: Output file path
        format: Output format (png or svg)
        width: Image width in pixels

    Returns:
        Path to rendered file

    Raises:
        RuntimeError: If mmdc (mermaid-cli) is not installed
    """
    if not _mmdc_available():
        raise RuntimeError(
            "mermaid-cli (mmdc) not found. Install with: npm install -g @mermaid-js/mermaid-cli"
        )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
        f.write(diagram)
        input_path = Path(f.name)

    try:
        cmd = [
            "mmdc",
            "-i", str(input_path),
            "-o", str(output_path),
            "-w", str(width),
        ]
        if format == "svg":
            cmd.extend(["-e", "svg"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"mmdc failed: {result.stderr}")

        return output_path
    finally:
        input_path.unlink(missing_ok=True)


def _mmdc_available() -> bool:
    """Check if mermaid-cli is available."""
    try:
        subprocess.run(
            ["mmdc", "--version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

"""Tests for visualization pipeline."""

import os
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.viz import render_mermaid, create_chart, create_social_card


class TestMermaid:
    """Tests for Mermaid diagram rendering."""

    def test_render_simple_diagram(self, tmp_path: Path) -> None:
        """Test rendering a simple flowchart."""
        diagram = """
        graph TD
            A[Start] --> B[Process]
            B --> C[End]
        """
        output = tmp_path / "test.png"

        # Skip if mmdc not available
        pytest.importorskip("subprocess")
        try:
            render_mermaid(diagram, output)
            assert output.exists()
            assert output.stat().st_size > 0
        except RuntimeError as e:
            if "mmdc" in str(e):
                pytest.skip("mermaid-cli not installed")
            raise

    def test_render_invalid_diagram_raises(self, tmp_path: Path) -> None:
        """Test that invalid diagram syntax raises error."""
        diagram = "invalid syntax here"
        output = tmp_path / "test.png"

        try:
            with pytest.raises(RuntimeError):
                render_mermaid(diagram, output)
        except RuntimeError as e:
            if "mmdc" in str(e):
                pytest.skip("mermaid-cli not installed")
            raise


class TestCharts:
    """Tests for matplotlib/seaborn chart generation."""

    def test_bar_chart(self, tmp_path: Path) -> None:
        """Test bar chart generation."""
        output = tmp_path / "bar.png"
        create_chart(
            chart_type="bar",
            data={
                "x": ["A", "B", "C"],
                "y": [10, 20, 15],
                "ylabel": "Count",
            },
            output_path=output,
            title="Test Bar Chart",
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def test_line_chart(self, tmp_path: Path) -> None:
        """Test line chart generation."""
        output = tmp_path / "line.png"
        create_chart(
            chart_type="line",
            data={
                "x": [1, 2, 3, 4, 5],
                "y": [2, 4, 6, 8, 10],
                "xlabel": "Time",
                "ylabel": "Value",
            },
            output_path=output,
            title="Test Line Chart",
        )
        assert output.exists()

    def test_scatter_chart(self, tmp_path: Path) -> None:
        """Test scatter plot generation."""
        output = tmp_path / "scatter.png"
        create_chart(
            chart_type="scatter",
            data={
                "x": [1, 2, 3, 4, 5],
                "y": [5, 4, 3, 2, 1],
            },
            output_path=output,
        )
        assert output.exists()

    def test_heatmap_chart(self, tmp_path: Path) -> None:
        """Test heatmap generation."""
        output = tmp_path / "heatmap.png"
        create_chart(
            chart_type="heatmap",
            data={
                "matrix": [[1, 2], [3, 4]],
                "xticklabels": ["A", "B"],
                "yticklabels": ["X", "Y"],
            },
            output_path=output,
        )
        assert output.exists()

    def test_unknown_chart_type_raises(self, tmp_path: Path) -> None:
        """Test that unknown chart type raises ValueError."""
        output = tmp_path / "unknown.png"
        with pytest.raises(ValueError, match="Unknown chart type"):
            create_chart(
                chart_type="unknown",
                data={},
                output_path=output,
            )


class TestSocialCards:
    """Tests for html2image social card generation.

    These tests are skipped on low-RAM environments or when
    SKIP_HTML2IMAGE environment variable is set.
    """

    @pytest.fixture(autouse=True)
    def check_html2image(self) -> None:
        """Skip tests if html2image should be skipped."""
        if os.environ.get("SKIP_HTML2IMAGE", "").lower() in ("1", "true", "yes"):
            pytest.skip("SKIP_HTML2IMAGE is set (low-RAM environment)")

    def test_create_social_card(self, tmp_path: Path) -> None:
        """Test basic social card generation."""
        output = tmp_path / "card.png"
        html = """
        <!DOCTYPE html>
        <html>
        <body style="background: #1a1a2e; color: white; padding: 40px;">
            <h1>Test Card</h1>
            <p>This is a test social card.</p>
        </body>
        </html>
        """
        try:
            create_social_card(html, output)
            assert output.exists()
            assert output.stat().st_size > 0
        except RuntimeError as e:
            if "html2image" in str(e):
                pytest.skip("html2image not installed")
            raise

    def test_create_social_card_custom_size(self, tmp_path: Path) -> None:
        """Test social card with custom dimensions."""
        output = tmp_path / "card_custom.png"
        html = "<html><body><h1>Custom Size</h1></body></html>"
        try:
            create_social_card(html, output, size=(800, 400))
            assert output.exists()
        except RuntimeError as e:
            if "html2image" in str(e):
                pytest.skip("html2image not installed")
            raise

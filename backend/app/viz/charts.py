"""Chart generation with matplotlib/seaborn."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import seaborn as sns


def create_chart(
    chart_type: str,
    data: dict[str, Any],
    output_path: Path,
    title: str = "",
    figsize: tuple[int, int] = (10, 6),
    dpi: int = 150,
) -> Path:
    """Create a chart and save to file.

    Args:
        chart_type: Type of chart (bar, line, scatter, heatmap)
        data: Chart data (format depends on chart_type)
        output_path: Output file path (PNG/SVG)
        title: Chart title
        figsize: Figure size in inches
        dpi: Resolution for raster formats

    Returns:
        Path to saved chart
    """
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=figsize)

    if chart_type == "bar":
        _bar_chart(ax, data)
    elif chart_type == "line":
        _line_chart(ax, data)
    elif chart_type == "scatter":
        _scatter_chart(ax, data)
    elif chart_type == "heatmap":
        _heatmap_chart(ax, data)
    else:
        raise ValueError(f"Unknown chart type: {chart_type}")

    if title:
        ax.set_title(title, fontsize=14, fontweight="bold")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return output_path


def _bar_chart(ax: plt.Axes, data: dict[str, Any]) -> None:
    """Create a bar chart."""
    x = data.get("x", [])
    y = data.get("y", [])
    labels = data.get("labels", x)

    bars = ax.bar(range(len(y)), y, color=sns.color_palette("viridis", len(y)))
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel(data.get("ylabel", "Value"))

    # Add value labels on bars
    for bar, value in zip(bars, y):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.2f}" if isinstance(value, float) else str(value),
            ha="center",
            va="bottom",
            fontsize=9,
        )


def _line_chart(ax: plt.Axes, data: dict[str, Any]) -> None:
    """Create a line chart."""
    x = data.get("x", [])
    y = data.get("y", [])

    ax.plot(x, y, marker="o", linewidth=2, markersize=6)
    ax.set_xlabel(data.get("xlabel", "X"))
    ax.set_ylabel(data.get("ylabel", "Y"))


def _scatter_chart(ax: plt.Axes, data: dict[str, Any]) -> None:
    """Create a scatter plot."""
    x = data.get("x", [])
    y = data.get("y", [])
    hue = data.get("hue", None)

    if hue:
        sns.scatterplot(x=x, y=y, hue=hue, ax=ax, s=100)
    else:
        ax.scatter(x, y, s=100, alpha=0.7)

    ax.set_xlabel(data.get("xlabel", "X"))
    ax.set_ylabel(data.get("ylabel", "Y"))


def _heatmap_chart(ax: plt.Axes, data: dict[str, Any]) -> None:
    """Create a heatmap."""
    matrix = data.get("matrix", [])
    xticklabels = data.get("xticklabels", "auto")
    yticklabels = data.get("yticklabels", "auto")

    sns.heatmap(
        matrix,
        ax=ax,
        annot=data.get("annot", True),
        fmt=data.get("fmt", ".2f"),
        cmap=data.get("cmap", "viridis"),
        xticklabels=xticklabels,
        yticklabels=yticklabels,
    )

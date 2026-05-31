"""Social card generation with html2image.

WARNING: This module uses headless Chrome which consumes significant RAM.
Always run sequentially, never in parallel. On low-RAM machines (<16GB),
consider delegating to a more powerful device.
"""

import html
import os
import sys
from pathlib import Path

# Skip import on low-RAM environments during testing
SKIP_HTML2IMAGE = os.environ.get("SKIP_HTML2IMAGE", "").lower() in ("1", "true", "yes")


def create_social_card(
    html_content: str,
    output_path: Path,
    size: tuple[int, int] = (1200, 630),
) -> Path:
    """Generate a social card image from HTML.

    Args:
        html_content: HTML/CSS content for the card
        output_path: Output file path (PNG)
        size: Card dimensions (width, height)

    Returns:
        Path to generated image

    Raises:
        RuntimeError: If html2image is not available or skipped
    """
    if SKIP_HTML2IMAGE:
        raise RuntimeError(
            "html2image skipped: SKIP_HTML2IMAGE environment variable is set. "
            "This is typically done on low-RAM machines."
        )

    try:
        from html2image import Html2Image
    except ImportError:
        raise RuntimeError(
            "html2image not installed. Install with: pip install html2image"
        )

    # Create temporary directory for html2image output
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    hti = Html2Image(
        output_path=str(output_dir),
        size=size,
        custom_flags=[
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
        ],
    )

    # Generate image
    hti.screenshot(
        html_str=html_content,
        save_as=output_path.name,
    )

    return output_path


def create_experiment_card(
    experiment_id: str,
    title: str,
    key_finding: str,
    output_path: Path,
) -> Path:
    """Generate a standardized experiment result card.

    Args:
        experiment_id: Experiment identifier (e.g., "001-content-structure")
        title: Experiment title
        key_finding: Main finding to highlight
        output_path: Output file path

    Returns:
        Path to generated card
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{
            margin: 0;
            padding: 40px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #ffffff;
            display: flex;
            flex-direction: column;
            justify-content: center;
            height: 100vh;
            box-sizing: border-box;
        }}
        .badge {{
            display: inline-block;
            background: #e94560;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 20px;
            width: fit-content;
        }}
        h1 {{
            font-size: 36px;
            margin: 0 0 30px 0;
            line-height: 1.2;
        }}
        .finding {{
            background: rgba(255, 255, 255, 0.1);
            border-left: 4px solid #e94560;
            padding: 20px;
            font-size: 24px;
            line-height: 1.4;
            border-radius: 0 8px 8px 0;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 16px;
            color: #a0a0a0;
        }}
    </style>
    </head>
    <body>
        <div class="badge">AI SEO Lab • {html.escape(experiment_id)}</div>
        <h1>{html.escape(title)}</h1>
        <div class="finding">{html.escape(key_finding)}</div>
        <div class="footer">lang-forge • todo es lenguaje</div>
    </body>
    </html>
    """
    return create_social_card(html_content, output_path)

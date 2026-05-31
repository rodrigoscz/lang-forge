"""
Experiment 001: Content Structure vs AI Overview Citations

This script runs the first experiment: testing how semantic HTML and
heading hierarchy affect citation rates in AI Overviews.

Usage:
    python -m experiments.001_content_structure.run

Environment:
    DATAFORSEO_LOGIN: DataforSEO API login
    DATAFORSEO_PASSWORD: DataforSEO API password
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.dataforseo import DataforSEOClient, DataforSEOCache, QueryBudget
from app.variants import VariantGenerator
from app.viz import create_chart, create_social_card

# Experiment configuration
EXPERIMENT_ID = "001-content-structure"
EXPERIMENT_DIR = Path(__file__).parent
DATA_DIR = EXPERIMENT_DIR / "data"
OUTPUT_DIR = EXPERIMENT_DIR / "outputs"

# Test queries (subset for MVP)
TEST_QUERIES = [
    "how to structure content for SEO",
    "best practices for heading hierarchy",
    "semantic HTML for search engines",
    "how AI understands web content",
    "content optimization for AI overviews",
]

# Variant types to test
VARIANT_TYPES = [
    "plain",           # No semantic structure
    "h2_structured",   # Proper H2 hierarchy
    "semantic",        # Full semantic HTML (article, section, nav)
    "schema_enriched", # Semantic + Schema.org markup
]


def setup_directories() -> None:
    """Create necessary directories."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_variants() -> dict[str, Path]:
    """Generate all page variants for the experiment.

    Returns:
        Dict mapping variant type to file path
    """
    generator = VariantGenerator()
    variants = {}

    for variant_type in VARIANT_TYPES:
        output_path = DATA_DIR / f"{variant_type}.html"
        generator.generate(variant_type, output_path)
        variants[variant_type] = output_path
        print(f"Generated variant: {variant_type} -> {output_path}")

    return variants


def collect_ai_overview_data(client: DataforSEOClient) -> list[dict]:
    """Query AI Overviews for test queries and collect citation data.

    Args:
        client: DataforSEO API client

    Returns:
        List of results per query
    """
    results = []

    for query in TEST_QUERIES:
        print(f"Querying: {query}")
        try:
            response = client.serps_ai_overview(query)
            results.append({
                "query": query,
                "citations": _extract_citations(response),
                "raw_response": response,
            })
        except Exception as e:
            print(f"Error querying '{query}': {e}")
            results.append({
                "query": query,
                "citations": [],
                "error": str(e),
            })

    return results


def _extract_citations(response: dict) -> list[dict]:
    """Extract citation URLs from AI Overview response."""
    citations = []

    # Navigate DataforSEO response structure
    tasks = response.get("tasks", [])
    for task in tasks:
        results = task.get("result", [])
        for result in results:
            items = result.get("items", [])
            for item in items:
                if item.get("type") == "ai_overview":
                    references = item.get("references", [])
                    for ref in references:
                        citations.append({
                            "url": ref.get("url"),
                            "title": ref.get("title"),
                            "domain": ref.get("domain"),
                        })

    return citations


def analyze_results(results: list[dict]) -> dict:
    """Analyze experiment results.

    Args:
        results: Raw results from data collection

    Returns:
        Analysis summary
    """
    total_queries = len(results)
    queries_with_citations = sum(1 for r in results if r.get("citations"))
    total_citations = sum(len(r.get("citations", [])) for r in results)

    # Count citations by domain (to see if our variants get cited)
    domain_counts = {}
    for result in results:
        for citation in result.get("citations", []):
            domain = citation.get("domain", "unknown")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

    return {
        "total_queries": total_queries,
        "queries_with_citations": queries_with_citations,
        "total_citations": total_citations,
        "citation_rate": queries_with_citations / total_queries if total_queries > 0 else 0,
        "top_domains": sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10],
    }


def generate_visualizations(analysis: dict) -> None:
    """Generate charts and cards from analysis.

    Args:
        analysis: Analysis results
    """
    # Bar chart: citations by domain
    if analysis["top_domains"]:
        domains, counts = zip(*analysis["top_domains"][:5])
        create_chart(
            chart_type="bar",
            data={
                "x": list(domains),
                "y": list(counts),
                "ylabel": "Number of Citations",
            },
            output_path=OUTPUT_DIR / "citations_by_domain.png",
            title="AI Overview Citations by Domain",
        )
        print(f"Generated: {OUTPUT_DIR / 'citations_by_domain.png'}")

    # Social card with key finding
    key_finding = f"Citation rate: {analysis['citation_rate']:.1%} ({analysis['queries_with_citations']}/{analysis['total_queries']} queries)"
    try:
        create_social_card(
            experiment_id=EXPERIMENT_ID,
            title="Content Structure vs AI Overview Citations",
            key_finding=key_finding,
            output_path=OUTPUT_DIR / "social_card.png",
        )
        print(f"Generated: {OUTPUT_DIR / 'social_card.png'}")
    except RuntimeError as e:
        print(f"Skipped social card: {e}")


def save_results(results: list[dict], analysis: dict) -> None:
    """Save results to JSON files.

    Args:
        results: Raw results
        analysis: Analysis summary
    """
    with open(DATA_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    with open(DATA_DIR / "analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"Saved results to {DATA_DIR / 'results.json'}")
    print(f"Saved analysis to {DATA_DIR / 'analysis.json'}")


def main() -> None:
    """Run the experiment."""
    print(f"=== Experiment {EXPERIMENT_ID} ===")
    print("Content Structure vs AI Overview Citations\n")

    # Setup
    setup_directories()

    # Step 1: Generate variants
    print("Step 1: Generating page variants...")
    variants = generate_variants()
    print(f"Generated {len(variants)} variants\n")

    # Step 2: Collect data
    print("Step 2: Collecting AI Overview data...")
    print("Note: This requires DataforSEO API credentials\n")

    # Initialize client with caching and budget
    cache = DataforSEOCache()
    budget = QueryBudget(daily_limit=100)  # Conservative limit for MVP
    client = DataforSEOClient(cache=cache, budget=budget)

    results = collect_ai_overview_data(client)
    print(f"\nCollected data for {len(results)} queries\n")

    # Step 3: Analyze
    print("Step 3: Analyzing results...")
    analysis = analyze_results(results)
    print(f"Citation rate: {analysis['citation_rate']:.1%}")
    print(f"Total citations: {analysis['total_citations']}")
    print(f"Top domains: {analysis['top_domains'][:3]}\n")

    # Step 4: Visualize
    print("Step 4: Generating visualizations...")
    generate_visualizations(analysis)
    print()

    # Step 5: Save
    print("Step 5: Saving results...")
    save_results(results, analysis)

    print("\n=== Experiment complete ===")
    print(f"Results: {DATA_DIR}")
    print(f"Visualizations: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

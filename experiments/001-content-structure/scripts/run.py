"""
Experiment 001: Content Structure vs AI Overview Citations

This script runs the first experiment: testing how semantic HTML and
heading hierarchy affect citation rates in AI Overviews.

Usage:
    python -m experiments.001_content_structure.run

Environment:
    DATAFORSEO_LOGIN: DataforSEO API login
    DATAFORSEO_PASSWORD: DataforSEO API password
    DATABASE_URL: SQLite URL (default: sqlite:///data/experiments.db)
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.dataforseo import ApiCache, DataforSEOClient, DataforSEOConfig, QueryBudget
from app.dataforseo.budget import BudgetExceededError
from app.dataforseo.client import DataforSEOAPIError, DataforSEOConfigError
from app.db.schema import Database, database_from_env
from app.variants import VariantGenerator, VariantInput
from app.viz import create_chart, create_experiment_card

# Experiment configuration
EXPERIMENT_ID = "001-content-structure"
EXPERIMENT_DIR = Path(__file__).parent.parent
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
    "plain",
    "h2_structured",
    "semantic",
    "schema_enriched",
]

STRUCTURE_TYPE_MAP = {
    "plain": "plain",
    "h2_structured": "h2-structured",
    "semantic": "semantic",
    "schema_enriched": "schema-enriched",
}


def setup_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_variants() -> dict[str, Path]:
    generator = VariantGenerator()
    variants = {}

    for variant_type in VARIANT_TYPES:
        structure_type = STRUCTURE_TYPE_MAP[variant_type]
        output_path = DATA_DIR / f"{variant_type}.html"

        variant_input = VariantInput(
            experiment_id=EXPERIMENT_ID,
            query_slug="sample",
            title=f"Content Structure Experiment: {variant_type}",
            content_slots={
                "heading": "Content structure matters for AI visibility",
                "intro": "How you structure your content affects how AI Overviews interpret and cite it.",
                "body": "Semantic HTML helps AI systems understand the hierarchy and relationships between sections of content.",
                "key_points": [
                    "Use proper heading hierarchy (h1-h6)",
                    "Semantic elements convey meaning to AI",
                    "Schema.org markup adds structured context",
                ],
                "faq": [
                    {
                        "question": "Does semantic HTML really affect AI citations?",
                        "answer": "Early evidence suggests semantic structure helps AI systems better understand content relationships.",
                    }
                ],
                "how_to_steps": [
                    "Define your content hierarchy",
                    "Apply semantic HTML elements",
                    "Add structured data markup",
                ],
            },
        )

        variant = generator.render_variant(variant_input, structure_type)
        output_path.write_text(variant.html, encoding="utf-8")
        variants[variant_type] = output_path
        print(f"Generated variant: {variant_type} -> {output_path}")

    return variants


def collect_ai_overview_data(client: DataforSEOClient) -> list[dict]:
    results = []

    for query in TEST_QUERIES:
        print(f"Querying: {query}")
        try:
            response = client.query_ai_overview(keyword=query, experiment_id=EXPERIMENT_ID)
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


def _extract_citations(response) -> list[dict]:
    citations = []
    for url in response.citations:
        citations.append({"url": url, "title": None, "domain": None})
    return citations


def analyze_results(results: list[dict]) -> dict:
    total_queries = len(results)
    queries_with_citations = sum(1 for r in results if r.get("citations"))
    total_citations = sum(len(r.get("citations", [])) for r in results)

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

    key_finding = f"Citation rate: {analysis['citation_rate']:.1%} ({analysis['queries_with_citations']}/{analysis['total_queries']} queries)"
    try:
        create_experiment_card(
            experiment_id=EXPERIMENT_ID,
            title="Content Structure vs AI Overview Citations",
            key_finding=key_finding,
            output_path=OUTPUT_DIR / "social_card.png",
        )
        print(f"Generated: {OUTPUT_DIR / 'social_card.png'}")
    except RuntimeError as e:
        print(f"Skipped social card: {e}")


def save_results(results: list[dict], analysis: dict) -> None:
    with open(DATA_DIR / "results.json", "w") as f:
        json.dump(results, f, indent=2)

    with open(DATA_DIR / "analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"Saved results to {DATA_DIR / 'results.json'}")
    print(f"Saved analysis to {DATA_DIR / 'analysis.json'}")


def main() -> None:
    print(f"=== Experiment {EXPERIMENT_ID} ===")
    print("Content Structure vs AI Overview Citations\n")

    setup_directories()

    print("Step 1: Generating page variants...")
    variants = generate_variants()
    print(f"Generated {len(variants)} variants\n")

    print("Step 2: Collecting AI Overview data...")
    print("Note: This requires DataforSEO API credentials\n")

    config = DataforSEOConfig.from_env()
    database = database_from_env()
    database.initialize()

    cache = ApiCache(database)
    budget = QueryBudget(
        database,
        monthly_budget_cents=config.monthly_budget_cents,
        per_experiment_limit=config.per_experiment_limit,
    )
    client = DataforSEOClient(config, cache=cache, budget=budget)

    results = collect_ai_overview_data(client)
    print(f"\nCollected data for {len(results)} queries\n")

    print("Step 3: Analyzing results...")
    analysis = analyze_results(results)
    print(f"Citation rate: {analysis['citation_rate']:.1%}")
    print(f"Total citations: {analysis['total_citations']}")
    print(f"Top domains: {analysis['top_domains'][:3]}\n")

    print("Step 4: Generating visualizations...")
    generate_visualizations(analysis)
    print()

    print("Step 5: Saving results...")
    save_results(results, analysis)

    print("\n=== Experiment complete ===")
    print(f"Results: {DATA_DIR}")
    print(f"Visualizations: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

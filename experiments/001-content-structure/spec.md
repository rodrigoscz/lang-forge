# Content Structure vs AI Overview Citations

## Hypothesis

Semantic HTML and a clear heading hierarchy increase citation rates in AI Overviews compared with equivalent plain-text pages.

## Variables

### Controlled Variables

- Base visible text content for each query.
- Publishing domain and page template chrome.
- Query set, language, and location settings.
- Collection cadence across the two-week observation window.

### Independent Variables

- Page structure treatment:
  1. Plain HTML with minimal structure.
  2. H2/H3 heading hierarchy.
  3. Semantic HTML5 with article, section, aside, and nav elements.
  4. Semantic HTML5 plus JSON-LD schema enrichment.

### Dependent Metrics

- AI Overview citation presence per variant.
- Citation position when present.
- SERP result position for the hosted variant URL.
- Query-level citation rate by structure type.

## Metrics

- Citation rate: cited variants / queried variants per structure type.
- Relative lift: citation-rate delta versus the plain variant control.
- Stability: citation-rate variance across repeated collection runs.
- Cost: DataforSEO query spend per collection run.

## Data Sources

- Hosted Astro variant pages under `/experiments/001-content-structure/variants/{query-slug}/{structure-type}`.
- DataforSEO AI Overview and SERP responses.
- SQLite records in `data/experiments.db` linked by experiment ID, query slug, and structure type.

## Methodology

1. Select 20 informational SEO queries with stable intent.
2. Generate four page variants for each query while preserving identical visible text content.
3. Publish the static variants and expose them through the sitemap.
4. Query AI Overview and SERP data via DataforSEO on a fixed cadence for two weeks.
5. Compare citation rates by structure type and check control queries for external volatility.

## Success Criteria

- All 80 variants are generated with predictable URLs and identical visible text per query.
- Data collection stays within the configured monthly budget.
- Results identify whether semantic structure produces a measurable citation-rate lift over the plain control.
- Findings are reproducible from the stored SQLite rows and raw response snapshots.

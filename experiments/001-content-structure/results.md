# Experiment 001: Content Structure vs AI Overview Citations

## Status

🔄 **In Progress** — Scaffold complete, awaiting data collection

## Hypothesis

Semantic HTML with clear heading hierarchy increases citation rate in AI Overviews compared to plain HTML without structure.

## Methodology

### Variables

- **Independent**: HTML structure type (4 variants)
  - `plain`: No semantic structure, basic divs
  - `h2_structured`: Proper H2/H3 hierarchy
  - `semantic`: Full semantic HTML (article, section, nav, header)
  - `schema_enriched`: Semantic + Schema.org Article markup

- **Dependent**: Citation rate in AI Overviews
  - Measured as: % of queries where variant domain appears in citations
  - Secondary: position in citation list, number of citations per query

### Test Queries

5 queries targeting content structure topics:
1. "how to structure content for SEO"
2. "best practices for heading hierarchy"
3. "semantic HTML for search engines"
4. "how AI understands web content"
5. "content optimization for AI overviews"

### Data Collection

- **API**: DataforSEO SERP API (AI Overview endpoint)
- **Caching**: SQLite with 24h TTL
- **Budget**: 100 queries/day limit
- **Control**: Same queries run daily to detect AI Overview volatility

## Results

*Pending data collection*

### Expected Output

- `data/results.json`: Raw API responses
- `data/analysis.json`: Aggregated metrics
- `outputs/citations_by_domain.png`: Bar chart of citations
- `outputs/social_card.png`: Twitter-ready summary card

## Analysis

*Pending*

## Key Findings

*Pending*

## Next Steps

1. Deploy variants to test URLs (requires hosting)
2. Run data collection script: `python -m experiments.001_content_structure.run`
3. Analyze results and update this document
4. Generate Twitter thread from findings

## Technical Notes

### Running the Experiment

```bash
# Set API credentials
export DATAFORSEO_LOGIN="your_login"
export DATAFORSEO_PASSWORD="your_password"

# Run experiment
cd /Users/novasanchez/lang-forge
python -m experiments.001_content_structure.run
```

### Skipping Social Card Generation

On low-RAM machines (<16GB), skip html2image:

```bash
export SKIP_HTML2IMAGE=1
python -m experiments.001_content_structure.run
```

### Mermaid Diagrams

To render architecture diagrams:

```bash
npm install -g @mermaid-js/mermaid-cli
mmdc -i diagram.mmd -o diagram.png
```

## References

- [Google AI Overviews Documentation](https://developers.google.com/search/docs/appearance/ai-features)
- [DataforSEO SERP API](https://docs.dataforseo.com/v3/serp/)
- Spec: `openspec/changes/ai-seo-lab/specs/content-variant-generator/spec.md`

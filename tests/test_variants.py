from __future__ import annotations

import json
import re

import pytest

from app.variants.generator import StructureType, VariantGenerator, VariantInput, visible_text


@pytest.fixture()
def variant_input() -> VariantInput:
    return VariantInput(
        experiment_id="001-content-structure",
        query_slug="best-running-shoes",
        title="Best running shoes for marathon training",
        content_slots={
            "heading": "Choose shoes by fit, rotation, and training load",
            "intro": "Marathon shoes should support long runs without changing form.",
            "body": "The safest choice balances cushioning, stability, durability, and comfort across weekly mileage.",
            "key_points": [
                "Use long-run comfort as the primary filter.",
                "Rotate shoes to reduce repetitive stress.",
                "Replace pairs when cushioning feels compressed.",
            ],
            "faq": [
                {
                    "question": "Do carbon shoes help every runner?",
                    "answer": "Carbon shoes can help race-day efficiency but are not required for daily mileage.",
                }
            ],
            "how_to_steps": [
                "Measure current weekly mileage.",
                "Test fit after a warm-up walk.",
                "Compare comfort after an easy run.",
            ],
        },
    )


def test_all_structure_types_preserve_identical_visible_text(variant_input: VariantInput) -> None:
    variants = VariantGenerator().generate_variants(variant_input)

    assert len(variants) == 4
    assert {variant.structure_type for variant in variants} == set(StructureType)
    assert len({visible_text(variant.html) for variant in variants}) == 1


def test_generator_supports_full_80_page_experiment_batch(variant_input: VariantInput) -> None:
    inputs = [
        variant_input.model_copy(update={"query_slug": f"query-{index:02d}", "title": f"Query {index:02d}"})
        for index in range(1, 21)
    ]

    result = VariantGenerator().generate_many(inputs)

    assert result.skipped == {}
    assert len(result.variants) == 80
    assert len({variant.url for variant in result.variants}) == 80


@pytest.mark.parametrize("structure_type", list(StructureType))
def test_structure_specific_elements(variant_input: VariantInput, structure_type: StructureType) -> None:
    variant = VariantGenerator().render_variant(variant_input, structure_type)

    if structure_type is StructureType.PLAIN:
        assert "<article" not in variant.html
        assert "<section" not in variant.html
        assert "<aside" not in variant.html
        assert "<nav" not in variant.html
        assert "application/ld+json" not in variant.html

    if structure_type is StructureType.H2_STRUCTURED:
        assert "<h2" in variant.html
        assert "<h3" in variant.html
        assert "<article" not in variant.html
        assert "<section" not in variant.html
        assert "application/ld+json" not in variant.html

    if structure_type is StructureType.SEMANTIC:
        assert "<article" in variant.html
        assert "<section" in variant.html
        assert "<aside" in variant.html
        assert "<nav" in variant.html
        assert "application/ld+json" not in variant.html

    if structure_type is StructureType.SCHEMA_ENRICHED:
        assert "<article" in variant.html
        assert "<section" in variant.html
        assert "application/ld+json" in variant.html
        script = re.search(r'<script type="application/ld\+json">(.*?)</script>', variant.html, re.S)
        assert script is not None
        schema = json.loads(script.group(1))
        schema_types = {entry["@type"] for entry in schema["@graph"]}
        assert {"Article", "FAQPage", "HowTo"}.issubset(schema_types)


def test_json_ld_prevents_script_injection() -> None:
    xss_payload = '</script><script>alert(1)</script>'
    variant_input = VariantInput(
        experiment_id="001-xss",
        query_slug="xss-test",
        title=f"Test {xss_payload}",
        content_slots={
            "heading": f"XSS {xss_payload}",
            "intro": f"Test {xss_payload}",
            "body": "Safe body",
            "key_points": ["Safe point"],
            "faq": [{"question": f"Q {xss_payload}", "answer": f"A {xss_payload}"}],
            "how_to_steps": [f"Step {xss_payload}"],
        },
    )
    variant = VariantGenerator().render_variant(variant_input, StructureType.SCHEMA_ENRICHED)

    script_tag = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        variant.html,
        re.S,
    )
    assert script_tag is not None
    raw_json = script_tag.group(1)

    assert '</script>' not in raw_json
    assert '<\\/script>' in raw_json

    unescaped = raw_json.replace('<\\/', '</')
    parsed = json.loads(unescaped)
    assert parsed["@context"] == "https://schema.org"


def test_missing_required_slots_are_reported() -> None:
    with pytest.raises(ValueError, match="how_to_steps"):
        VariantInput(
            experiment_id="001-content-structure",
            query_slug="missing-slots",
            title="Missing slots",
            content_slots={
                "heading": "A heading",
                "intro": "An intro",
                "body": "A body",
                "key_points": ["One point"],
                "faq": [{"question": "Question?", "answer": "Answer."}],
            },
        )

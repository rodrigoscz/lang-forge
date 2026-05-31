from __future__ import annotations

import json
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from pydantic import BaseModel, Field, field_validator


class StructureType(StrEnum):
    PLAIN = "plain"
    H2_STRUCTURED = "h2-structured"
    SEMANTIC = "semantic"
    SCHEMA_ENRICHED = "schema-enriched"


TEMPLATE_BY_STRUCTURE = {
    StructureType.PLAIN: "plain.html",
    StructureType.H2_STRUCTURED: "h2_structured.html",
    StructureType.SEMANTIC: "semantic.html",
    StructureType.SCHEMA_ENRICHED: "schema_enriched.html",
}


class FAQItem(BaseModel):
    question: str
    answer: str


class ContentSlots(BaseModel):
    heading: str
    intro: str
    body: str
    key_points: list[str] = Field(min_length=1)
    faq: list[FAQItem] = Field(min_length=1)
    how_to_steps: list[str] = Field(min_length=1)

    @field_validator("heading", "intro", "body")
    @classmethod
    def require_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("slot must not be empty")
        return value


class VariantInput(BaseModel):
    experiment_id: str
    query_slug: str
    title: str
    content_slots: ContentSlots


class VariantOutput(BaseModel):
    id: str
    url: str
    html: str
    structure_type: StructureType


class VariantBatchResult(BaseModel):
    variants: list[VariantOutput]
    skipped: dict[str, str]


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text and not self._skip_depth:
            self.parts.append(text)


def visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


class VariantGenerator:
    def __init__(self, template_dir: Path | str | None = None) -> None:
        templates_path = Path(template_dir) if template_dir else Path(__file__).with_name("templates")
        self.environment = Environment(
            loader=FileSystemLoader(templates_path),
            autoescape=select_autoescape(enabled_extensions=("html",)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_variant(self, variant_input: VariantInput, structure_type: StructureType) -> VariantOutput:
        template = self.environment.get_template(TEMPLATE_BY_STRUCTURE[structure_type])
        url = self._variant_url(variant_input, structure_type)
        html = template.render(
            title=variant_input.title,
            query_slug=variant_input.query_slug,
            slots=variant_input.content_slots,
            url=url,
            schema_json=self._schema_json(variant_input, url),
        )
        return VariantOutput(
            id=f"{variant_input.experiment_id}:{variant_input.query_slug}:{structure_type.value}",
            url=url,
            html=html.strip(),
            structure_type=structure_type,
        )

    def generate_variants(self, variant_input: VariantInput) -> list[VariantOutput]:
        variants = [self.render_variant(variant_input, structure_type) for structure_type in StructureType]
        self._validate_visible_content(variants)
        return variants

    def generate_many(self, variant_inputs: list[VariantInput]) -> VariantBatchResult:
        variants: list[VariantOutput] = []
        skipped: dict[str, str] = {}
        for variant_input in variant_inputs:
            try:
                variants.extend(self.generate_variants(variant_input))
            except ValueError as error:
                skipped[variant_input.query_slug] = str(error)
        return VariantBatchResult(variants=variants, skipped=skipped)

    @staticmethod
    def _variant_url(variant_input: VariantInput, structure_type: StructureType) -> str:
        return f"/experiments/{variant_input.experiment_id}/variants/{variant_input.query_slug}/{structure_type.value}"

    @staticmethod
    def _validate_visible_content(variants: list[VariantOutput]) -> None:
        normalized = {variant.structure_type.value: visible_text(variant.html) for variant in variants}
        if len(set(normalized.values())) != 1:
            raise ValueError(f"Visible text differs across variants: {normalized}")

    @staticmethod
    def _schema_json(variant_input: VariantInput, url: str) -> str:
        slots = variant_input.content_slots
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Article",
                    "headline": variant_input.title,
                    "description": slots.intro,
                    "url": url,
                },
                {
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": item.question,
                            "acceptedAnswer": {"@type": "Answer", "text": item.answer},
                        }
                        for item in slots.faq
                    ],
                },
                {
                    "@type": "HowTo",
                    "name": slots.heading,
                    "step": [
                        {"@type": "HowToStep", "position": index, "text": step}
                        for index, step in enumerate(slots.how_to_steps, start=1)
                    ],
                },
            ],
        }
        return json.dumps(schema, ensure_ascii=False)

import type { QueryContent, StructureType } from '../data/experiments';

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function list(items: string[], ordered = false): string {
  const tag = ordered ? 'ol' : 'ul';
  return `<${tag}>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</${tag}>`;
}

function faq(query: QueryContent): string {
  return query.faq.map((item) => `<p>${escapeHtml(item.question)}</p><p>${escapeHtml(item.answer)}</p>`).join('');
}

function schemaJson(experimentId: string, query: QueryContent, structureType: StructureType): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Article',
        headline: query.title,
        description: query.intro,
        url: `/experiments/${experimentId}/variants/${query.slug}/${structureType}`,
      },
      {
        '@type': 'FAQPage',
        mainEntity: query.faq.map((item) => ({
          '@type': 'Question',
          name: item.question,
          acceptedAnswer: { '@type': 'Answer', text: item.answer },
        })),
      },
      {
        '@type': 'HowTo',
        name: query.heading,
        step: query.howToSteps.map((step, index) => ({ '@type': 'HowToStep', position: index + 1, text: step })),
      },
    ],
  });
}

export function renderVariantHtml(experimentId: string, query: QueryContent, structureType: StructureType): string {
  const keyPoints = list(query.keyPoints);
  const steps = list(query.howToSteps, true);

  if (structureType === 'plain') {
    return `<div class="variant variant-plain"><p>${escapeHtml(query.title)}</p><p>${escapeHtml(query.heading)}</p><p>${escapeHtml(query.intro)}</p><p>Analysis</p><p>${escapeHtml(query.body)}</p><p>Key points</p>${keyPoints}<p>Questions</p>${faq(query)}<p>Process</p>${steps}</div>`;
  }

  if (structureType === 'h2-structured') {
    return `<div class="variant variant-h2-structured"><h1>${escapeHtml(query.title)}</h1><h2>${escapeHtml(query.heading)}</h2><p>${escapeHtml(query.intro)}</p><h3>Analysis</h3><p>${escapeHtml(query.body)}</p><h3>Key points</h3>${keyPoints}<h3>Questions</h3>${faq(query)}<h3>Process</h3>${steps}</div>`;
  }

  const semanticHtml = `<article class="variant variant-${structureType}"><nav aria-label="Variant context"></nav><header><h1>${escapeHtml(query.title)}</h1></header><section><h2>${escapeHtml(query.heading)}</h2><p>${escapeHtml(query.intro)}</p></section><section><h3>Analysis</h3><p>${escapeHtml(query.body)}</p></section><section><h3>Key points</h3>${keyPoints}</section><section><h3>Questions</h3>${faq(query)}</section><section><h3>Process</h3>${steps}</section><aside aria-label="Experiment metadata"></aside>`;

  if (structureType === 'schema-enriched') {
    return `${semanticHtml}<script type="application/ld+json">${schemaJson(experimentId, query, structureType)}</script></article>`;
  }

  return `${semanticHtml}</article>`;
}

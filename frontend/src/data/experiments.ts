export const structureTypes = ['plain', 'h2-structured', 'semantic', 'schema-enriched'] as const;

export type StructureType = (typeof structureTypes)[number];

export type QueryContent = {
  slug: string;
  title: string;
  heading: string;
  intro: string;
  body: string;
  keyPoints: string[];
  faq: { question: string; answer: string }[];
  howToSteps: string[];
};

export type Experiment = {
  id: string;
  title: string;
  summary: string;
  hypothesis: string;
  status: 'draft' | 'ready' | 'running' | 'completed' | 'archived';
  queries: QueryContent[];
};

const querySeeds = [
  ['best-running-shoes', 'Best running shoes'],
  ['marathon-training-plan', 'Marathon training plan'],
  ['trail-running-gear', 'Trail running gear'],
  ['beginner-yoga-routine', 'Beginner yoga routine'],
  ['plant-based-protein', 'Plant-based protein'],
  ['home-office-ergonomics', 'Home office ergonomics'],
  ['email-marketing-strategy', 'Email marketing strategy'],
  ['local-seo-checklist', 'Local SEO checklist'],
  ['content-audit-process', 'Content audit process'],
  ['technical-seo-basics', 'Technical SEO basics'],
  ['coffee-brewing-methods', 'Coffee brewing methods'],
  ['sourdough-starter-care', 'Sourdough starter care'],
  ['budget-travel-europe', 'Budget travel Europe'],
  ['remote-team-rituals', 'Remote team rituals'],
  ['notion-project-management', 'Notion project management'],
  ['cybersecurity-for-small-business', 'Cybersecurity for small business'],
  ['solar-panel-maintenance', 'Solar panel maintenance'],
  ['electric-bike-commuting', 'Electric bike commuting'],
  ['language-learning-habits', 'Language learning habits'],
  ['ai-overview-optimization', 'AI Overview optimization'],
] as const;

function buildQuery([slug, title]: readonly [string, string]): QueryContent {
  return {
    slug,
    title,
    heading: `${title} should be evaluated with a clear decision framework`,
    intro: `${title} research works best when advice is specific, verifiable, and easy to compare.`,
    body: `A useful ${title.toLowerCase()} answer explains the context, defines the main tradeoffs, and gives practical next steps without changing the underlying recommendation.`,
    keyPoints: [
      'Start with the user goal before choosing a tactic.',
      'Compare options with measurable criteria.',
      'Document assumptions so the answer remains auditable.',
    ],
    faq: [
      {
        question: `What matters most for ${title.toLowerCase()}?`,
        answer: 'The strongest answer matches intent, explains tradeoffs, and gives a repeatable decision path.',
      },
    ],
    howToSteps: [
      'Define the search intent.',
      'Identify the criteria that change the recommendation.',
      'Select the option that best matches those criteria.',
    ],
  };
}

export const experiments: Experiment[] = [
  {
    id: '001-content-structure',
    title: 'Content Structure vs AI Overview Citations',
    summary: 'Tests whether semantic HTML and heading hierarchy affect AI Overview citation rates.',
    hypothesis: 'Semantic HTML plus clear heading hierarchy increases citation rate in AI Overviews.',
    status: 'draft',
    queries: querySeeds.map(buildQuery),
  },
];

export function getExperiment(id: string): Experiment | undefined {
  return experiments.find((experiment) => experiment.id === id);
}

export function getVariantPaths() {
  return experiments.flatMap((experiment) =>
    experiment.queries.flatMap((query) =>
      structureTypes.map((structureType) => ({
        params: { id: experiment.id, slug: `${query.slug}/${structureType}` },
        props: { experiment, query, structureType },
      })),
    ),
  );
}

export function variantUrl(experimentId: string, querySlug: string, structureType: StructureType): string {
  return `/experiments/${experimentId}/variants/${querySlug}/${structureType}`;
}

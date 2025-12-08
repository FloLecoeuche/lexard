"""Bilingual prompts for the agent system.

Provides prompts in both English and French for all agent operations.
Uses language detection to select appropriate prompts automatically.
"""

# System prompts for different agent intents
SYSTEM_PROMPTS = {
    "en": """You are a legal contract analysis assistant.
Answer questions accurately using only the provided context.
If the answer is not in the context, say "I cannot find this information in the document".""",
    "fr": """Vous êtes un assistant d'analyse de contrats juridiques.
Répondez aux questions de manière précise en utilisant uniquement le contexte fourni.
Si la réponse n'est pas dans le contexte, dites "Je ne peux pas trouver cette information dans le document".""",
}

# Query/question answering prompts
QUERY_TEMPLATES = {
    "en": """Context: {context}

Question: {question}

Answer based only on the context above. Include specific citations.""",
    "fr": """Contexte: {context}

Question: {question}

Répondez uniquement en vous basant sur le contexte ci-dessus. Incluez des citations spécifiques.""",
}

# Document summarization prompts
# IMPORTANT: Response language follows DOCUMENT language, not query language
CHUNK_SUMMARY_PROMPTS = {
    "en": """Summarize the following document excerpt in 2-3 sentences.
Focus on key facts, obligations, and important details.
IMPORTANT: You MUST respond in English.

EXCERPT:
{content}

SUMMARY:""",
    "fr": """Résumez l'extrait de document suivant en 2-3 phrases.
Concentrez-vous sur les faits clés, les obligations et les détails importants.
IMPORTANT: Vous DEVEZ répondre en français.

EXTRAIT:
{content}

RÉSUMÉ:""",
}

AGGREGATION_PROMPTS = {
    "en": """Based on these section summaries, create a cohesive document summary.
IMPORTANT: You MUST respond in English regardless of the source language.

SECTION SUMMARIES:
{summaries}

Create:
1. An executive summary (2-3 paragraphs)
2. A bullet list of 5-7 key points

FORMAT:
## Executive Summary
[Your summary here]

## Key Points
- Point 1
- Point 2
...""",
    "fr": """Basé sur ces résumés de sections, créez un résumé cohérent du document.
IMPORTANT: Vous DEVEZ répondre en français quelle que soit la langue source.

RÉSUMÉS DES SECTIONS:
{summaries}

Créez:
1. Un résumé exécutif (2-3 paragraphes)
2. Une liste à puces de 5-7 points clés

FORMAT:
## Résumé Exécutif
[Votre résumé ici]

## Points Clés
- Point 1
- Point 2
...""",
}

# Risk analysis prompts
# IMPORTANT: Response language follows DOCUMENT language, not query language
RISK_ANALYSIS_PROMPTS = {
    "en": """Analyze the following contract excerpt for potential risks.
IMPORTANT: You MUST respond in English.

EXCERPT:
{content}

Identify:
1. Financial risks (penalties, unlimited liability, payment terms)
2. Legal risks (termination clauses, dispute resolution, governing law)
3. Operational risks (SLA obligations, compliance requirements)

For each risk, provide:
- Type: financial | legal | operational
- Severity: low | medium | high
- Description: Brief explanation

FORMAT:
- [Type] [Severity]: Description""",
    "fr": """Analysez l'extrait de contrat suivant pour identifier les risques potentiels.
IMPORTANT: Vous DEVEZ répondre en français.

EXTRAIT:
{content}

Identifiez:
1. Risques financiers (pénalités, responsabilité illimitée, conditions de paiement)
2. Risques juridiques (clauses de résiliation, résolution des litiges, droit applicable)
3. Risques opérationnels (obligations SLA, exigences de conformité)

Pour chaque risque, fournissez:
- Type: financial | legal | operational
- Gravité: low | medium | high
- Description: Brève explication

FORMAT:
- [Type] [Gravité]: Description""",
}

# Document comparison prompts
# IMPORTANT: Response language follows DOCUMENT language, not query language
DIFF_PROMPTS = {
    "en": """Compare these two contract excerpts and identify key differences.
IMPORTANT: You MUST respond in English.

DOCUMENT A:
{doc_a}

DOCUMENT B:
{doc_b}

Identify differences in:
1. Terms and conditions
2. Financial obligations
3. Timelines and deadlines
4. Rights and responsibilities

For each difference, specify which document contains what.""",
    "fr": """Comparez ces deux extraits de contrat et identifiez les différences clés.
IMPORTANT: Vous DEVEZ répondre en français.

DOCUMENT A:
{doc_a}

DOCUMENT B:
{doc_b}

Identifiez les différences dans:
1. Termes et conditions
2. Obligations financières
3. Délais et échéances
4. Droits et responsabilités

Pour chaque différence, précisez quel document contient quoi.""",
}


def get_prompt(prompt_type: str, language: str = "en", **kwargs) -> str:
    """Get a prompt in the specified language.

    Args:
        prompt_type: Type of prompt (system, query, chunk_summary, aggregation, risk_analysis, diff)
        language: Language code ('en' or 'fr')
        **kwargs: Template variables to format into the prompt

    Returns:
        Formatted prompt string in the requested language

    Raises:
        ValueError: If prompt_type is invalid

    Examples:
        >>> get_prompt("system", "en")
        'You are a legal contract analysis assistant...'
        >>> get_prompt("query", "fr", context="...", question="...")
        'Contexte: ...'
    """
    prompts_map = {
        "system": SYSTEM_PROMPTS,
        "query": QUERY_TEMPLATES,
        "chunk_summary": CHUNK_SUMMARY_PROMPTS,
        "aggregation": AGGREGATION_PROMPTS,
        "risk_analysis": RISK_ANALYSIS_PROMPTS,
        "diff": DIFF_PROMPTS,
    }

    if prompt_type not in prompts_map:
        raise ValueError(
            f"Invalid prompt_type: {prompt_type}. "
            f"Must be one of: {', '.join(prompts_map.keys())}"
        )

    prompts = prompts_map[prompt_type]

    # Default to English if language not supported
    template = prompts.get(language, prompts["en"])

    # Format template if kwargs provided
    return template.format(**kwargs) if kwargs else template

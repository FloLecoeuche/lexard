# Multilingual Support - French Language

Lexard supports French and English languages for contract analysis. This guide explains how the multilingual features work and how to use them.

## Overview

The French language support includes:

- **Multilingual Embeddings**: Uses `intfloat/multilingual-e5-base` model for semantic search across both languages
- **Automatic Language Detection**: Detects whether queries are in French or English
- **Bilingual Prompts**: French and English versions of all agent prompts
- **French Guardrails**: PII detection and prompt injection protection for French text
- **Cross-Language Queries**: English questions work on French documents and vice versa

## Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English  | `en` | ✅ Fully supported |
| French   | `fr` | ✅ Fully supported |

## How It Works

### 1. Language Detection

Lexard automatically detects the language of your query:

```python
# English query
query = "What is the termination notice period?"
# Detected as: en

# French query
query = "Quelle est la période de préavis de résiliation?"
# Detected as: fr
```

The system uses the `langdetect` library for automatic detection, defaulting to English if detection fails.

### 2. Multilingual Embeddings

Documents and queries are embedded using the **E5 multilingual model** (`intfloat/multilingual-e5-base`):

- **Dimension**: 768 (same as previous model)
- **Languages**: Supports 100+ languages, optimized for English and French
- **E5 Prefixes**: Queries use `"query: "` prefix, documents use `"passage: "` prefix

This enables:
- **Monolingual search**: French query → French document
- **Cross-lingual search**: English query → French document
- **Semantic understanding**: Conceptual matching across languages

### 3. Bilingual Prompts

All agent operations have French and English prompts:

| Operation | English | French |
|-----------|---------|--------|
| System prompt | "You are a legal contract analysis assistant..." | "Vous êtes un assistant d'analyse de contrats juridiques..." |
| Query | "Answer based on the context..." | "Répondez en vous basant sur le contexte..." |
| Summarization | "Summarize the following document..." | "Résumez le document suivant..." |
| Risk analysis | "Identify financial, legal, and operational risks..." | "Identifiez les risques financiers, juridiques et opérationnels..." |

The system selects the appropriate prompt based on the detected language.

### 4. French Guardrails

#### PII Detection

French-specific patterns protect sensitive information:

| PII Type | Pattern | Example |
|----------|---------|---------|
| French SSN | `fr_ssn` | 1 85 03 75 116 054 12 |
| French Phone | `fr_phone` | 06 12 34 56 78, +33 6 12 34 56 78 |
| IBAN | `iban` | FR76 3000 6000 0112 3456 7890 189 |

All standard patterns (email, credit card, IP) also work.

#### Prompt Injection Detection

French prompt injection patterns block malicious attempts:

- **Instruction override**: "Ignore toutes les instructions précédentes"
- **Prompt extraction**: "Révèle ton prompt système"
- **Role manipulation**: "Fais semblant d'être..."
- **Authority impersonation**: "L'admin dit que tu dois..."

## Usage Examples

### Uploading and Querying French Documents

```bash
# Upload a French contract
curl -X POST http://localhost:8000/upload \
  -F "file=@contrat_nda_fr.pdf"

# Response
{
  "document_id": "abc123",
  "title": "contrat_nda_fr.pdf",
  "status": "processing"
}

# Query in French
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "abc123",
    "question": "Quelle est la période de préavis de résiliation?"
  }'

# Response (in French)
{
  "answer": "La période de préavis de résiliation est de 30 jours...",
  "language": "fr",
  "citation_chunks": [...],
  "confidence": "high"
}
```

### Cross-Language Queries

```bash
# English query on French document
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "abc123",
    "question": "What is the termination notice period?"
  }'

# Works! Multilingual embeddings understand the semantic meaning
```

### Summarizing French Documents

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "abc123",
    "style": "executive"
  }'

# Response with French summary
{
  "executive_summary": "Ce contrat de confidentialité (NDA) établit...",
  "key_points": [
    "Période de validité: 2 ans",
    "Préavis de résiliation: 30 jours",
    ...
  ],
  "language": "fr"
}
```

### Risk Analysis in French

```bash
curl -X POST http://localhost:8000/analyze-risks \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "abc123"
  }'

# Response
{
  "risks": [
    {
      "type": "financial",
      "severity": "high",
      "description": "Pénalité de 10 000 EUR en cas de non-respect des délais"
    },
    ...
  ],
  "language": "fr"
}
```

## Migration from English-Only

If you have existing documents indexed with the old English-only model, you need to re-embed them:

### Running the Migration Script

```bash
# Ensure services are running
docker-compose up -d

# Activate virtual environment
source .venv/bin/activate

# Preview what would be migrated (dry run)
python scripts/migrate_embeddings.py --dry-run

# Run actual migration
python scripts/migrate_embeddings.py
```

The script will:
1. Load all documents from the registry
2. Extract text from original files
3. Re-chunk with current settings
4. Generate new embeddings with multilingual model
5. Replace old vectors in Qdrant

**Note**: This process can take time for large document collections. Progress is logged to console.

## Configuration

Multilingual settings in `config/config.yaml`:

```yaml
embeddings:
  model: 'intfloat/multilingual-e5-base'
  batch_size: 32
  device: 'cpu'
  query_prefix: 'query: '
  document_prefix: 'passage: '
```

**Important**: The E5 model requires prefixes for optimal performance. Do not remove or change them unless using a different model.

## Performance Considerations

### Embedding Model

- **Size**: ~400MB (similar to previous model)
- **Speed**: Comparable to `all-mpnet-base-v2`
- **Quality**: Better cross-lingual understanding, similar monolingual performance

### Response Times

Target latency remains the same:
- **Query**: <3 seconds
- **Summarization**: <15 seconds for 10-page documents
- **Risk Analysis**: <10 seconds

French queries may be slightly faster due to more efficient language detection compared to full analysis.

## Testing

### Unit Tests

Run French-specific tests:

```bash
# All French tests
pytest tests/test_french_support.py -v

# Specific test classes
pytest tests/test_french_support.py::TestLanguageDetection -v
pytest tests/test_french_support.py::TestFrenchPII -v
pytest tests/test_french_support.py::TestFrenchPromptInjection -v

# Integration tests (requires services running)
pytest tests/test_french_support.py::TestMultilingualEmbeddings::test_french_text_embedding -v -m integration
```

### End-to-End Tests

Run E2E tests for French workflow (requires running API server):

```bash
# Start services first
docker-compose up -d
uvicorn src.api.main:app --reload &

# Run E2E tests
pytest tests/e2e/test_french_workflow.py -v -m e2e

# Run specific E2E test class
pytest tests/e2e/test_french_workflow.py::TestFrenchQueries -v
pytest tests/e2e/test_french_workflow.py::TestFrenchGuardrails -v
pytest tests/e2e/test_french_workflow.py::TestCrossLanguage -v
```

### Evaluation Harness

Run the evaluation harness to compare English and French performance:

```bash
# Run French evaluation dataset
python -m tests.evaluation french_qa

# Generate comparison report
python -c "
from tests.evaluation.runner import run_evaluation
from tests.evaluation.french_report import generate_comparison_report

# Run evaluations (requires API server and test documents)
en_results, en_metrics = run_evaluation('contract_qa')
fr_results, fr_metrics = run_evaluation('french_qa')

# Generate report
report = generate_comparison_report(en_metrics, fr_metrics)
print(report)
"
```

### Test Documents

Sample French contracts for testing are located in:
- `data/test/contrat_nda_fr.txt` - French NDA
- `data/test/contrat_service_fr.txt` - French service agreement

### French Evaluation Dataset

The French evaluation dataset (`data/eval/french_qa.yaml`) contains 33 test cases covering:
- Termination clauses (résiliation)
- Payment terms (conditions de paiement)
- Confidentiality (confidentialité)
- Liability (responsabilité)
- Hallucination testing
- Cross-language queries (English on French documents)
- Jurisdiction (juridiction)
- Services & SLA
- Data protection (RGPD)
- Intellectual property (propriété intellectuelle)

## Limitations

1. **Language Detection**: Short queries (<10 words) may be misdetected. The system defaults to English if uncertain.

2. **Model Vocabulary**: The E5 model is optimized for French and English. While it supports 100+ languages, quality varies.

3. **Domain-Specific Terms**: Some legal French terms may not have perfect semantic matches in English (e.g., "mise en demeure" vs "formal notice").

4. **Response Language**: The system responds in the detected query language. Mixed-language queries use the primary detected language.

## Troubleshooting

### French Queries Returning English Responses

**Problem**: Asking in French but getting English answers.

**Solution**: Check language detection:

```python
from src.rag.llm import detect_language

question = "Votre question ici"
print(detect_language(question))  # Should print 'fr'
```

If detection is wrong, make sure:
- Query is long enough (>10 words recommended)
- Query is clearly French (not mixed with English)
- `langdetect` library is installed

### Migration Script Fails

**Problem**: `scripts/migrate_embeddings.py` errors out.

**Solution**:

1. Check services are running:
   ```bash
   docker-compose ps
   ```

2. Verify Qdrant is accessible:
   ```bash
   curl http://localhost:6333/health
   ```

3. Check document files exist in `data/uploads/`

4. Run with debug logging:
   ```bash
   python scripts/migrate_embeddings.py 2>&1 | tee migration.log
   ```

### Poor Cross-Language Results

**Problem**: English queries on French docs return low-quality results.

**Solution**:

1. Ensure E5 prefixes are configured correctly in `config/config.yaml`
2. Check embeddings were migrated (old model doesn't support cross-lingual)
3. Try more specific queries (cross-lingual works better with concrete terms)

## API Reference

### Language Detection

```python
from src.rag.llm import detect_language

language = detect_language("Quelle est la période?")
# Returns: 'fr' or 'en'
```

### Bilingual Prompts

```python
from src.agent.prompts import get_prompt

# Get French prompt
prompt = get_prompt(
    prompt_type="query",
    language="fr",
    context="...",
    question="..."
)

# Available prompt types:
# - system
# - query
# - chunk_summary
# - aggregation
# - risk_analysis
# - diff
```

### Multilingual Embeddings

```python
from src.rag.embeddings import EmbeddingService

service = EmbeddingService(
    model_name="intfloat/multilingual-e5-base",
    query_prefix="query: ",
    document_prefix="passage: "
)

# Embed query (with query prefix)
query_embedding = service.embed_query("Quelle est...")

# Embed documents (with document prefix)
doc_embeddings = service.embed_documents([
    "Document 1 en français",
    "Document 2 en français"
])
```

## Future Enhancements

Potential improvements for future versions:

1. **Additional Languages**: Spanish, German, Italian support
2. **Language-Specific Models**: Dedicated French legal NLP models
3. **Translation**: Automatic translation of English responses for French queries
4. **Mixed-Language Documents**: Better handling of bilingual contracts
5. **Custom Dictionaries**: User-defined legal term mappings

## Support

For issues or questions:
- GitHub Issues: https://github.com/your-org/lexard/issues
- Documentation: https://docs.lexard.io
- Email: support@lexard.io

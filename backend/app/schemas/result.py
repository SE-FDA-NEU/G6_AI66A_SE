"""Version 1 analysis/persistence contract shared by future analyzer adapters.

Offsets are half-open Unicode code points in the exact persisted page text.
Reader versions pin evidence to the PDF displayed by /documents/{id}/reader.pdf.
A table output is one contract row; result_data.documents supplies the batch.
Missing table fields are null/unverified, never inferred from absent evidence.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Evidence(Payload):
    document_id: int = Field(gt=0, strict=True)
    page: int = Field(gt=0, strict=True)
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    quote: str = Field(min_length=1)
    reader_version: str = Field(pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def valid_span(self):
        if self.end <= self.start or self.end - self.start != len(self.quote):
            raise ValueError('Evidence must use exact half-open source offsets.')
        return self


class Claim(Payload):
    """Shared by bullets/actions, table cells and concept descriptions.

    kind is descriptive, never a bypass for source/numeric validation. Evidence
    contains only server-validated passages; rejected references are removed.
    unverified and verification_issues describe claim-level support, not truth.
    Multiple passages/documents stay separate, even when their text is equal.
    """
    text: str | None = Field(default=None, min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    unverified: bool = True
    kind: Literal['general', 'amount', 'date', 'percentage', 'clause'] = 'general'
    verification_issues: list[Literal['missing_evidence', 'invalid_evidence',
                                     'unsupported_fact', 'model_uncertain']] = Field(default_factory=list)


class BulletOutput(Payload):
    type: Literal['bullet'] = 'bullet'
    bullets: list[Claim] = Field(default_factory=list)
    actions: list[Claim] = Field(default_factory=list)


class TableOutput(Payload):
    type: Literal['table'] = 'table'
    value: Claim = Field(default_factory=Claim)
    payment_term: Claim = Field(default_factory=Claim)
    penalty: Claim = Field(default_factory=Claim)


class Concept(Payload):
    name: str = Field(min_length=1)
    description: Claim


class ConceptOutput(Payload):
    type: Literal['concept'] = 'concept'
    concepts: list[Concept] = Field(default_factory=list, max_length=5)
    limitation: str | None = None


Output = Annotated[BulletOutput | TableOutput | ConceptOutput, Field(discriminator='type')]


class LabelSuggestion(Payload):
    ai_label: str | None = Field(default=None, min_length=1, max_length=100)
    ai_confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode='after')
    def paired_values(self):
        if (self.ai_label is None) != (self.ai_confidence is None):
            raise ValueError('A label suggestion requires both label and confidence.')
        return self


class AnalysisMetadata(Payload):
    provider: Literal['gemini'] = 'gemini'
    model: str
    prompt_version: str
    cache_hit: bool = False
    input_truncated: bool = False
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AnalysisResult(Payload):
    """Return value of an async analyzer(document_input, mode) adapter.

    Source matching establishes a valid citation, not semantic entailment.
    Adapters must keep unverified=True for claims they cannot substantiate.
    """
    analysis_status: Literal['completed', 'not_configured'] = 'completed'
    output: Output
    label: LabelSuggestion = Field(default_factory=LabelSuggestion)
    warnings: list[str] = Field(default_factory=list)
    analysis_metadata: AnalysisMetadata | None = None


class LabelMetadata(LabelSuggestion):
    review_state: Literal['confirmed', 'needs_review']
    confidence_level: Literal['unknown', 'low', 'high']
    user_label: str | None = None


class ReaderMetadata(Payload):
    version: str = Field(pattern=r'^[0-9a-f]{64}$')
    page_count: int = Field(gt=0)
    page_kind: Literal['page', 'slide']
    url: str


class DocumentResult(Payload):
    schema_version: Literal[1] = 1
    document_id: int
    original_filename: str
    mode: Literal['bullet', 'table', 'concept']
    analysis_status: Literal['completed', 'not_configured']
    reader: ReaderMetadata
    label: LabelMetadata
    output: Output
    warnings: list[str] = Field(default_factory=list)
    analysis_metadata: AnalysisMetadata | None = None


class JobResultData(Payload):
    schema_version: Literal[1] = 1
    documents: dict[str, DocumentResult]

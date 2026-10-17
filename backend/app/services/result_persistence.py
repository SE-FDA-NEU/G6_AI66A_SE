"""Validate analyzer output against reader pages and save existing models."""
from contextlib import contextmanager

from app.models import Citation, Document, ReviewState
from app.schemas.result import DocumentResult, LabelMetadata, ReaderMetadata
from app.services.evidence import EvidenceValidator, claim_contexts, claims, parse_analysis
from app.services.reader_extraction import ReaderConversionError, publish_pdf, reader_file, sha256


class InvalidAnalysisResult(ValueError):
    pass


@contextmanager
def publish_reader(document, prepared):
    """A DB rollback removes only an artifact newly published by this attempt."""
    reference = prepared.data['extracted_text'][0]['reader']
    if sha256(document.storage_path) != reference['source_sha256']:
        raise ReaderConversionError('source_changed', 'The source changed during processing. Please retry.')
    target = reader_file(document, reference)
    created = False
    if prepared.rendered != target:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256(target) != reference['sha256']:
            created = not target.exists()
            publish_pdf(prepared.rendered, target)
    try:
        yield
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise


def save_analysis(db, job, document, prepared, raw_result):
    """Stage JSON, native pages, labels and citations in the caller's transaction."""
    if document.owner_id != job.owner_id or document.id not in {link.document_id for link in job.job_files}:
        raise InvalidAnalysisResult('The job does not own this document.')
    result = parse_analysis(raw_result)
    if result.output.type != job.mode.value:
        raise InvalidAnalysisResult('Analyzer returned a different output mode.')
    pages = prepared.data['extracted_text']
    reference = pages[0]['reader']
    all_claims = claims(result.output)
    if sum(len((claim.text or '').split()) for claim in all_claims) > 1000:
        raise InvalidAnalysisResult('The summary exceeds the result word limit.')
    if result.analysis_status == 'not_configured' and (
            any(claim.text or claim.evidence for claim in all_claims) or result.label.ai_label is not None):
        raise InvalidAnalysisResult('An unconfigured analyzer cannot return generated content.')
    validator = EvidenceValidator(db, job, document, prepared)
    for claim, heading in claim_contexts(result.output):
        validator.validate(claim, heading)
    if any(claim.text and claim.unverified for claim in all_claims) and 'unverified_claims' not in result.warnings:
        result.warnings.append('unverified_claims')

    document.page_count = prepared.data['page_count']
    document.extracted_text = pages
    if result.label.ai_label is not None:
        document.ai_label = result.label.ai_label
        document.ai_confidence = result.label.ai_confidence
    # CONFIRMED and user_label represent human decisions. AI cannot change
    # either field or folder_id, including for a high confidence suggestion.
    review_state = document.review_state or ReviewState.NEEDS_REVIEW
    label = LabelMetadata(
        ai_label=document.ai_label, ai_confidence=document.ai_confidence,
        user_label=document.user_label, review_state=review_state.value,
        confidence_level=('unknown' if document.ai_confidence is None else
                          'high' if document.ai_confidence >= .8 else 'low'))
    payload = DocumentResult(
        document_id=document.id, original_filename=document.original_filename, mode=job.mode.value,
        analysis_status=result.analysis_status, label=label, output=result.output,
        reader=ReaderMetadata(version=reference['sha256'], page_count=document.page_count,
                              page_kind=reference['page_kind'],
                              url=f'/documents/{document.id}/reader.pdf?version={reference["sha256"]}'),
        warnings=result.warnings, analysis_metadata=result.analysis_metadata)

    return payload.model_dump(mode='json')


def sync_citations(db, job):
    """Rebuild citations atomically from validated results, preserving each source.

    Deleting only this file's citations loses another claim's cross-document
    sources when the next file completes. Synchronize the entire saved batch.
    Never deduplicate by claim_text/quote: page and document identity matter.
    """
    with db.no_autoflush:
        db.query(Citation).filter_by(job_id=job.id).delete(synchronize_session=False)
        for raw in job.result_data['documents'].values():
            result = DocumentResult.model_validate(raw)
            for claim in claims(result.output):
                if claim.text is None:
                    continue
                for evidence in claim.evidence or [None]:
                    document_id = evidence.document_id if evidence else result.document_id
                    document = db.query(Document).filter_by(id=document_id, owner_id=job.owner_id).one()
                    db.add(Citation(job_id=job.id, document_id=document_id, claim_text=claim.text,
                                    doc_name=document.original_filename,
                                    page=evidence.page if evidence else None,
                                    text_span=evidence.quote if evidence else None,
                                    unverified=claim.unverified))

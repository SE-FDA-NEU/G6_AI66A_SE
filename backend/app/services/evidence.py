"""Reusable evidence validation for every analysis mode, without AI calls.

Only the current user's documents in this job may supply evidence. Resolve
pages from the prepared/persisted reader, never a model-provided page body.
This verifies source identity, exact spans and conservative literal facts. It
does not prove semantic entailment of arbitrary paraphrases or contract advice.
Ambiguous numeric reformats/conversions require review rather than guessing.
"""
from copy import deepcopy
import re
from types import SimpleNamespace
import unicodedata

from pydantic import ValidationError

from app.models import Document
from app.schemas.result import AnalysisResult, Evidence
from app.services.reader_extraction import ReaderConversionError, reader_representation, sha256


def claims(output):
    if output.type == 'bullet':
        return output.bullets + output.actions
    if output.type == 'table':
        return [output.value, output.payment_term, output.penalty]
    return [concept.description for concept in output.concepts]


def claim_contexts(output):
    """A concept title can assert facts too; it shares its description's sources."""
    if output.type == 'concept':
        return [(concept.description, concept.name) for concept in output.concepts]
    return [(claim, '') for claim in claims(output)]


def parse_analysis(raw):
    """Bad individual citations become Unverified, not a lost whole-file result.

    The output envelope and claim text still obey the strict reusable schema.
    Do not echo malformed or unauthorized citation metadata back to a user.
    """
    data = deepcopy(raw.model_dump() if isinstance(raw, AnalysisResult) else raw)
    output = data.get('output', {}) if isinstance(data, dict) else {}
    mode = output.get('type') if isinstance(output, dict) else None
    if mode == 'bullet':
        candidates = [*(output.get('bullets') or []), *(output.get('actions') or [])]
    elif mode == 'table':
        candidates = [output.get(field) for field in ('value', 'payment_term', 'penalty')]
    elif mode == 'concept':
        candidates = [item.get('description') for item in output.get('concepts', []) if isinstance(item, dict)]
    else:
        candidates = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate['verification_issues'] = []  # validation status is server-owned
        original = candidate.get('evidence', [])
        valid, invalid = [], not isinstance(original, list)
        for reference in original if isinstance(original, list) else []:
            try:
                valid.append(Evidence.model_validate(reference).model_dump())
            except ValidationError:
                invalid = True
        if candidate.get('text') is None and valid:
            invalid, valid = True, []
        candidate['evidence'] = valid
        if invalid:
            candidate['unverified'] = True
            candidate['verification_issues'] = ['invalid_evidence']
    return AnalysisResult.model_validate(data)


NUMBER = r'(?<![\w.,])[-+]?\d+(?:[.,]\d+)*(?!\w|[.,]\d)'
DATE = re.compile(r'\b(?:\d{4}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{1,2}|\d{1,2}\s*[-/]\s*\d{1,2}\s*[-/]\s*\d{4})\b')
PERCENT = re.compile(rf'({NUMBER})\s*(?:%|percent\b|phần\s+trăm\b)', re.I)
MONEY = re.compile(rf'(?:[$€£₫]\s*{NUMBER}|{NUMBER}\s*(?:(?:million|billion|thousand|triệu|tỷ|nghìn)\s+)?(?:usd|eur|gbp|vnd|vnđ|đồng)\b)', re.I)
PERIOD = re.compile(r'(?:per\s+|mỗi\s+|/\s*)(day|daily|ngày|month|tháng|year|năm)\b', re.I)
PERIODS = {'day': 'day', 'daily': 'day', 'ngày': 'day', 'month': 'month', 'tháng': 'month', 'year': 'year', 'năm': 'year'}
DURATION = re.compile(rf'({NUMBER})\s*(days?|ngày|months?|tháng|years?|năm)\b', re.I)


def normalized(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text).casefold())


def literal_facts(text):
    """Return comparable facts without silently changing decimals or date order."""
    text = unicodedata.normalize('NFC', text)
    facts = set()
    occupied = set()
    for kind, pattern in [('date', DATE), ('percentage', PERCENT), ('amount', MONEY)]:
        for match in pattern.finditer(text):
            occupied.update(range(match.start(), match.end()))
            if kind == 'percentage':
                value = normalized(match.group(1)) + '%'
                facts.add((kind, value))
                period = PERIOD.match(text[match.end():].lstrip())
                if period:
                    facts.add(('rate_period', value + '/' + PERIODS[period.group(1).casefold()]))
            else:
                facts.add((kind, normalized(match.group())))
    for match in DURATION.finditer(text):
        period = match.group(2).casefold().removesuffix('s')
        facts.add(('duration', normalized(match.group(1)) + '/' + PERIODS[period]))
    for match in re.finditer(NUMBER, text):
        if not any(index in occupied for index in range(match.start(), match.end())):
            facts.add(('number', normalized(match.group())))
    return facts


class EvidenceValidator:
    def __init__(self, db, job, document, prepared):
        self.db, self.owner_id = db, job.owner_id
        self.allowed_ids = {link.document_id for link in job.job_files}
        self.sources = {}
        self.current = document
        self.prepared = prepared

    def source(self, document_id):
        if document_id in self.sources:
            return self.sources[document_id]
        result = None
        if document_id in self.allowed_ids:
            document = self.db.query(Document).filter_by(id=document_id, owner_id=self.owner_id).first()
            if document is not None:
                # Current extraction is staged, so use its pages before commit.
                reader = (SimpleNamespace(id=document.id, storage_path=document.storage_path,
                          file_format=document.file_format, **self.prepared.data)
                          if document_id == self.current.id else document)
                try:
                    _, reference = reader_representation(reader)
                    if sha256(document.storage_path) == reference['source_sha256']:
                        result = (reader.extracted_text, reference)
                except (ReaderConversionError, OSError):
                    pass
        self.sources[document_id] = result
        return result

    def validate(self, claim, heading=''):
        issues = list(claim.verification_issues)
        accepted, seen = [], set()
        for evidence in claim.evidence:
            source = self.source(evidence.document_id)
            valid = False
            if source is not None:
                pages, reference = source
                if (evidence.reader_version == reference['sha256'] and evidence.page <= len(pages)):
                    page = pages[evidence.page - 1]
                    valid = (page['page'] == evidence.page and evidence.end <= len(page['text']) and
                             page['text'][evidence.start:evidence.end] == evidence.quote and bool(evidence.quote.strip()))
            if not valid:
                issues.append('invalid_evidence')
                continue
            identity = (evidence.document_id, evidence.page, evidence.start, evidence.end, evidence.reader_version)
            if identity not in seen:
                accepted.append(evidence)
                seen.add(identity)
        claim.evidence = accepted
        if claim.text:
            if not accepted:
                issues.append('missing_evidence')
            else:
                required = literal_facts(heading + ' ' + claim.text)
                supported = set().union(*(literal_facts(item.quote) for item in accepted))
                if not required.issubset(supported):
                    issues.append('unsupported_fact')
                if claim.kind == 'general':
                    claim.kind = next((kind for kind in ('percentage', 'amount', 'date')
                                       if any(fact[0] == kind for fact in required)), 'general')
            if claim.unverified and not issues:
                issues.append('model_uncertain')
        claim.verification_issues = list(dict.fromkeys(issues))
        claim.unverified = claim.unverified or bool(issues) or not accepted
        return claim

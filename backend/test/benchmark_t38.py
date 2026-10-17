"""Run T38 against the configured real Gemini model, never against a mock.

Usage from backend: .venv/Scripts/python.exe test/benchmark_t38.py [--pdf report.pdf]
Uses a temporary SQLite DB/storage and writes test-results/t38.json by default.
The default input is a synthetic 15-page report with explicit source actions.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DB_PASSWORD', 'unused-isolated-benchmark')
os.environ.setdefault('SECRET_KEY', 'unused-isolated-benchmark-secret')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.database import Base
from app.models import Document, FileFormat, Job, JobFile, JobMode, JobStatus, User
from app.services.processing import BULLET_TARGET_SECONDS, process_job
from app.schemas.result import DocumentResult


def sample_pdf(path):
    # Reuse the deterministic native PDF writer; no additional model call builds the fixture.
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_pdf_extraction import make_pdf
    pages = [
        'Market report. Revenue is 1,200,000,000 VND. Operating costs are 750,000,000 VND.',
        'Recommended action: Review the revenue forecast before approving the budget.',
        'Recommended action: Compare supplier quotations before renewing the supply contract.',
        'Risk: A late payment incurs a penalty of 0.05% per day.',
    ]
    pages += [f'Section {page}. Monitor market demand and document changes in the monthly report.' for page in range(5, 16)]
    return make_pdf(path, [f'BT /F1 10 Tf 30 720 Td ({text}) Tj ET'.encode() for text in pages])


def benchmark(pdf_path, work):
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
    if page_count != 15:
        return {'status': 'blocked', 'reason': 'T38 requires a 15-page PDF.', 'page_count': page_count,
                'passed': False, 'real_model': False}
    settings.STORAGE_DIR = work / 'storage'
    settings.GEMINI_CACHE_ENABLED = False
    engine = create_engine(f'sqlite:///{(work / "benchmark.db").as_posix()}')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    try:
        source = pdf_path.read_bytes()
        stored = work / 'input.pdf'
        stored.write_bytes(source)
        with factory() as db:
            user = User(username='t38', email='t38@example.invalid', password_hash='unused')
            db.add(user)
            db.flush()
            document = Document(owner_id=user.id, original_filename=pdf_path.name,
                                storage_path=str(stored), file_format=FileFormat.PDF, file_size_bytes=len(source),
                                expires_at=datetime.now(timezone.utc) + timedelta(days=30))
            job = Job(owner_id=user.id, mode=JobMode.BULLET, status=JobStatus.PENDING,
                      file_count=1, completed_count=0)
            db.add_all([document, job])
            db.flush()
            db.add(JobFile(job_id=job.id, document_id=document.id, status=JobStatus.PENDING))
            job_id = job.id
            db.commit()
        started = time.perf_counter()
        process_job(job_id, factory)
        elapsed = time.perf_counter() - started
        with factory() as db:
            job = db.get(Job, job_id)
            file = job.job_files[0]
            report = {'status': job.status.value, 'elapsed_seconds': round(elapsed, 3),
                      'within_target': elapsed <= BULLET_TARGET_SECONDS,
                      'page_count': file.document.page_count, 'attempt_count': file.attempt_count,
                      'error_message': file.error_message, 'source_sha256': hashlib.sha256(source).hexdigest()}
            raw = (job.result_data or {}).get('documents', {}).get(str(file.document_id))
            if raw:
                result = DocumentResult.model_validate(raw)
                output = result.output
                report.update(word_count=sum(len((claim.text or '').split()) for claim in output.bullets + output.actions)
                              + len((output.limitation or '').split()),
                              bullet_count=len(output.bullets), action_count=len(output.actions),
                              limitation=output.limitation, warnings=result.warnings,
                              analysis_metadata=result.analysis_metadata.model_dump() if result.analysis_metadata else None,
                              field_evidence_valid=all(action.evidence and not action.unverified for action in output.actions))
            report['passed'] = bool(job.status == JobStatus.COMPLETED and raw and
                                    raw['analysis_status'] == 'completed' and report['page_count'] == 15 and
                                    report['within_target'] and report['word_count'] <= 1000 and
                                    report['field_evidence_valid'] and report['bullet_count'] > 0 and
                                    (report['action_count'] >= 2 or report['limitation']))
            return report
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', type=Path, help='A real 15-page native PDF; default: synthetic report.')
    parser.add_argument('--output', type=Path, default=ROOT / 'test-results' / 't38.json')
    args = parser.parse_args()
    report = {'test_case': 'T38', 'model': settings.GEMINI_MODEL, 'real_model': True,
              'started_at': datetime.now(timezone.utc).isoformat(), 'target_seconds': BULLET_TARGET_SECONDS,
              'input_kind': 'provided_pdf' if args.pdf else 'synthetic_15_page_pdf', 'passed': False}
    if not settings.GEMINI_API_KEY.get_secret_value().strip():
        report.update(status='blocked', reason='GEMINI_API_KEY is not configured.', real_model=False)
    else:
        with tempfile.TemporaryDirectory(prefix='documind-t38-') as directory:
            work = Path(directory)
            source = args.pdf.resolve() if args.pdf else sample_pdf(work / 'market-report-15-pages.pdf')
            report.update(benchmark(source, work))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

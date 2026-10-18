"""Real saved-table export, authorization, numeric fidelity and PDF layout checks."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pdfplumber
import pypdfium2
import pytest

from app.core.security import create_access_token
from app.models import Job
from app.models.jobmode import JobMode
from app.models.jobstatus import JobStatus
from app.services import processing
from test_financial_table import AMOUNTS, financial_batch  # shared real five-contract pipeline fixture


@pytest.fixture
def completed_table(client, session_factory, financial_batch):
    job_id, state = financial_batch
    processing.process_job(job_id, session_factory)
    with session_factory() as db:
        job = db.get(Job, job_id)
        data = deepcopy(job.result_data)
        for index, file in enumerate(sorted(job.job_files, key=lambda file: file.id)):
            row = data['documents'][str(file.document_id)]
            row['original_filename'] = f'Hợp đồng {index + 1}.pdf'
            # Later metadata edits must not replace the saved comparison snapshot.
            file.document.original_filename = f'renamed-{index + 1}.pdf'
        job.result_data = data
        db.commit()
    return job_id, state


def export(client, job_id):
    return client.get(f'/jobs/{job_id}/export.pdf')


def pdf_text(content):
    with pdfplumber.open(BytesIO(content)) as pdf:
        return '\n'.join(page.extract_text() for page in pdf.pages)


def test_five_saved_rows_units_vietnamese_missing_fields_and_repeat_download(
        client, session_factory, completed_table):
    job_id, state = completed_table
    before = client.get(f'/jobs/{job_id}').json()
    result = export(client, job_id)
    assert result.status_code == 200 and result.content.startswith(b'%PDF-')
    assert result.headers['content-type'] == 'application/pdf'
    assert result.headers['content-disposition'] == f'attachment; filename="comparison-{job_id}.pdf"'
    assert result.headers['cache-control'] == 'private, no-store'
    text = pdf_text(result.content)
    for index, amount in enumerate(AMOUNTS):
        assert f'Hợp đồng {index + 1}.pdf' in text
        assert amount in text
    assert text.count('0.05% per day') == 5
    assert 'Không có thông tin' in text and 'Unverified' in text
    assert 'Chưa có nguồn xác thực' in text and 'trang 1' in text
    assert 'renamed-' not in text
    with pdfplumber.open(BytesIO(result.content)) as pdf:
        tables = [table for page in pdf.pages for table in page.extract_tables()]
        assert sum(len(table) - 1 for table in tables) == 5
        assert all('Tài liệu' in page.extract_text() for page in pdf.pages)
    assert pdf_text(export(client, job_id).content) == text
    assert client.get(f'/jobs/{job_id}').json() == before and state['calls'] == 5


@pytest.mark.parametrize('status', [JobStatus.PENDING, JobStatus.PROCESSING,
                                    JobStatus.FAILED, JobStatus.TIMED_OUT])
def test_incomplete_job_cannot_export(client, session_factory, completed_table, status):
    job_id, _ = completed_table
    with session_factory() as db:
        db.get(Job, job_id).status = status
        db.commit()
    assert export(client, job_id).status_code == 409


@pytest.mark.parametrize('problem', ['wrong_mode', 'partial_count', 'partial_file', 'missing_file',
                                    'missing_result', 'missing_row', 'extra_row', 'missing_field',
                                    'wrong_row_id', 'wrong_output', 'not_analyzed', 'foreign_document'])
def test_completed_status_alone_does_not_make_a_complete_table(
        client, session_factory, completed_table, problem):
    job_id, _ = completed_table
    with session_factory() as db:
        job = db.get(Job, job_id)
        data = deepcopy(job.result_data)
        key = next(iter(data['documents']))
        row = data['documents'][key]
        if problem == 'wrong_mode':
            job.mode = JobMode.BULLET
        elif problem == 'partial_count':
            job.completed_count = 4
        elif problem == 'partial_file':
            job.job_files[-1].status = JobStatus.FAILED
        elif problem == 'missing_file':
            job.job_files.pop()
        elif problem == 'missing_result':
            data = None
        elif problem == 'missing_row':
            del data['documents'][key]
        elif problem == 'extra_row':
            data['documents']['9999'] = deepcopy(row)
        elif problem == 'missing_field':
            del row['output']['penalty']
        elif problem == 'wrong_row_id':
            row['document_id'] = 9999
        elif problem == 'wrong_output':
            row['output'] = {'type': 'bullet', 'bullets': [], 'actions': []}
        elif problem == 'not_analyzed':
            row['analysis_status'] = 'not_configured'
        elif problem == 'foreign_document':
            job.job_files[0].document.owner_id = 124
        job.result_data = data
        db.commit()
    result = export(client, job_id)
    assert result.status_code == 409 and not result.content.startswith(b'%PDF')


def test_other_account_missing_job_and_unauthenticated_requests(client, completed_table):
    job_id, _ = completed_table
    client.headers['Authorization'] = f"Bearer {create_access_token({'sub': '124'})}"
    other = export(client, job_id)
    assert other.status_code == 404
    assert other.json() == client.get(f'/jobs/{job_id}').json()
    assert export(client, 999999).status_code == 404
    del client.headers['Authorization']
    assert export(client, job_id).status_code == 401


@pytest.mark.parametrize('problem', ['unsupported', 'missing', 'issues', 'foreign_source', 'wrong_version', 'bad_page'])
def test_unverified_cells_and_only_real_authorized_page_references(
        client, session_factory, completed_table, problem):
    job_id, _ = completed_table
    with session_factory() as db:
        job = db.get(Job, job_id)
        data = deepcopy(job.result_data)
        row = next(iter(data['documents'].values()))
        claim = row['output']['value']
        # Do not trust a stale false flag when evidence is missing or unusable.
        claim['unverified'] = False
        if problem == 'unsupported':
            claim['unverified'] = True
        elif problem == 'missing':
            claim['evidence'] = []
        elif problem == 'issues':
            claim['verification_issues'] = ['unsupported_fact']
        elif problem == 'foreign_source':
            claim['evidence'][0]['document_id'] = 999999
        elif problem == 'wrong_version':
            claim['evidence'][0]['reader_version'] = '0' * 64
        elif problem == 'bad_page':
            claim['evidence'][0]['page'] = 999
        job.result_data = data
        db.commit()
    response = export(client, job_id)
    assert response.status_code == 200
    text = pdf_text(response.content)
    assert '1,200,000,000 VND' in text
    with pdfplumber.open(BytesIO(response.content)) as pdf:
        first_row = pdf.pages[0].extract_tables()[0][1]
        assert 'Unverified' in first_row[1] and 'Unverified' in first_row[4]
        if problem in ('missing', 'foreign_source', 'wrong_version', 'bad_page'):
            source_value = first_row[4].split('Thanh toán:')[0]
            assert 'trang' not in source_value and 'Chưa có nguồn xác thực' in source_value


def test_long_clauses_wrap_split_rows_repeat_headers_and_render_without_clipping(
        client, session_factory, completed_table):
    job_id, _ = completed_table
    sentence = 'Bên mua thanh toán trong vòng 30 ngày sau khi nhận đủ hồ sơ hợp lệ. '
    with session_factory() as db:
        job = db.get(Job, job_id)
        data = deepcopy(job.result_data)
        row = next(iter(data['documents'].values()))
        row['output']['payment_term'] = {
            'text': sentence * 110 + 'KẾT THÚC ĐIỀU KHOẢN <tag> & nguyên văn.',
            'evidence': [], 'unverified': True,
        }
        row['reader']['page_count'] = 6
        row['output']['value']['evidence'][0]['page'] = 6
        row['original_filename'] = 'Hợp đồng_' + 'rấtdài' * 35 + '.pdf'
        job.result_data = data
        db.commit()
    result = export(client, job_id)
    assert result.status_code == 200
    text = pdf_text(result.content)
    assert 'trang 6' in text
    with pdfplumber.open(BytesIO(result.content)) as pdf:
        assert len(pdf.pages) >= 3
        # Read the payment column in order: whole-page extraction interleaves
        # adjacent columns, and line/page breaks must not count as lost words.
        payment_text = ' '.join(' '.join(
            row[2] or '' for page in pdf.pages for table in page.extract_tables()
            for row in table[1:]).split())
        assert payment_text.count(sentence.strip()) == 110
        assert 'KẾT THÚC ĐIỀU KHOẢN <tag> & nguyên văn.' in payment_text
        for page in pdf.pages:
            assert all(header in page.extract_text() for header in ('Tài liệu', 'Giá trị', 'Thanh toán', 'Phạt', 'Nguồn (trang)'))
            for char in page.chars:
                assert 35 <= char['x0'] < char['x1'] <= page.width - 35
                assert 30 <= char['top'] < char['bottom'] <= page.height - 15
    artifacts = Path(__file__).resolve().parents[1] / 'test-results'
    artifacts.mkdir(exist_ok=True)
    (artifacts / 'comparison-long-clauses.pdf').write_bytes(result.content)
    rendered = pypdfium2.PdfDocument(result.content)
    try:
        for index in (0, 1, len(rendered) - 1):
            page = rendered[index]
            bitmap = page.render(scale=1.4)
            bitmap.to_pil().save(artifacts / f'comparison-long-page-{index + 1}.png')
            bitmap.close()
            page.close()
    finally:
        rendered.close()

"""Acceptance corpus integrity plus real API/extraction/DB checks, offline."""
import hashlib
import json
from pathlib import Path
import sys

from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'test'))
from acceptance_fixtures import FIXTURES, build, controlled_output, seed_account
from app.core.config import settings
from app.models import Document
from app.services.pdf_extraction import extract_pdf
from app.services import gemini_analysis as gemini, processing


def manifest():
    return json.loads((FIXTURES / 'expected.json').read_text(encoding='utf-8'))


def test_committed_sources_match_answers_and_rebuild_deterministically(tmp_path):
    expected = manifest()
    assert build(tmp_path) == expected
    assert len(expected['documents']) == 20
    for spec in expected['documents']:
        path = FIXTURES / spec['filename']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == spec['sha256']
        actual = extract_pdf(path)
        assert actual['page_count'] == spec['page_count']
        assert [{'page': p['page'], 'text': p['text']} for p in actual['extracted_text']] == spec['pages']
        for field, evidence in spec.get('field_evidence', {}).items():
            if evidence is None:
                assert spec['fields'][field] is None
            else:
                text = spec['pages'][evidence['page'] - 1]['text']
                assert text[evidence['start']:evidence['end']] == evidence['quote'] == spec['fields'][field]
    by_key = {doc['key']: doc for doc in expected['documents']}
    assert by_key['report-15-pages']['page_count'] == 15
    assert by_key['contract-24-pages']['page_count'] == 24
    assert by_key['textless-page']['pages'] == [{'page': 1, 'text': ''}]


def install_controlled_provider(monkeypatch, specs, mode):
    monkeypatch.setattr(settings, 'GEMINI_API_KEY', SecretStr('offline-acceptance-only'))
    monkeypatch.setattr(settings, 'GEMINI_CACHE_ENABLED', False)
    pending = iter(specs)
    calls = []
    async def generate(body):
        calls.append(body)
        excerpts = json.loads(body['contents'][0]['parts'][0]['text'])
        return controlled_output(next(pending), excerpts, mode), {}
    monkeypatch.setattr(gemini, 'generate', generate)
    return calls


def upload(client, specs, mode):
    files = [('files', (spec['filename'], (FIXTURES / spec['filename']).read_bytes(), 'application/pdf'))
             for spec in specs]
    response = client.post('/upload', data={'mode': mode}, files=files)
    assert response.status_code == 202, response.text
    return int(response.json()['jobId'])


def test_five_committed_contracts_persist_numbers_sources_and_confidence_boundary(client, session_factory, monkeypatch):
    specs = manifest()['documents'][:5]
    install_controlled_provider(monkeypatch, specs, 'table')
    job_id = upload(client, specs, 'table')
    processing.process_job(job_id, session_factory)
    response = client.get(f'/jobs/{job_id}').json()
    assert response['status'] == 'completed' and response['completed_count'] == 5
    rows = list(response['result_data']['documents'].values())
    for spec, row in zip(specs, rows):
        assert row['original_filename'] == spec['filename']
        for field, value in spec['fields'].items():
            claim = row['output'][field]
            assert claim['text'] == value
            assert claim['unverified'] is (value is None)
            if value is None:
                assert claim['evidence'] == []
            else:
                assert claim['evidence'][0]['page'] == spec['field_evidence'][field]['page']
                assert value in claim['evidence'][0]['quote']
        assert row['label'] == spec['expected_label']
    assert rows[0]['label']['ai_confidence'] == .79 and rows[0]['label']['confidence_level'] == 'low'
    assert rows[1]['label']['ai_confidence'] == .8 and rows[1]['label']['confidence_level'] == 'high'
    assert client.get(f'/jobs/{job_id}').json()['result_data'] == response['result_data']


def test_supported_insufficient_and_missing_evidence_use_saved_shared_contract(client, session_factory, monkeypatch):
    by_key = {doc['key']: doc for doc in manifest()['documents']}
    for key in ('report-15-pages', 'insufficient-actions', 'missing-evidence', 'textless-page'):
        spec = by_key[key]
        calls = install_controlled_provider(monkeypatch, [spec], 'bullet')
        job_id = upload(client, [spec], 'bullet')
        processing.process_job(job_id, session_factory)
        saved = client.get(f'/jobs/{job_id}').json()
        assert saved['status'] == 'completed', saved
        row = next(iter(saved['result_data']['documents'].values()))
        output = row['output']
        words = sum(len((c['text'] or '').split()) for c in output['bullets'] + output['actions'])
        assert words + len((output['limitation'] or '').split()) <= 1000
        expected = spec['expected_bullet_output']
        assert bool(output['limitation']) == expected['limitation_required']
        for field in ('bullets', 'actions'):
            assert len(output[field]) == len(expected[field])
            for claim, answer in zip(output[field], expected[field]):
                assert claim['text'] == answer['text']
                assert claim['unverified'] is answer['unverified']
                assert [e['page'] for e in claim['evidence']] == answer['source_pages']
        assert len(calls) == (0 if key == 'textless-page' else 1)
        assert client.get(f'/jobs/{job_id}').json()['result_data'] == saved['result_data']


def test_seed_extends_ten_to_twenty_and_searches_beyond_list_page_with_owner_isolation(client, session_factory):
    storage = settings.STORAGE_DIR
    ids = seed_account(session_factory, storage, 123, count=10)
    assert len(ids) == 10
    with session_factory() as db:
        edited = db.get(Document, ids[0])
        edited.user_label = 'Preserved human edit'
        edited.folder_id = None
        db.commit()
    extended = seed_account(session_factory, storage, 123)
    assert extended[:10] == ids and len(extended) == 20
    assert seed_account(session_factory, storage, 123) == extended
    with session_factory() as db:
        assert db.query(Document).filter_by(owner_id=123).count() == 20
        edited = db.get(Document, ids[0])
        assert edited.user_label == 'Preserved human edit' and edited.folder_id is None
    listing = client.get('/documents', params={'limit': 3}).json()
    # This API returns a list; search must not be constrained to its visible IDs.
    visible = {row['id'] for row in listing}
    for query in manifest()['search']:
        response = client.get('/search', params={'q': query['query']})
        assert response.status_code == 200, response.text
        hits = response.json()['hits']
        expected = {(hit['key'] + '.pdf', hit['page']) for hit in query['hits']}
        assert {(hit['doc_name'], hit['page']) for hit in hits} == expected
        for hit, answer in zip(hits, query['hits']):
            assert hit['snippet'] == answer['snippet']
            assert (hit['start'], hit['end']) == (answer['start'], answer['end'])
            assert f"page={hit['page']}" in hit['highlight_url']
            page = client.get(f"/documents/{hit['document_id']}/pages/{hit['page']}/text")
            assert page.status_code == 200
            assert answer['snippet'] in page.json()['text']
        if query['hits']:
            assert any(hit['document_id'] not in visible for hit in hits)
    filtered = client.get('/documents', params={'ai_label': 'Macroeconomics', 'limit': 100}).json()
    assert len(filtered) == 8
    for folder_id in {row['folder_id'] for row in filtered if row['folder_id'] is not None}:
        combined = client.get('/documents', params={
            'ai_label': 'Macroeconomics', 'folder_id': folder_id, 'limit': 100}).json()
        assert {row['id'] for row in combined} == {row['id'] for row in filtered if row['folder_id'] == folder_id}
    assert len(client.get('/documents', params={'limit': 100}).json()) == 20
    from app.core.security import create_access_token
    client.headers['Authorization'] = f"Bearer {create_access_token({'sub': '124'})}"
    assert client.get('/search', params={'q': 'Amber escrow release'}).json()['hits'] == []

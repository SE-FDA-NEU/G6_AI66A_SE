"""Opt-in pytest collector for the US04/US08/US09 handover matrix."""
import json
import re
from pathlib import Path


def pytest_collection_finish(session):
    rows = []
    for item in session.items:
        case = re.search(r'TC-US(?:04|08|09)-\d+', item.nodeid)
        if case:
            rows.append({
                'case_id': case.group(),
                'nodeid': item.nodeid,
                'parameters': item.callspec.params,
            })
    output = Path(__file__).resolve().parents[1] / 'docs/testing-evidence/cases.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')

"""Source-derived coverage checks; never rewrite source text or citations."""
from collections import Counter
import re
import unicodedata


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFC', value).casefold() if c.isalnum())


def source_topics(wire):
    """Find recurring slide headings and named sections, not body sentences.

    A table of contents alone does not establish a detailed topic. Require a
    section heading in an excerpt, and retain its exact original spelling.
    """
    headings = []
    for source_id, text in wire:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        heading = lines[0]
        if (len(heading) > 110 or len(heading.split()) > 14 or heading.isdigit()
                or heading.endswith(('.', '?', ':'))
                or heading.casefold() in {'nội dung', 'contents', 'agenda', 'references', 'tài liệu tham khảo'}):
            continue
        headings.append((source_id, heading))
    counts = Counter(heading for _, heading in headings)
    topics = {}
    for source_id, heading in headings:
        aliases = re.findall(r'\(([A-Za-z][A-Za-z0-9 -]{1,39})\)', heading)
        name = aliases[-1] if aliases else heading
        if not aliases and counts[heading] < 2:
            continue
        if normalized(name) not in topics:
            topics[normalized(name)] = {'name': name, 'sources': []}
        topics[normalized(name)]['sources'].append(source_id)
    return list(topics.values())


def coverage_instructions(wire, mode):
    if mode not in ('bullet', 'concept'):
        return ''
    topics = source_topics(wire)
    if not topics:
        return ''
    names = ', '.join(topic['name'] for topic in topics)
    if mode == 'concept' and len(topics) > 5:
        return (' SOURCE CONCEPT CANDIDATES: ' + names + '. Select only 3-5 central, well-supported concepts. '
                'Retain their exact source names and supporting IDs. Other candidates may be omitted; '
                'do not invent details from titles or figures.')
    return (
        ' SOURCE COVERAGE CHECKLIST (derived from section headings): ' + names + '. '
        'Give each listed topic its own substantive item with its EXACT source name, '
        'its defining mechanism and supporting source IDs. A name mentioned only in the overview is not coverage. '
        'Also cover major mechanisms not listed in the headings. Do not invent facts from title-only slides; '
        'state the source limitation when details exist only in figures. '
        'Use the checklist to review completeness before returning JSON.'
    )


def quality_issues(raw, wire, mode):
    if mode not in ('bullet', 'concept'):
        return []
    topics = source_topics(wire)
    if mode == 'bullet':
        # The overview may enumerate names without explaining any of them.
        details = [(item.t or '', item.s or []) for item in raw.bullets[1:]]
    else:
        details = [(item.n + ' ' + (item.t or ''), item.s or []) for item in raw.concepts]
    text = '\n'.join(text for text, _ in details)
    missing = [topic['name'] for topic in topics if not any(
        normalized(topic['name']) in normalized(text) and len(text.split()) >= 8
        and set(sources).intersection(topic['sources']) for text, sources in details)]
    if mode == 'concept' and len(topics) > 5:
        # The reader contract allows at most five concepts. Requiring one
        # separate item for every source topic would make valid output impossible.
        missing = []
    issues = ['Missing substantive coverage: ' + ', '.join(missing)] if missing else []
    source = ' '.join(text for _, text in wire).casefold()
    invented = sorted({word for word in re.findall(r'\b[A-Z][A-Z0-9]{1,7}\b', text)
                       if word.casefold() not in source})
    if invented:
        issues.append('Check unsupported or misspelled abbreviations: ' + ', '.join(invented))
    return issues

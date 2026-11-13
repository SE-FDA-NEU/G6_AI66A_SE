from copy import deepcopy

from app.services.gemini_analysis import WireBullet
from app.services.summary_quality import coverage_instructions, quality_issues, source_topics


HEADER = 'Facultyof Data Science and Artificial Intelligence MovieMate'


def test_repeated_report_masthead_is_not_a_required_summary_topic():
    wire = [(i, HEADER + '\n' + f'{i + 1}. Project section\nThe service recommends movies using user preferences.')
            for i in range(5)]
    original = deepcopy(wire)
    assert source_topics(wire) == []
    assert coverage_instructions(wire, 'bullet') == ''
    raw = WireBullet.model_validate({'label': None, 'confidence': None, 'bullets': [
        {'t': 'An overview of a movie recommendation service.', 's': [0]},
        {'t': 'The service recommends movies based on the preferences provided by each user.', 's': [1]},
    ], 'actions': []})
    assert quality_issues(raw, wire, 'bullet') == []
    assert wire == original


def test_real_section_headings_after_masthead_still_require_grounded_coverage():
    wire = [(i, HEADER + '\nCollaborative Filtering (CF)\nRecommendations use shared preferences between users.')
            for i in range(3)]
    topics = source_topics(wire)
    assert topics == [{'name': 'CF', 'sources': [0, 1, 2]}]
    raw = WireBullet.model_validate({'label': None, 'confidence': None, 'bullets': [
        {'t': 'CF is the subject of this overview.', 's': [0]},
        {'t': 'The project stores user preferences and generates suggestions for movie viewers.', 's': [1]},
    ], 'actions': []})
    assert quality_issues(raw, wire, 'bullet') == ['Missing substantive coverage: CF']
    raw.bullets[1].t = 'CF generates movie recommendations using shared preferences between different users.'
    assert quality_issues(raw, wire, 'bullet') == []


def test_lecture_architecture_headings_remain_required_topics():
    wire = [(i, name + '\nThis architecture extracts hierarchical features from image inputs.')
            for i, name in enumerate(['AlexNet', 'AlexNet', 'VGG', 'VGG', 'DenseNet', 'DenseNet'])]
    assert [topic['name'] for topic in source_topics(wire)] == ['AlexNet', 'VGG', 'DenseNet']


def test_nonrepeated_institution_heading_is_not_automatically_stripped():
    wire = [(0, 'Faculty of Medicine (FM)\nThis department studies clinical health.')]
    assert [topic['name'] for topic in source_topics(wire)] == ['FM']

from app.skills import SKILLS, detect_skill_code, parse_top_skill_numbers


def test_skill_count_and_question_bank():
    assert len(SKILLS) == 18
    assert all(len(item['questions']) >= 1 for item in SKILLS)


def test_detect_common_skills():
    assert detect_skill_code('JUKI DDL-9000C jarum 1') == 'JARUM_1'
    assert detect_skill_code('mesin obras Pegasus') == 'OBRAS'
    assert detect_skill_code('servo drive error') == 'ELEKTRONIK_SERVO'
    assert detect_skill_code('auto template pattern') == 'AUTO_TEMPLATE'


def test_parse_top_skill_numbers():
    assert parse_top_skill_numbers('1,3,14') == [1, 3, 14]
    assert parse_top_skill_numbers('1 3 14') == [1, 3, 14]
    assert parse_top_skill_numbers('99') == []

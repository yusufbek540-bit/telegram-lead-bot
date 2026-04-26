"""Unit tests for score recalculation against the new intake fields."""

from bot.services.db_service import compute_score


def test_score_business_name_only():
    lead = {"phone": None, "email": None, "business_name": "Foo Clinic", "website": None}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    assert score == 5


def test_score_business_name_and_website():
    lead = {"phone": None, "email": None, "business_name": "Foo Clinic", "website": "https://foo.com"}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    assert score == 10


def test_score_no_intake_no_score():
    lead = {"phone": None, "email": None, "business_name": None, "website": None}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    assert score == 0


def test_score_phone_plus_intake():
    lead = {"phone": "+998900000000", "email": None, "business_name": "Foo", "website": "https://foo.com"}
    score = compute_score(lead, user_msg_count=0, event_types=set())
    assert score == 40

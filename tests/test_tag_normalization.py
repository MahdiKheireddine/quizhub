"""Tests for Tag.from_string normalization."""

import pytest

from quizzes.models import Tag


@pytest.mark.django_db
class TestTagFromString:
    @pytest.mark.parametrize("raw,expected", [
        ("django", "django"),
        ("Django", "django"),
        ("DJANGO", "django"),
        ("  django  ", "django"),
        ("web dev", "web-dev"),
        ("Web Dev", "web-dev"),
        ("hello!! @#$", "hello"),
        ("multi   spaces", "multi-spaces"),
        ("---leading-trailing---", "leading-trailing"),
    ])
    def test_normalization(self, raw, expected):
        t = Tag.from_string(raw)
        assert t is not None
        assert t.slug == expected

    @pytest.mark.parametrize("raw", ["", "  ", "!@#$%", "---"])
    def test_invalid_returns_none(self, raw):
        assert Tag.from_string(raw) is None

    def test_same_input_returns_same_tag(self):
        t1 = Tag.from_string("django")
        t2 = Tag.from_string("Django")
        t3 = Tag.from_string("DJANGO")
        assert t1.id == t2.id == t3.id

    def test_truncates_long_input(self):
        raw = "a" * 100
        t = Tag.from_string(raw)
        assert len(t.slug) <= 40
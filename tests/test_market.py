"""Tests for Market and elapsed_seconds."""

from datetime import datetime

import pytest

from vizflow import CN, CRYPTO, Market, Session


class TestCNMarket:
    """Tests for China A-shares market."""

    def test_elapsed_seconds_morning_open(self):
        """09:30:00 → 0"""
        dt = datetime(2024, 1, 1, 9, 30, 0)
        assert CN.elapsed_seconds(dt) == 0

    def test_elapsed_seconds_morning_middle(self):
        """10:00:00 → 1800 (30 minutes)"""
        dt = datetime(2024, 1, 1, 10, 0, 0)
        assert CN.elapsed_seconds(dt) == 1800

    def test_elapsed_seconds_morning_end(self):
        """11:29:59 → 7199"""
        dt = datetime(2024, 1, 1, 11, 29, 59)
        assert CN.elapsed_seconds(dt) == 7199

    def test_elapsed_seconds_afternoon_open(self):
        """13:00:00 → 7200"""
        dt = datetime(2024, 1, 1, 13, 0, 0)
        assert CN.elapsed_seconds(dt) == 7200

    def test_elapsed_seconds_afternoon_middle(self):
        """14:00:00 → 10800 (7200 + 3600)"""
        dt = datetime(2024, 1, 1, 14, 0, 0)
        assert CN.elapsed_seconds(dt) == 10800

    def test_elapsed_seconds_afternoon_end(self):
        """15:00:00 → 14400"""
        dt = datetime(2024, 1, 1, 15, 0, 0)
        assert CN.elapsed_seconds(dt) == 14400

    def test_elapsed_seconds_outside_hours(self):
        """Time outside trading hours should raise ValueError."""
        dt = datetime(2024, 1, 1, 12, 0, 0)  # Lunch break
        with pytest.raises(ValueError):
            CN.elapsed_seconds(dt)


class TestCryptoMarket:
    """Tests for crypto market (24/7)."""

    def test_elapsed_seconds_midnight(self):
        """00:00:00 → 0"""
        dt = datetime(2024, 1, 1, 0, 0, 0)
        assert CRYPTO.elapsed_seconds(dt) == 0

    def test_elapsed_seconds_noon(self):
        """12:00:00 → 43200"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        assert CRYPTO.elapsed_seconds(dt) == 43200


class TestMarketStructure:
    """Tests for Market/Session structure."""

    def test_cn_has_two_sessions(self):
        """CN market should have 2 sessions."""
        assert len(CN.sessions) == 2

    def test_session_attributes(self):
        """Session should have start and end."""
        session = CN.sessions[0]
        assert session.start == "09:30"
        assert session.end == "11:30"

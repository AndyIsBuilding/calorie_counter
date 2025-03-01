import pytest
from datetime import datetime, date
import pytz
import sys
import os

# Add the parent directory to sys.path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import get_local_date

def test_get_local_date(app):
    """Test the get_local_date function."""
    with app.app_context():
        # Test that the function returns a date or datetime object
        result = get_local_date()
        assert isinstance(result, (date, datetime))
        
        # Test that the date is recent
        today = date.today()
        if isinstance(result, datetime):
            assert (today - result.date()).days <= 1
        else:
            assert (today - result).days <= 1 
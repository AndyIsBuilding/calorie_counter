# Testing the HealthVibe Application

This directory contains tests for the HealthVibe application using pytest.

## Running Tests

To run all tests:

```bash
pytest
```

To run tests with coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

To run a specific test file:

```bash
pytest tests/test_routes.py
```

To run a specific test function:

```bash
pytest tests/test_routes.py::test_index_page
```

To run a report with HTML coverage: 
```bash
pytest --cov=all -cov-report=html
```

## Test Structure

- `conftest.py`: Contains pytest fixtures used across test files
- `test_auth.py`: Tests for authentication and authorization
- `test_dashboard_routes.py`: Tests for dashboard routes and views
- `test_database.py`: Tests for database operations
- `test_food_logging.py`: Tests for food logging and tracking
- `test_goals.py`: Tests for goal tracking and management
- `test_routes.py`: Tests for application routes and views
- `test_settings_routes.py`: Tests for settings routes and views
- `test_user_management.py`: Tests for user management
- `test_utils.py`: Tests for utility functions  

## Adding New Tests

When adding new tests:

1. Create a new file named `test_*.py` in the tests directory
2. Import necessary fixtures from `conftest.py`
3. Write test functions prefixed with `test_`

## Test Database

Tests use a temporary SQLite database that is created and destroyed for each test session. This ensures that tests don't interfere with your development or production database. 
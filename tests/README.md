# Testing the Calorie Counter Application

This directory contains tests for the Calorie Counter application using pytest.

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

## Test Structure

- `conftest.py`: Contains pytest fixtures used across test files
- `test_routes.py`: Tests for application routes and views
- `test_database.py`: Tests for database operations

## Adding New Tests

When adding new tests:

1. Create a new file named `test_*.py` in the tests directory
2. Import necessary fixtures from `conftest.py`
3. Write test functions prefixed with `test_`

## Test Database

Tests use a temporary SQLite database that is created and destroyed for each test session. This ensures that tests don't interfere with your development or production database. 
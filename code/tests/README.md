# API Tests

This directory contains comprehensive tests for the Luftdaten API endpoints.

## Test Structure

- `conftest.py` - Pytest configuration and common fixtures
- `test_station.py` - Tests for station-related endpoints
- `test_city.py` - Tests for city-related endpoints  
- `test_health.py` - Tests for health check endpoints

## Running Tests

### Prerequisites

1. Ensure you have a test database running (PostgreSQL)
2. Install test dependencies:
   ```bash
   pip install pytest pytest-cov
   ```

### Running All Tests

From the `code` directory:
```bash
pytest tests/ -v
```

### Running Specific Test Files

```bash
# Run only city tests
pytest tests/test_city.py -v

# Run only health tests
pytest tests/test_health.py -v

# Run only station tests
pytest tests/test_station.py -v
```

### Running with Coverage

```bash
pytest tests/ --cov=../ --cov-report=html --cov-report=term
```

### Running Specific Test Classes

```bash
# Run only city router tests
pytest tests/test_city.py::TestCityRouter -v

# Run only health router tests
pytest tests/test_health.py::TestHealthRouter -v

# Run only station router tests
pytest tests/test_station.py::TestStationRouter -v
```

## Test Database Configuration

The tests use a separate test database with the following configuration:
- Host: `db_test`
- Database: `test_database`
- User: `test_user`
- Password: `test_password`

Make sure this database is available and accessible during testing.

## Test Features

### Station Router Tests (`test_station.py`)

- **GET /v1/station/current** - Current station data
  - No data scenario (404)
  - With sample data (GeoJSON format)
  - CSV format output
  - With calibration data
  - Specific station IDs
  - Inactive stations (outside last_active window)

- **GET /v1/station/info** - Station information
  - Station not found (404)
  - Existing station info (JSON response)

- **GET /v1/station/calibration** - Calibration data
  - No stations (empty CSV)
  - With calibration data
  - Specific station IDs
  - Data flag (data=false)

- **POST /v1/station/data** - Station data creation
  - Successful station data posting
  - Database verification

- **POST /v1/station/status** - Station status
  - Successful status posting

- **GET /v1/station/all** - All stations
  - No data (empty CSV)
  - With data (CSV format)
  - JSON format output

- **GET /v1/station/topn** - Top N stations
  - Top N stations by dimension

- **GET /v1/station/historical** - Historical data
  - Historical data with station IDs
  - End=current scenario
  - Invalid date format (400 error)

- **Legacy endpoints** - Backward compatibility
  - GET /v1/station/current/all (old endpoint)
  - GET /v1/station/history (old endpoint)

### City Router Tests (`test_city.py`)

- **GET /v1/city/all** - Tests for retrieving all cities
  - No data scenario
  - Single city scenario
  - Multiple cities scenario

- **GET /v1/city/current** - Tests for current city measurements
  - City not found scenario
  - City with no stations
  - City with measurement data
  - City without coordinates
  - Old data filtering
  - Multiple stations aggregation

### Health Router Tests (`test_health.py`)

- **GET /v1/health/simple** - Simple health check
  - Response structure validation
  - Timestamp format validation

- **GET /v1/health/** - Comprehensive health check
  - All components healthy
  - Database unhealthy scenarios
  - Scheduler unhealthy scenarios
  - Multiple scheduler jobs
  - Error handling and response structure

### Test Fixtures

- `sample_data` - Creates test data including countries, cities, stations, and measurements
- `mock_scheduler` - Mocks the APScheduler for health check tests
- `setup_database` - Automatically sets up and tears down the test database

## Test Data

The tests create realistic test data including:
- Countries (Austria, Germany)
- Cities (Vienna, Berlin) with coordinates and timezones
- Stations with locations and firmware information
- Measurements with various sensor values (P1, P2, temperature)
- Calibration measurements and values
- Station status information

## Mocking

The health tests use mocking to avoid external dependencies:
- Database connections are mocked to test failure scenarios
- APScheduler is mocked to test different scheduler states
- External geocoding services are avoided in tests

## Continuous Integration

These tests are designed to run in CI/CD pipelines and provide:
- Fast execution (isolated test database)
- Reliable results (no external dependencies)
- Comprehensive coverage of all endpoints
- Clear error messages for debugging

# luftdaten-api

## About luftdaten-api
luftdaten-api ist an open source database for air quality data build on the FastAPI Framework.

## Documentation

### Development
Development version:

    docker compose up -d


#### Database migration
Setup alembic folder and config files:
    
    docker compose exec app alembic init alembic

Generate and apply migrations:
    
    docker compose exec app alembic revision --autogenerate -m "Initial migration"
    docker compose exec app alembic upgrade head

Rollback migrations:
    
    docker compose exec app alembic downgrade

#### Database reset

    docker compose down
    docker volume ls
    docker volume rm luftdaten-api_postgres_data
    docker compose up -d
    docker compose exec app alembic upgrade head

#### Running Tests

Run all unit tests via Docker:

    docker compose run --rm test

Or use the convenience script:

    ./run_tests.sh

Run specific test files:

    docker compose run --rm test pytest tests/test_city.py -v
    docker compose run --rm test pytest tests/test_health.py -v
    docker compose run --rm test pytest tests/test_station.py -v

Run tests with coverage (requires pytest-cov in requirements.txt):

    docker compose run --rm test pytest tests/ --cov=. --cov-report=html --cov-report=term

The test service uses a separate test database (`db_test`) that is automatically set up and torn down.


#### Deployment

Build and push to Dockerhub.

    docker build -f Dockerfile.prod -t luftdaten/api:tagname --platform linux/amd64 .
    docker push luftdaten/api:tagname

Currently automaticly done by Github Workflow.
Tags:
    - **staging**: latest version for testing
    - **x.x.x**: released versions for production

### Production

Create docker-compose.prod.yml from example-docker-compose.prod.yml by setting the secret key. Then run:

    docker compose -f docker-compose.prod.yml up -d

Create database structure:
    
    docker compose exec app alembic upgrade head    

## API Documentation

Open API Standard 3.1

/docs
https://api.luftdaten.at/docs

## License
This project is licensed under GNU General Public License v3.0.
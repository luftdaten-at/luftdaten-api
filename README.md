# luftdaten-api

## About luftdaten-api
luftdaten-api ist an open source database for air quality data build on the FastAPI Framework.

## Documentation

### Development
Development version:

    docker compose up -d

### Production

Build and push to Dockerhub.

    docker build -f Dockerfile.prod -t luftdaten/api:tagname --platform linux/amd64 .
    docker push luftdaten/api:tagname

Create docker-compose.prod.yml from example-docker-compose.prod.yml by setting the secret key. Then run:

    docker compose -f docker-compose.prod.yml up -d

## API Documentation

Open API Standard 3.1

/docs
https://api.luftdaten.at/docs

## License
This project is licensed under GNU General Public License v3.0.
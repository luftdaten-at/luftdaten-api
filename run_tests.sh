#!/bin/bash

# Script to run unit tests via Docker

echo "Starting test database..."
docker-compose up -d db_test

echo "Waiting for test database to be ready..."
sleep 5

echo "Running unit tests..."
docker-compose run --rm test

echo "Stopping test database..."
docker-compose stop db_test


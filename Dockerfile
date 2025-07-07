# Use an official Python runtime as the base image
FROM python:3.13-alpine

# Set timezone
ENV TZ=Europe/Vienna

# Install required packages
RUN apk update && apk add --no-cache \
    build-base \
    cmake \
    netcat-openbsd

# set env variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set the working directory in the container
WORKDIR /usr/src/app

# Install dependencies
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application code into the container
#COPY ./code .
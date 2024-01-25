# Use an official Python runtime as the base image
FROM python:3-alpine

# Set the working directory in the container
WORKDIR /usr/src/app

# set env variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application code into the container
COPY ./code .

# Expose the port that FastAPI is listening on
EXPOSE 80

# Start the FastAPI application with uvicorn
#CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:80", "main:app"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
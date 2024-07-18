# ./Dockerfile

# Using the official Python image as a base
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

# Copy of requirements and uwsgi
COPY requirements.txt .
COPY uwsgi.ini .
COPY uwsgi.py .

# Installieren Sie die Abhängigkeiten und uWSGI
RUN pip install --no-cache-dir -r requirements.txt uwsgi

# Copy of the app and maybe config and migrations
COPY ./app ./app
#COPY ./migrations ./migrations
#COPY ./config ./config
RUN mkdir -p /app/instance/uploads

# Copy of the scripts and set the execution rights
COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/wait-for-it.sh /wait-for-it.sh
RUN chmod +x /entrypoint.sh /wait-for-it.sh

# We set the entry point script as entry point
#ENTRYPOINT ["/entrypoint.sh"]

# Start command for the container
CMD ["uwsgi", "--ini", "uwsgi.ini"]
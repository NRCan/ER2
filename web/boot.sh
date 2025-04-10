#!/bin/sh
# this script is used to boot a Docker container
. venv/bin/activate
flask translate compile
flask init-db

exec gunicorn -b :<host-port>  --access-logfile - --error-logfile - er2:app

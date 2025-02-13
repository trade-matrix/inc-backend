#!/bin/bash

# Start Celery worker
celery -A your_project worker --loglevel=info &

# Start Celery beat
celery -A your_project beat --loglevel=info &

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $? 
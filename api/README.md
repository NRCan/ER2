# API

Gunicorn is the application server that calls the ER2 API, made using Flask.

Receives client AJAX requests and executes a variety of tasks, including initiating earthquake and flood simulations, checking progress, and querying tracts/blocks. Time-consuming tasks are sent to Redis/Celery for execution.
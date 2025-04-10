# Task queue

The [Celery](http://www.celeryproject.org/) task queue is responsible for executing flood calculations (and later, wildfire). As calculations proceed, the database is updated. These calculations take a significant time, which is why the asynchronous task queue is needed. Full documentation is provided in the main documentation page.
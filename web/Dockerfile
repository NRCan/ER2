FROM python:3.7

WORKDIR /home/er2

# uncomment in production
# RUN adduser -D er2

# Install native libraries; required for numpy and other libraries
# RUN apk --no-cache add musl-dev linux-headers g++

# RUN apk add --no-cache --virtual .build-deps gcc musl-dev

# For work computer only!
COPY ssl-workaround.crt /usr/local/share/ca-certificates/ssl-workaround.crt
RUN update-ca-certificates
ADD pip.conf /etc/pip.conf

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install --upgrade pip
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn pymysql

COPY app app
COPY er2.py config.py boot.sh ./
ADD er2.sqlite ./
RUN chmod +x boot.sh

ENV FLASK_APP er2.py

# Sets the owner of all files in /home/er2 as the new er2 user
# RUN chown -R er2:er2 ./

# Make the er2 user the default for subsequent instructions
# USER er2

EXPOSE <host-port>
ENTRYPOINT ["./boot.sh"]
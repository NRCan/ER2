FROM continuumio/miniconda:latest

# Add the user that will run the app (no need to run as root)
RUN groupadd -r myuser && useradd -r -g myuser myuser

WORKDIR /app

ENV C_FORCE_ROOT true

# WORK COMPUTER ONLY
COPY ssl-workaround.crt ssl-workaround.crt
COPY .condarc /root/.condarc

# Install requirements
COPY environment.yml /app/environment.yml
RUN conda env create -f environment.yml
# RUN echo "source activate base_celery" > ~/.bashrc

# Install app
COPY . /app/
RUN chown -R myuser:myuser /app/*

# activate the environment
ENV PATH /opt/conda/envs/base_celery/bin:$PATH

ENTRYPOINT celery -A tasks worker --loglevel=info
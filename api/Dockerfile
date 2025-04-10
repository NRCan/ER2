FROM continuumio/miniconda:latest

# Add the user that will run the app (no need to run as root)
RUN groupadd -r myuser && useradd -r -g myuser myuser

WORKDIR /app

# WORK COMPUTER ONLY
COPY ssl-workaround.crt ssl-workaround.crt
COPY .condarc /root/.condarc

COPY environment.yml /app/environment.yml
RUN conda env create -f environment.yml
# RUN echo "source activate flood_base" > ~/.bashrc

ENV C_FORCE_ROOT true
ENV FLASK_APP app.py

# Install myapp
COPY . /app/
RUN chown -R myuser:myuser /app/*

# activate the flood_base environment
ENV PATH /opt/conda/envs/flood_base/bin:$PATH

# expose the app port
EXPOSE <host-port>

# run the app server
CMD ["gunicorn", "--bind", ":<host-port>", "--workers", "3", "app:app"]
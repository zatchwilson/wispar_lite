FROM mcr.microsoft.com/devcontainers/python:3.12

ENV PYTHONUNBUFFERED 1

RUN apt-get clean \
    && apt-get update \
    && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends mariadb-server ffmpeg calibre

COPY requirements.txt /tmp/pip-tmp/

RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
   && rm -rf /tmp/pip-tmp

RUN mkdir -p /app/nltk_data && \
   python -c "import nltk; nltk.download('stopwords', download_dir='/app/nltk_data')"
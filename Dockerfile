FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY Pipfile Pipfile.lock ./
RUN pip install --no-cache-dir pipenv \
    && pipenv install --system --deploy

COPY . .

RUN mkdir -p /data /media /playback_output

ENV DATABASE_URL=sqlite:////data/media_library.db \
    SCANNER_MEDIA_ROOT=/media \
    MEDIA_ROOT=/media \
    PLAYBACK_OUTPUT_ROOT=/playback_output \
    FLASK_DEBUG=false

EXPOSE 5000

CMD ["python", "app.py"]

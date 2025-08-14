ARG PYTHON_VERSION=3.12-slim

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir -p /code

WORKDIR /code

COPY requirements.txt /tmp/requirements.txt
RUN set -ex && \
    pip install --upgrade pip && \
    pip install -r /tmp/requirements.txt && \
    rm -rf /root/.cache/
COPY . /code

# Create entrypoint script
RUN echo '#!/bin/sh\nset -e\necho "Running migrations..."\npython manage.py migrate --noinput\necho "Promoting admin users..."\npython manage.py promote_admin\necho "Starting server..."\nexec "$@"' > /code/entrypoint.sh
RUN chmod +x /code/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/code/entrypoint.sh"]
CMD ["gunicorn","--bind",":8000","--workers","2","hello_beomsan.wsgi"]

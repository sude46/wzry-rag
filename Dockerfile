FROM python:3.12-slim

WORKDIR /app
ARG PYPI_MIRROR=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_DEFAULT_INDEX=${PYPI_MIRROR}

RUN pip install --no-cache-dir -i ${PYPI_MIRROR} uv
COPY . .
RUN uv export --frozen --no-dev --no-hashes --no-emit-project > /tmp/requirements.txt \
    && pip install --no-cache-dir -i ${PYPI_MIRROR} -r /tmp/requirements.txt

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

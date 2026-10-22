FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY servicos/ ./servicos/

EXPOSE 8002

CMD ["uvicorn", "servicos.recuperacao.app:app", "--host", "0.0.0.0", "--port", "8002"]

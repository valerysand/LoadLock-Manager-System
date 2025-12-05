FROM python:3.11-slim

WORKDIR /app

# Копируем требования ДО создания пользователя
COPY requirements.txt .

# Устанавливаем зависимости как root (необходимо для системных пакетов)
RUN pip install --no-cache-dir --disable-pip-version-check -q -r requirements.txt

# Копируем приложение
COPY . .

# Создаем непривилегированного пользователя и директории
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/uploads /app/output && \
    chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV PORT=5001

EXPOSE 5001

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5001", "--workers", "2"]

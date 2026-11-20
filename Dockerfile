FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 officeflow
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY docker-entrypoint.sh /usr/local/bin/officeflow-entrypoint
RUN chmod 0755 /usr/local/bin/officeflow-entrypoint \
    && mkdir -p /app/staticfiles \
    && chown -R officeflow:officeflow /app
USER officeflow
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/officeflow-entrypoint"]
CMD ["gunicorn", "officeflow.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "4", "--timeout", "40", "--access-logfile", "-"]

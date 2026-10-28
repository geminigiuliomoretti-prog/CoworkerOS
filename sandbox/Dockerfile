FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn

COPY browser_server.py /app/
RUN mkdir -p /app/downloads

EXPOSE 9333

CMD ["uvicorn", "browser_server:app", "--host", "0.0.0.0", "--port", "9333"]

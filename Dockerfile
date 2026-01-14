FROM python:3.14-alpine

WORKDIR /app

RUN apk add --no-cache \
    g++ \
    make \
    musl-dev \
    && pip install --no-cache-dir --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

ENTRYPOINT ["python", "backend/run.py"]

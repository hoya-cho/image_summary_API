FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

# Download model during build time (optional, can also be done on first run)
# RUN python -c "from transformers import pipeline; pipeline('image-to-text', model='nlpconnect/vit-gpt2-image-captioning')"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 
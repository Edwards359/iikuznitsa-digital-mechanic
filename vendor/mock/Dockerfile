FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mock_ml mock_ml
COPY mock_toir mock_toir
COPY data data
ENV MOCK_DATA_PATH=/srv/data/vehicles.json
EXPOSE 8001
CMD ["uvicorn", "mock_ml.app:app", "--host", "0.0.0.0", "--port", "8001"]

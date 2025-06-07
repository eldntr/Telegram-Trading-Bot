# Auto Trade Bot/dashboard.Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir streamlit pandas
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "dashboard.py"]
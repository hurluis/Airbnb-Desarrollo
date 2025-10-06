FROM python:3.11-slim

WORKDIR /app

# Copiar requirements primero
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el resto de archivos
COPY main.py .
COPY static/ ./static/  

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
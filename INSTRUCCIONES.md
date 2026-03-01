# Instrucciones de ejecución

Pasos para levantar el entorno local: Langfuse, LocalStack y la aplicación Streamlit.

---

## Requisitos previos

- **Docker** y **Docker Compose**
- **Python 3.12.10** (entorno virtual recomendado)
- **Terraform** (para el orquestador IaC)

---

## 1. Langfuse (observabilidad)

Desde la raíz del proyecto:

```bash
cd langfuse
docker compose up -d
```

- Interfaz: **http://localhost:3000**
- Opcional: configura `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` y `LANGFUSE_HOST` en tu `.env` para que la app envíe trazas.

---

## 2. LocalStack (AWS local)

Entra en la carpeta y levanta el compose:

```bash
cd localstack
docker compose up -d
```

- API: **http://localhost:4566**
- El Terraform del proyecto ya apunta a este endpoint para S3, SNS, SQS, DynamoDB, etc.

---

## 3. Aplicación Streamlit

Desde la raíz del proyecto:

```bash
pip install -r requirements.txt
streamlit run app.py
```

- App: **http://localhost:8501**

---

## Orden recomendado

1. `cd langfuse && docker compose up -d`
2. `cd localstack && docker compose up -d`
3. Desde la raíz: `pip install -r requirements.txt && streamlit run app.py`

Para parar servicios: ejecuta `docker compose down` dentro de `langfuse` y de `localstack` cuando termines.

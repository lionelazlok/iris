# Image de l'API FastAPI (Render, Railway, Hugging Face Spaces, Fly.io…)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tools ./tools
COPY streamlit_app.py ./
COPY .streamlit ./.streamlit
COPY docs/STREAMLIT_ABOUT.md docs/results.json ./docs/
RUN useradd -m appuser && mkdir -p data && chown -R appuser /app
USER appuser
ENV PORT=8000
EXPOSE 8000
# MODE=streamlit lance l'interface web au lieu de l'API
CMD ["sh", "-c", "if [ \"$MODE\" = streamlit ]; then streamlit run streamlit_app.py --server.port ${PORT} --server.address 0.0.0.0; else uvicorn app.main:app --host 0.0.0.0 --port ${PORT}; fi"]

# Dashboard in replay mode: no GPU, serves the model answers recorded on the MI300X
# (results/llm_cache.sqlite) plus the backtest and benchmark results.
# Works on any small CPU host, for example a Hugging Face Docker Space (port 7860).
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shelfcast ./shelfcast
COPY data/synthetic-store.json ./data/synthetic-store.json
COPY results ./results
# Must match the model the answers were recorded with (part of the cache key).
ENV SHELFCAST_LLM_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507 \
    PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "python -m shelfcast serve --dataset data/synthetic-store.json --mode replay --port ${PORT}"]

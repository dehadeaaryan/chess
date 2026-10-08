FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends stockfish && rm -rf /var/lib/apt/lists/*
ENV STOCKFISH_PATH=/usr/games/stockfish PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home chessapp
RUN mkdir -p /data && chown chessapp /data
USER chessapp
EXPOSE 8000
CMD ["uvicorn", "chess_game.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]

# Wordsworth — sovereign document straat. Multi-stage: build tools stay in the
# builder; runtime carries the venv + app + the OCR native stack. Non-root.
#
# Serves the API by default (uvicorn wordsworth.serve:app). The same image runs
# the one-shot jobs via its console scripts:
#   wordsworth-init                     # create schema + append-only audit trigger
#   wordsworth-ingest --corpus-dir ...  # run the full straat over a PDF corpus

# ---------- builder ----------
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV UV_NO_CACHE=1

# git: the `zeef` dependency is a git source (see [tool.uv.sources]).
RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Resolve from uv.lock only, no dev deps. Builds+installs the wordsworth package.
RUN uv sync --frozen --no-dev --no-cache \
 && find .venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ---------- runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# OS security patches + the OCR native stack. ocrmypdf (OCR recovery) shells out
# to tesseract + ghostscript; the corpus is Dutch → the `nld` language pack
# (WORDSWORTH_OCR_LANGUAGE default). As root, before the non-root USER.
RUN apt-get update \
 && apt-get -y --no-install-recommends upgrade \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-nld ghostscript \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1000 wordsworth \
 && useradd --no-log-init -u 1000 -g wordsworth -m wordsworth

WORKDIR /app
COPY --from=builder --chown=wordsworth:wordsworth /app/.venv /app/.venv
COPY --chown=wordsworth:wordsworth src ./src
COPY --chown=wordsworth:wordsworth pyproject.toml README.md ./

# venv on PATH → `uvicorn`, `wordsworth-init`, `wordsworth-ingest` resolve.
ENV PATH="/app/.venv/bin:$PATH"
# Fail fast + unbuffered logs for k8s.
ENV PYTHONUNBUFFERED=1

USER wordsworth
EXPOSE 8000

# gunicorn + uvicorn worker with --max-requests: the worker is recycled after
# ~40 requests (jittered), releasing memory so a long ingest run cannot grow the
# process unbounded (pypdf/boto3/client retention). One worker (CPU-bound, single
# replica); generous timeout for slow CPU batches; graceful recycle finishes the
# in-flight request first. init/ingest jobs override this CMD with their own.
CMD ["gunicorn", "wordsworth.serve:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "1", "-b", "0.0.0.0:8000", \
     "--max-requests", "40", "--max-requests-jitter", "10", \
     "--timeout", "1200", "--graceful-timeout", "90"]

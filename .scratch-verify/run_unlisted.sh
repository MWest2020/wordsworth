#!/bin/sh
export WORDSWORTH_HOMELAB_HOSTS=lab.local
export WORDSWORTH_S3_ENDPOINT_URL=http://s3.lab.local:8333
export WORDSWORTH_OPENANONYMISER_URL=http://openanonymiser.lab.local:8080
export WORDSWORTH_OPENSEARCH_URL=http://opensearch.lab.local:9200
export WORDSWORTH_OLLAMA_URL=http://ollama.lab.local:11434
uv run wordsworth-ingest --corpus-dir .scratch-verify/corpus --dossier demo \
  --manifest .scratch-verify/manifest-empty.jsonl --pilot-report .scratch-verify/check.json
echo "EXIT:$?"

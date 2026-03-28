---
description: Start the full Docker Compose development stack and verify health
---

Start the full local development stack and verify all services are healthy.

Run these commands in sequence:
1. `docker compose up -d`
2. Wait 10 seconds for services to initialize
3. `docker compose ps` to show service status
4. `curl -sf http://localhost:9200/_cluster/health` to verify Elasticsearch
5. `docker compose logs --tail=5 temporal` to verify Temporal started

Report which services are healthy and which failed.

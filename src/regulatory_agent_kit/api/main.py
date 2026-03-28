"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="regulatory-agent-kit",
    description="AI-powered regulatory compliance automation API",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}

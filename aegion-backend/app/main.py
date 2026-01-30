"""
Aegion Backend - FastAPI Application Entry Point.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Aegion API",
    description="The governed AI development platform backend.",
    version="0.1.0",
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Aegion Backend",
        "version": "0.1.0",
        "status": "operational"
    }


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy"}

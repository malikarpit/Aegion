"""
OpenTelemetry Instrumentation for Aegion Backend.

Configures distributed tracing with Google Cloud Trace (production) or Console (development).
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from app.core.config import settings

def setup_instrumentation(app):
    """
    Setup OpenTelemetry instrumentation for the FastAPI app.
    """
    # 1. Configure Tracer Provider
    provider = TracerProvider()
    trace.set_tracer_provider(provider)

    # 2. Configure Exporter
    if settings.environment in ['production', 'staging']:
        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            exporter = CloudTraceSpanExporter()
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
        except ImportError:
            # Fallback if GCP package missing
            print("GCP Trace Exporter not found, falling back to Console")
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        # Development: Log traces to console
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # 3. Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # 4. Instrument HTTPX (for outgoing requests)
    HTTPXClientInstrumentor().instrument()

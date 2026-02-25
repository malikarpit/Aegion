
from prometheus_client import Summary, Counter

class MetricsService:
    def __init__(self):
        self.council_duration = Summary('council_duration_seconds', 'Time spent in council sessions')
        self.council_sessions = Counter('council_sessions_total', 'Total council sessions', ['result'])

_metrics_service = MetricsService()

def get_metrics_service():
    return _metrics_service


import pytest
from unittest.mock import MagicMock, patch
from app.services.sentinel.drift import DriftDetector

def test_drift_detection_no_changes():
    """Verify no drift when git status is clean."""
    detector = DriftDetector()
    with patch.object(detector, '_run_git', return_value=""):
        alerts = detector.check_drift(active_session_files=[])
        assert len(alerts) == 0

def test_drift_detection_with_changes():
    """Verify drift alert when file is modified."""
    detector = DriftDetector()
    
    # Mock git output: 'app/core/config.py' is modified
    with patch.object(detector, '_run_git') as mock_git:
        def side_effect(args):
            if "--name-only" in args:
                return "app/core/config.py"
            if "--stat" in args:
                return "1 file changed, 2 insertions(+)"
            return ""
        mock_git.side_effect = side_effect
        
        # Test 1: File NOT in active session -> Drift Alert
        alerts = detector.check_drift(active_session_files=[])
        assert len(alerts) == 1
        assert alerts[0].file_path == "app/core/config.py"
        assert alerts[0].severity == "high"  # config is critical
        
        # Test 2: File IS in active session -> No Alert
        alerts_valid = detector.check_drift(active_session_files=["app/core/config.py"])
        assert len(alerts_valid) == 0

from app.services import model_monitor


def test_model_monitor_score_drift():
    model_monitor.reset()
    model_monitor.configure_baseline(0.2, 0.05, 100.0)
    for _ in range(30):
        model_monitor.record("D001", 0.9, 10.0, "P1")
    snapshot = model_monitor.snapshot()
    assert snapshot["count"] == 30
    assert "score_drift" in snapshot["alerts"]
    assert snapshot["score"]["mean"] > 0.8
    model_monitor.reset()

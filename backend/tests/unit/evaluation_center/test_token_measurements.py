from app.platform.observability.metrics import token_metrics


def test_partial_usage_keeps_known_tokens_without_claiming_complete_totals():
    metrics = token_metrics([
        {"event_type": "model_call", "http_attempted": True,
         "actual_input_tokens": 10, "actual_output_tokens": 4},
        {"event_type": "model_call", "http_attempted": True,
         "actual_input_tokens": 20, "actual_output_tokens": None},
        {"event_type": "model_call", "http_attempted": False},
    ])
    assert metrics["model_call_count"] == 2
    assert metrics["token_usage_missing_calls"] == 1
    assert metrics["actual_input_tokens"] is None
    assert metrics["actual_output_tokens"] is None
    assert metrics["partial_actual_input_tokens"] == 30
    assert metrics["partial_actual_output_tokens"] == 4

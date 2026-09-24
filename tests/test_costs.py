from api.calculations import calculate_repair_metrics


def test_estimated_cost_inr_is_present_and_matches_usd_rate():
    metrics = calculate_repair_metrics(5.0)

    assert hasattr(metrics, "estimated_cost_inr")
    assert metrics.estimated_cost_inr == round(metrics.estimated_cost_usd * 83.0, 2)

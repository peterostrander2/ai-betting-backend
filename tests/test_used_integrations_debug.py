from core.telemetry import apply_used_integrations_debug


def test_used_integrations_debug_only():
    result = {}
    apply_used_integrations_debug(result, {"playbook"}, debug_mode=False)
    assert "debug" not in result

    apply_used_integrations_debug(result, {"playbook"}, debug_mode=True)
    assert "debug" in result
    assert result["debug"]["used_integrations"] == ["playbook"]

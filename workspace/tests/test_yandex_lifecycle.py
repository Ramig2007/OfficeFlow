import pytest

from scripts.configure_yandex_lifecycle import (
    RULE_ID,
    build_lifecycle,
    normalized_prefix,
    verify_lifecycle,
)


def test_builds_30_day_rule_and_preserves_unrelated_rules():
    existing = {
        "Rules": [
            {
                "ID": "other-rule",
                "Status": "Enabled",
                "Filter": {"Prefix": "logs/"},
                "Expiration": {"Days": 90},
            }
        ]
    }
    result = build_lifecycle(existing, "officeflow/daily")
    assert len(result["Rules"]) == 2
    assert result["Rules"][0] == existing["Rules"][0]
    rule = result["Rules"][1]
    assert rule["ID"] == RULE_ID
    assert rule["Status"] == "Enabled"
    assert rule["Filter"] == {"Prefix": "officeflow/daily/"}
    assert rule["Expiration"] == {"Days": 30}
    assert rule["AbortIncompleteMultipartUpload"] == {"DaysAfterInitiation": 7}


def test_replaces_only_the_previous_officeflow_rule():
    existing = {
        "Rules": [
            {"ID": RULE_ID, "Status": "Disabled", "Filter": {"Prefix": "old/"}},
            {"ID": "keep-me", "Status": "Enabled", "Filter": {"Prefix": "keep/"}},
        ]
    }
    result = build_lifecycle(existing, "officeflow/daily")
    assert [rule["ID"] for rule in result["Rules"]] == ["keep-me", RULE_ID]


def test_versioned_bucket_expires_noncurrent_versions_too():
    result = build_lifecycle({"Rules": []}, "officeflow/daily", {"Status": "Enabled"})
    assert result["Rules"][0]["NoncurrentVersionExpiration"] == {"NoncurrentDays": 30}


def test_suspended_versioning_also_expires_noncurrent_versions():
    result = build_lifecycle({"Rules": []}, "officeflow/daily", {"Status": "Suspended"})
    assert result["Rules"][0]["NoncurrentVersionExpiration"] == {"NoncurrentDays": 30}


def test_unversioned_bucket_does_not_add_noncurrent_rule():
    result = build_lifecycle({"Rules": []}, "officeflow/daily", {})
    assert "NoncurrentVersionExpiration" not in result["Rules"][0]


def test_normalizes_prefix_and_rejects_empty_or_traversal():
    assert normalized_prefix("/officeflow/daily/") == "officeflow/daily/"
    with pytest.raises(ValueError):
        normalized_prefix("")
    with pytest.raises(ValueError):
        normalized_prefix("officeflow/../private")


def test_verifies_expected_rule():
    config = build_lifecycle({"Rules": []}, "officeflow/daily", {"Status": "Enabled"})
    verify_lifecycle(config, "officeflow/daily", {"Status": "Enabled"})


def test_verification_rejects_wrong_retention():
    config = build_lifecycle({"Rules": []}, "officeflow/daily")
    config["Rules"][0]["Expiration"]["Days"] = 90
    with pytest.raises(ValueError, match="30 days"):
        verify_lifecycle(config, "officeflow/daily")


def test_refuses_to_exceed_s3_lifecycle_rule_limit():
    existing = {"Rules": [{"ID": f"rule-{i}"} for i in range(1000)]}
    with pytest.raises(ValueError, match="1000 lifecycle rules"):
        build_lifecycle(existing, "officeflow/daily")

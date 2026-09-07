from privacy.project_policy import (
    ProjectPrivacyMode,
    outbound_data_class,
    resolve_project_policy,
)
from privacy.router import (
    DataClass,
    DestinationClass,
    PrivacyRouter,
)


def test_unknown_mode_fails_closed():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="p1",
        privacy_mode="banana",
    )

    assert policy.mode == ProjectPrivacyMode.PRIVATE


def test_private_project_blocks_public_model_egress():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="private-project",
        privacy_mode="private",
    )

    ctx = policy.context_for(DataClass.PUBLIC)

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL,
    )

    assert decision.allowed is False


def test_private_project_still_allows_world_read():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="private-project",
        privacy_mode="private",
    )

    ctx = policy.context_for(DataClass.PRIVATE)

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.WORLD_READ,
    )

    assert decision.allowed is True


def test_public_data_only_allows_public_model_egress():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="research",
        privacy_mode="public_data_only",
    )

    ctx = policy.context_for(DataClass.PUBLIC)

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL,
    )

    assert decision.allowed is True


def test_public_data_only_blocks_private_model_egress():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="research",
        privacy_mode="public_data_only",
    )

    ctx = policy.context_for(DataClass.PRIVATE)

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL,
    )

    assert decision.allowed is False


def test_standard_still_blocks_private_data():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="normal",
        privacy_mode="standard",
    )

    ctx = policy.context_for(DataClass.PRIVATE)

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL,
    )

    assert decision.allowed is False


def test_explicit_share_requires_consent():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="private-project",
        privacy_mode="private",
    )

    ctx = policy.context_for(
        outbound_data_class(
            policy,
            contains_private_project_data=True,
            explicit_share=True,
        )
    )

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL,
    )

    assert decision.allowed is False
    assert decision.reason == (
        "private_build_mode_blocks_outbound"
    )


def test_private_explicit_share_with_consent_allowed():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="private-project",
        privacy_mode="private",
        consent_token="test-consent",
    )

    ctx = policy.context_for(
        DataClass.EXPLICITLY_SHARED
    )

    decision = PrivacyRouter().decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL,
    )

    assert decision.allowed is True
    assert decision.reason == "explicit_user_consent"


def test_classifier_defaults_private_content_to_private():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="p1",
        privacy_mode="standard",
    )

    assert outbound_data_class(
        policy,
        contains_private_project_data=True,
    ) == DataClass.PRIVATE


def test_classifier_marks_nonprivate_content_public():
    policy = resolve_project_policy(
        user_id="u1",
        project_id="p1",
        privacy_mode="public_data_only",
    )

    assert outbound_data_class(
        policy,
        contains_private_project_data=False,
    ) == DataClass.PUBLIC

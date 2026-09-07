from privacy.router import (
    AuditLog,
    DataClass,
    DestinationClass,
    PrivacyContext,
    PrivacyRouter
)


def router(tmp_path):
    return PrivacyRouter(
        AuditLog(tmp_path / "audit.jsonl")
    )


def test_world_can_come_in(tmp_path):

    r = router(tmp_path)

    ctx = PrivacyContext(
        user_id="user1",
        project_id="project1",
        data_class=DataClass.PRIVATE,
        private_build_mode=True
    )

    assert r.decide(
        ctx,
        DestinationClass.WORLD_READ
    ).allowed


def test_private_data_cannot_leave(tmp_path):

    r = router(tmp_path)

    ctx = PrivacyContext(
        "user1",
        "project1",
        DataClass.PRIVATE
    )

    assert not r.decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL
    ).allowed


def test_private_mode_blocks_external_models(tmp_path):

    r = router(tmp_path)

    ctx = PrivacyContext(
        "user1",
        "project1",
        DataClass.PUBLIC,
        True
    )

    assert not r.decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL
    ).allowed


def test_user_can_explicitly_share(tmp_path):

    r = router(tmp_path)

    ctx = PrivacyContext(
        "user1",
        "project1",
        DataClass.EXPLICITLY_SHARED,
        True,
        "consent-123"
    )

    assert r.decide(
        ctx,
        DestinationClass.EXTERNAL_MODEL
    ).allowed

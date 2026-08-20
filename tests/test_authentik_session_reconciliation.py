from scripts.operations.authentik_session_reconciliation import TARGET_DURATION, TARGETS, reconcile, verify


class Stage:
    def __init__(self, name, duration):
        self.name = name
        self.session_duration = duration
        self.saved = False

    def save(self, update_fields=None):
        self.saved = True


def test_reconcile_updates_only_sea_speed_login_stages():
    stages = [
        Stage("sea-speed-authentication-login", "hours=12"),
        Stage("sea-speed-enrollment-login", "hours=12"),
        Stage("other-login", "hours=12"),
    ]

    changed = reconcile(stages)

    assert changed == 2
    assert all(stage.session_duration == TARGET_DURATION for stage in stages[:2])
    assert stages[2].session_duration == "hours=12"


def test_verify_accepts_target_state():
    verify([Stage(name, TARGET_DURATION) for name in TARGETS])

from scripts import seed_dev


def test_seed_requires_explicit_environment(monkeypatch, capsys):
    for name in ("DEV_SEED_USERNAME", "DEV_SEED_EMAIL", "DEV_SEED_PASSWORD"):
        monkeypatch.delenv(name, raising=False)

    assert seed_dev.load_seed_request() is None
    assert "DEV_SEED_PASSWORD" in capsys.readouterr().out


def test_seed_never_prints_password(monkeypatch, capsys):
    password = "StrongPassword1!"
    monkeypatch.setenv("DEV_SEED_USERNAME", "local_admin")
    monkeypatch.setenv("DEV_SEED_EMAIL", "local@example.com")
    monkeypatch.setenv("DEV_SEED_PASSWORD", password)

    request = seed_dev.load_seed_request()

    assert request is not None
    assert request.password == password
    assert password not in capsys.readouterr().out

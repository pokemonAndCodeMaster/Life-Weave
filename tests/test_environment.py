from src.config import ConfigManager
from src.config.environment import get_env


def test_current_environment_and_legacy_installation_aliases(monkeypatch):
    monkeypatch.delenv('LIFEWEAVE_DB_NAME', raising=False)
    monkeypatch.setenv('GONGZUO_DB_NAME', 'existing_database')
    assert get_env('LIFEWEAVE_DB_NAME') == 'existing_database'
    assert ConfigManager().get_database_by_alias()['database'] == 'existing_database'
    monkeypatch.setenv('LIFEWEAVE_DB_NAME', 'selected_database')
    assert get_env('LIFEWEAVE_DB_NAME') == 'selected_database'
    assert ConfigManager().get_database_by_alias()['database'] == 'selected_database'

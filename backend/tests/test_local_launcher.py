"""Do not launch any server until environment/database preparation succeeds."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('local_launcher', Path(__file__).resolve().parents[2] / 'run.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


@pytest.fixture
def local_launcher(monkeypatch):
    socket = Mock()
    socket.__enter__ = Mock(return_value=socket)
    socket.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(launcher.socket, 'socket', Mock(return_value=socket))
    popen = Mock(side_effect=AssertionError('A server must not start in this test'))
    monkeypatch.setattr(launcher.subprocess, 'Popen', popen)
    return popen, socket


def test_setup_only_prepares_database_and_dev_dependencies_without_starting_servers(local_launcher, monkeypatch):
    popen, _ = local_launcher
    prepare = Mock()
    monkeypatch.setattr(launcher, 'prepare_local', prepare)
    monkeypatch.setattr(launcher.sys, 'argv', ['run.py', '--setup-only', '--dev'])
    assert launcher.main() == 0
    prepare.assert_called_once_with(True)
    popen.assert_not_called()


def test_database_failure_stops_startup(local_launcher, monkeypatch, capsys):
    popen, _ = local_launcher
    monkeypatch.setattr(launcher, 'prepare_local', Mock(side_effect=RuntimeError('MySQL chưa bật')))
    monkeypatch.setattr(launcher.sys, 'argv', ['run.py', '--no-browser'])
    assert launcher.main() == 1
    assert 'MySQL chưa bật' in capsys.readouterr().err
    popen.assert_not_called()


def test_busy_port_prevents_any_environment_or_database_changes(local_launcher, monkeypatch):
    popen, socket = local_launcher
    socket.bind.side_effect = OSError('Address already in use')
    prepare = Mock()
    monkeypatch.setattr(launcher, 'prepare_local', prepare)
    monkeypatch.setattr(launcher.sys, 'argv', ['run.py'])
    assert launcher.main() == 1
    prepare.assert_not_called()
    popen.assert_not_called()

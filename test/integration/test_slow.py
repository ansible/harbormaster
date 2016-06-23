import os
import pytest

from scripttest import TestFileEnvironment as ScriptTestEnvironment  # rename to avoid pytest collect warning


def project_dir(name):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(test_dir, 'projects', name)


@pytest.mark.timeout(240)
def test_build_minimal_docker_container():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'build', cwd=project_dir('minimal'), expect_stderr=True)
    assert "Aborting on container exit" in result.stdout
    assert "Exported minimal-minimal with image ID " in result.stderr


def test_run_minimal_docker_container():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'run', cwd=project_dir('minimal'))
    assert "ansible_minimal_1 exited with code 0" in result.stdout


def test_shipit_minimal_docker_container():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'shipit', 'kube', cwd=project_dir('minimal'), expect_error=True)
    assert result.returncode == 1
    assert "Role minimal created" in result.stderr

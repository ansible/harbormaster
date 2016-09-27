import os
import pytest

from scripttest import TestFileEnvironment as ScriptTestEnvironment  # rename to avoid pytest collect warning


def project_dir(name):
    test_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(test_dir, 'projects', name)


@pytest.mark.timeout(240)
def test_build_minimal_docker_container():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'build', '--flatten', cwd=project_dir('minimal'), expect_stderr=True)
    assert "Aborting on container exit" in result.stdout
    assert "Exported minimal-minimal with image ID " in result.stderr

def test_build_with_variables():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'build', '--save-build-container', '--with-variables', 'foo=bar',
                     'bar=baz', cwd=project_dir('minimal'), expect_stderr=True)
    assert "Aborting on container exit" in result.stdout
    assert "Exported minimal-minimal with image ID " in result.stderr

    result = env.run('docker', 'inspect', '--format="{{ .Config.Env }}"', 'ansible_ansible-container_1',
                     expect_stderr=True)
    assert "foo=bar" in result.stdout
    assert "bar=baz" in result.stdout

def test_build_with_volumes():
    env = ScriptTestEnvironment()
    volume_string = "{0}:{1}:{2}".format(os.getcwd(), '/projectdir', 'ro')
    result = env.run('ansible-container', 'build', '--save-build-container', '--with-volumes', volume_string,
                     cwd=project_dir('minimal'), expect_stderr=True)
    assert "Aborting on container exit" in result.stdout
    assert "Exported minimal-minimal with image ID " in result.stderr
    result = env.run('docker', 'inspect',
                     '--format="{{range .Mounts}}{{ .Source }}:{{ .Destination }}:{{ .Mode}} {{ end }}"',
                     'ansible_ansible-container_1', expect_stderr=True)
    volumes = result.stdout.split(' ')
    assert volume_string in volumes

def test_run_minimal_docker_container():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'run', cwd=project_dir('minimal'), expect_stderr=True)
    assert "ansible_minimal_1 exited with code 0" in result.stdout


def test_run_minimal_docker_container_in_detached_mode():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal'), expect_stderr=True)
    assert "Deploying application in detached mode" in result.stderr


@pytest.mark.timeout(240)
def test_stop_minimal_docker_container():
    env = ScriptTestEnvironment()
    env.run('ansible-container', 'build', '--flatten',
            cwd=project_dir('minimal_sleep'), expect_stderr=True)
    env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    result = env.run('ansible-container', 'stop', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    assert "Stopping ansible_minimal1_1 ... done" in result.stderr
    assert "Stopping ansible_minimal2_1 ... done" in result.stderr


def test_stop_service_minimal_docker_container():
    env = ScriptTestEnvironment()
    env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    result = env.run('ansible-container', 'stop', 'minimal1',
                     cwd=project_dir('minimal_sleep'), expect_stderr=True)
    assert "Stopping ansible_minimal1_1 ... done" in result.stderr
    assert "Stopping ansible_minimal2_1 ... done" not in result.stderr


def test_force_stop_minimal_docker_container():
    env = ScriptTestEnvironment()
    env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    result = env.run('ansible-container', 'stop', '--force',
                     cwd=project_dir('minimal_sleep'), expect_stderr=True)
    assert "Killing ansible_minimal1_1 ... done" in result.stderr
    assert "Killing ansible_minimal2_1 ... done" in result.stderr


def test_force_stop_service_minimal_docker_container():
    env = ScriptTestEnvironment()
    env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    result = env.run('ansible-container', 'stop', '--force', 'minimal1',
                     cwd=project_dir('minimal_sleep'), expect_stderr=True)
    assert "Killing ansible_minimal1_1 ... done" in result.stderr
    assert "Killing ansible_minimal2_1 ... done" not in result.stderr


def test_restart_minimal_docker_container():
    env = ScriptTestEnvironment()
    env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    result = env.run('ansible-container', 'restart', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    assert "Restarting ansible_minimal1_1 ... done" in result.stderr
    assert "Restarting ansible_minimal2_1 ... done" in result.stderr
    env.run('ansible-container', 'stop', cwd=project_dir('minimal_sleep'),
            expect_stderr=True)


def test_restart_service_minimal_docker_container():
    env = ScriptTestEnvironment()
    env.run('ansible-container', 'run', '--detached', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    result = env.run('ansible-container', 'restart', 'minimal1', cwd=project_dir('minimal_sleep'), expect_stderr=True)
    assert "Restarting ansible_minimal1_1 ... done" in result.stderr
    assert "Restarting ansible_minimal2_1 ... done" not in result.stderr


def test_build_with_var_file():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', '--var-file=devel.yaml','--debug', 'build',
                     cwd=project_dir('vartest'), expect_stderr=True)
    assert "ansible_ansible-container_1 exited with code 0" in result.stderr
    assert "Exporting built containers as images..." in result.stderr

def test_run_with_var_file():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', '--var-file=devel.yaml', '--debug', 'run',
                     cwd=project_dir('vartest'), expect_stderr=True)
    assert "ansible_db_1 exited with code 0" in result.stdout
    assert "ansible_web_1 exited with code 0" in result.stdout

def test_install_role_requirements():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', '--debug', 'build',
                     cwd=project_dir('requirements'), expect_stderr=True)
    print result.stdout
    print "YYYYYYYYYYYYYYYYYYYYYYYYYYY\n"
    print result.stderr
    assert "ansible-role-apache was installed successfully" in result.stdout

@pytest.mark.timeout(240)
def test_setting_ansible_container_envar():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', '--debug', 'build',
                     cwd=project_dir('environment'), expect_stderr=True)
    assert "web MYVAR=foo ANSIBLE_CONTAINER=1" in result.stdout
    assert "db MYVAR=foo ANSIBLE_CONTAINER=1" in result.stdout
    assert "mw ANSIBLE_CONTAINER=1" in result.stdout

#def test_shipit_minimal_docker_container():
#    env = ScriptTestEnvironment()
#    result = env.run('ansible-container', 'shipit', 'kube', cwd=project_dir('minimal'), expect_error=True)
#    assert result.returncode == 1
#    assert "Role minimal created" in result.stderr

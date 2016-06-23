from scripttest import TestFileEnvironment as ScriptTestEnvironment  # rename to avoid pytest collect warning


def test_invalid_command_fails():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'invalid', expect_error=True)
    assert result.returncode == 2
    assert len(result.stdout) == 0
    assert "ansible-container: error: argument subcommand: invalid choice: 'invalid'" in result.stderr


def test_no_command_shows_help():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', expect_error=True)
    assert result.returncode == 2
    assert len(result.stdout) == 0
    assert "ansible-container: error: too few arguments" in result.stderr


def test_help_command_shows_help():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'help')
    assert "usage: ansible-container" in result.stdout


def test_help_option_shows_help():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', '--help')
    assert "usage: ansible-container" in result.stdout


def test_help_option_shows_help_for_run_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'run', '--help')
    assert "usage: ansible-container run" in result.stdout


def test_help_option_shows_help_for_help_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'help', '--help')
    assert "usage: ansible-container help" in result.stdout


def test_help_option_shows_help_for_shipit_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'shipit', '--help')
    assert "usage: ansible-container shipit" in result.stdout

def test_help_option_shows_help_for_shipit_engine_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'shipit', 'kube', '--help')
    assert "usage: ansible-container shipit kube" in result.stdout

def test_help_option_shows_help_for_init_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'init', '--help')
    assert "usage: ansible-container init" in result.stdout


def test_help_option_shows_help_for_build_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'build', '--help')
    assert "usage: ansible-container build" in result.stdout


def test_help_option_shows_help_for_push_command():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'push', '--help')
    assert "usage: ansible-container push" in result.stdout


def test_run_in_uninitialized_directory_fails():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'run', expect_error=True)
    assert result.returncode == 1
    assert result.stdout == ''
    assert "No Ansible Container project data found" in result.stderr


def test_shipit_in_uninitialized_directory_fails():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'shipit', 'kube', expect_error=True)
    assert result.returncode == 1
    assert result.stdout == ''
    assert "No Ansible Container project data found" in result.stderr


def test_init_empty_directory():
    env = ScriptTestEnvironment()
    result = env.run('ansible-container', 'init', expect_stderr=True)
    assert result.stdout == ''
    assert "Ansible Container initialized" in result.stderr

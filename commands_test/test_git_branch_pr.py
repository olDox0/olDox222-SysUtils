from click.testing import CliRunner
from unittest.mock import patch

from doxoade.commands.git_branch import branch
from doxoade.commands.git_pr import pr


@patch('doxoade.commands.git_branch._run_git_command')
def test_branch_list_uses_structured_render(mock_git):
    mock_git.side_effect = [
        '',
        '*main\torigin/main\tb4f28c9\tfeat: algo\n feature/x\t\ta1b2c3d\twip',
    ]
    runner = CliRunner()
    result = runner.invoke(branch, ['--list'])

    assert result.exit_code == 0
    assert 'HEAD Branch' in result.output
    assert 'main' in result.output


@patch('doxoade.commands.git_pr._run_git_command')
def test_pr_open_generates_compare_url(mock_git):
    mock_git.side_effect = [
        'feature/x',
        "abc123",
        'git@github.com:org/projeto.git',
        None,
    ]
    runner = CliRunner()
    result = runner.invoke(pr, ['--open', '--base', 'main'])

    assert result.exit_code == 0
    assert 'https://github.com/org/projeto/compare/main...feature/x?expand=1' in result.output


@patch('doxoade.commands.git_pr._run_git_command')
def test_pr_template_prints_commit_bullets(mock_git):
    mock_git.side_effect = [
        'feature/y',
        "abc123",
        'https://github.com/org/projeto.git',
        None,
        'a1b2c3 feat: criar fluxo\nd4e5f6 fix: corrigir merge',
    ]
    runner = CliRunner()
    result = runner.invoke(pr, ['--template', '--base', 'main'])

    assert result.exit_code == 0
    assert 'Título:' in result.output
    assert '- feat: criar fluxo' in result.output

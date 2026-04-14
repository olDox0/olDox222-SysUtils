from unittest.mock import patch

from doxoade.diagnostic.inspector import SystemInspector


@patch('doxoade.diagnostic.inspector._run_git_command')
def test_origin_main_delta_collects_ahead_behind_and_updates(mock_git):
    mock_git.side_effect = [
        '',
        '2',
        '1',
        'a1b2c3 feat: A\nd4e5f6 fix: B',
        'M\tdoxoade/commands/save.py\nA\tdoxoade/commands/git_pr.py',
    ]

    data = SystemInspector()._get_origin_main_delta('codex/branch')

    assert data['base_ref'] == 'origin/main'
    assert data['ahead'] == 2
    assert data['behind'] == 1
    assert len(data['updates']) == 2
    assert data['changed_files'][0].startswith('M\t')

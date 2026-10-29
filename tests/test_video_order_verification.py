"""Native order must agree with the archive after a video settings write."""
import pytest

from qlab_mcp.video_editing import verify_video


@pytest.mark.parametrize('section,live_key', [
    ('stages', 'stages'), ('routes', 'routes'), ('inputs', 'input_patches'),
])
def test_native_verifier_rejects_same_objects_in_different_order(section, live_key):
    expected = [{'id': 'A', 'name': 'First'}, {'id': 'B', 'name': 'Second'}]
    summary = dict(stages=[], routes=[], inputs=[])
    summary[section] = expected
    live = dict(stages=[], routes=[], input_patches=[])
    live[live_key] = [{'uniqueID': x['id'], 'name': x['name']} for x in reversed(expected)]

    class Reader:
        def get_workspace_settings(self, *args, **kwargs):
            return {'sections': {'video': live}}

    with pytest.raises(ValueError, match=f'Native video {section} order'):
        verify_video(Reader(), 'workspace', summary)


def test_native_verifier_accepts_matching_input_order():
    live = dict(stages=[], routes=[], input_patches=[{'uniqueID': 'A'}, {'uniqueID': 'B'}])

    class Reader:
        def get_workspace_settings(self, *args, **kwargs):
            return {'sections': {'video': live}}

    assert verify_video(Reader(), 'workspace', dict(stages=[], routes=[], inputs=[
        {'id': 'A'}, {'id': 'B'},
    ])) is live

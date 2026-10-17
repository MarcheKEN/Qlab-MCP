from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from qlab_mcp.cues.visual import VisualCuesMixin


class Reader(VisualCuesMixin):
    def __init__(self, names=None, families=None):
        self.names = ['HelveticaNeue', 'HelveticaNeue-Bold'] if names is None else names
        self.families = {'Helvetica Neue': ['Regular', 'Bold']} if families is None else families
        self.reads = []

    def _resolve_workspace_id_strict(self, workspace):
        return workspace

    def _request_tcp(self, address, **kwargs):
        self.reads.append((address, kwargs))
        return SimpleNamespace(data=self.names if address == '/fontNames' else self.families)


def test_font_inventory_uses_both_native_tcp_getters():
    reader = Reader()
    result = reader.get_fonts('ws')
    assert result.font_names == reader.names
    assert result.families_and_styles == reader.families
    assert reader.reads == [('/fontNames', {'workspace_id': 'ws'}),
                            ('/fontFamiliesAndStyles', {'workspace_id': 'ws'})]


@pytest.mark.parametrize('names,families', [([True], {'Helvetica': ['Regular']}),
                                          (['Helvetica'], {'Helvetica': [False]}),
                                          (['Helvetica'], []), ([''], {})])
def test_font_inventory_rejects_malformed_native_data(names, families):
    with pytest.raises(ValidationError):
        Reader(names, families).get_fonts('ws')

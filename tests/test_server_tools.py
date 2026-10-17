from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp.utilities.mcp_server_config.v1.mcp_server_config import MCPServerConfig
import pytest

import qlab_mcp.server as server_module
from qlab_mcp.errors import OscTimeoutError, QLabReplyError
from qlab_mcp.server import (
    CHECK_CONNECTION_TIMEOUT,
    CREATE_CUES_TIMEOUT,
    CUE_DETAILS_TIMEOUT,
    QUERY_CUES_TIMEOUT,
    UPDATE_CUES_TIMEOUT,
    WORKSPACE_OVERVIEW_TIMEOUT,
    WORKSPACE_STATUS_TIMEOUT,
    WORKSPACE_SETTINGS_TIMEOUT,
    WRITE_READINESS_TIMEOUT,
    _run_tool,
    mcp,
    qlab_get_workspace_overview,
    qlab_get_workspace_status,
    qlab_get_workspace_audio_settings,
    qlab_get_workspace_general_settings,
    qlab_get_workspace_light_settings,
    qlab_get_workspace_midi_settings,
    qlab_get_workspace_network_settings,
    qlab_get_workspace_video_settings,
    qlab_get_cue_details,
    qlab_query_cues,
)
from qlab_mcp.write.registry import UPDATE_PROFILES
from qlab_mcp.server_responses import overview_success_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NOISE_KEYS: frozenset[str] = frozenset()
EXPECTED_FASTMCP_TOOL_CONTRACTS = {'qlab_get_fonts': {
    'title': 'Get QLab Fonts', 'timeout': 20.0,
    'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': True},
    'tags': ['inventory', 'qlab', 'safe-read', 'text'],
    'input_schema_hash': 'c6bb5fac6574ff867aa6177017ff6d973966fb08778a28b6859f282ad5ed4d46',
    'output_schema_hash': '927ec460a5c728ff3f27b0ae47a844cc49dea30afb734be0b993b5db4e27b4a2'}, 'qlab_analyze_audio_file': {
    'title': 'Analyze QLab Audio File', 'timeout': 300.0,
    'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': True},
    'tags': ['audio', 'media', 'qlab', 'safe-read'],
    'input_schema_hash': 'b81c1228edc65d68ce2df3e9a5745304b1b6f6999fa9e7056bd56c5bd1e41b98',
    'output_schema_hash': 'd640e14de321928e12a8a1d0e83a25cc082c2d9c089363012b498a3feded90a9'}, 'qlab_search_media_files': {'annotations': {'destructiveHint': False,
                 'idempotentHint': True,
                 'openWorldHint': True,
                 'readOnlyHint': True},
 'input_schema_hash': '03550e79d743be6f9f0bb7eece2d966c01a4bdee3649f603ea7965ac2d33f780',
 'output_schema_hash': '82ef96cebaf5fbe16269fd18b0240d78f5b9b90a4155a17eb797115b09148ecf',
 'tags': ['media', 'qlab', 'safe-read'],
 'timeout': 6.0,
 'title': 'Search QLab Media Files'},
'qlab_check_connection': {'annotations': {'destructiveHint': False,
                                           'idempotentHint': True,
                                           'openWorldHint': True,
                                           'readOnlyHint': True},
                           'input_schema_hash': 'c8967eca6cd7a45b2f08cc835ff932aea3551d133cc6fd5c8388ffc177e44b83',
                           'output_schema_hash': 'abf13920f210805507d32c24c3166d28c8dd6fdbfe04b50678924063d4508e56',
                           'tags': ['diagnostics', 'orientation', 'qlab', 'safe-read'],
                           'timeout': 6.0,
                           'title': 'Check QLab Connection'},
 'qlab_check_write_readiness': {'annotations': {'destructiveHint': False,
                                                'idempotentHint': True,
                                                'openWorldHint': True,
                                                'readOnlyHint': True},
                                'input_schema_hash': 'a100d2c71d8a6573be48039f083c85ed16c495c4b69cc2a248b81336bb589578',
                                'output_schema_hash': '0f27f2df78299a76f441eeb8d81064c38cda1bdf763bddb1f5ae79b67451de26',
                                'tags': ['diagnostics', 'qlab', 'safe-read', 'write-mode'],
                                'timeout': 6.0,
                                'title': 'Check QLab Write Readiness'},
 'qlab_create_cue_lists': {'annotations': {'destructiveHint': False,
                                           'idempotentHint': False,
                                           'openWorldHint': True,
                                           'readOnlyHint': False},
                           'input_schema_hash': '90bbee12d7a6bab355ea760376f920567635f753f6e19542b84569779f57f6bd',
                           'output_schema_hash': 'c6592509ce436e5c44598a12d349ff905e8bc82aa4681d5a07cc48b2d017d6a2',
                           'tags': ['batch-create',
                                    'cue-list-create',
                                    'gated-write',
                                    'qlab',
                                    'write-mode'],
                           'timeout': 180.0,
                           'title': 'Create QLab Cue Lists'},
 'qlab_create_cues': {'annotations': {'destructiveHint': False,
                                      'idempotentHint': False,
                                      'openWorldHint': True,
                                      'readOnlyHint': False},
                      'input_schema_hash': '8061059f52cb97fb1010a76d393ca1c3453df54e0bb73acc834a195bfeb0d31c',
                      'output_schema_hash': 'd87db629f7d801ce945ea30019b2f64dfb35a00d1a5cd54ec92db9c1f94d26dc',
                      'tags': ['batch-create', 'cue-create', 'gated-write', 'qlab', 'write-mode'],
                      'timeout': 300.0,
                      'title': 'Create QLab Cues'},
 'qlab_delete_cues': {'annotations': {'destructiveHint': True,
                                      'idempotentHint': False,
                                      'openWorldHint': True,
                                      'readOnlyHint': False},
                      'input_schema_hash': 'b099773e8b5bbdfb6fa19ddcebcdf8d128e50c49145b96a52334d9acaef27ee7',
                      'output_schema_hash': '9f3062beefe3ed6e8b398b47c875e5ce478e424faa893f08a10ce21ebd604ba7',
                      'tags': ['cue-delete', 'gated-write', 'qlab', 'write-mode'],
                      'timeout': 180.0,
                      'title': 'Delete QLab Cues'},
 'qlab_edit_audio_cues': {'annotations': {'destructiveHint': True,
                                          'idempotentHint': False,
                                          'openWorldHint': True,
                                          'readOnlyHint': False},
                          'input_schema_hash': 'dfd145869ade3ae3f7f30ba77405b0744b192cdc585cbffeeb334d35e8302c59',
                          'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                          'tags': ['audio',
                                   'batch-edit',
                                   'cue-edit',
                                   'gated-write',
                                   'qlab',
                                   'write-mode'],
                          'timeout': 180.0,
                          'title': 'Edit QLab Audio Cues'},
 'qlab_edit_audio_output_patch': {'annotations': {'destructiveHint': True,
                                                  'idempotentHint': False,
                                                  'openWorldHint': True,
                                                  'readOnlyHint': False},
                                  'input_schema_hash': 'cc68b39dd9b8d55f94f0e67836bdec6574e3b56d33c1055894605a7bb6bcb3f9',
                                  'output_schema_hash': '12573ab3c34f0974c9245594b5dbc752ac1717003946758cb6baadb4c15909b7',
                                  'tags': ['audio', 'gated-write', 'qlab', 'settings'],
                                  'timeout': 60.0,
                                  'title': 'Edit QLab Audio Output Patch'},
 'qlab_edit_camera_cues': {'annotations': {'destructiveHint': True,
                                           'idempotentHint': False,
                                           'openWorldHint': True,
                                           'readOnlyHint': False},
                           'input_schema_hash': '2257483f89e61f90c08ce374726d690ff61d0c3e13e2e593847ad75a9aeffe53',
                           'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                           'tags': ['batch-edit',
                                    'camera',
                                    'cue-edit',
                                    'gated-write',
                                    'qlab',
                                    'write-mode'],
                           'timeout': 180.0,
                           'title': 'Edit QLab Camera Cues'},
 'qlab_edit_control_cues': {'annotations': {'destructiveHint': True,
                                            'idempotentHint': False,
                                            'openWorldHint': True,
                                            'readOnlyHint': False},
                            'input_schema_hash': 'ebf241f71874f386518cd57c007ee01ac252eb98c4dfb007aa56f9fa52619b51',
                            'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                            'tags': ['batch-edit',
                                     'control',
                                     'cue-edit',
                                     'gated-write',
                                     'qlab',
                                     'write-mode'],
                            'timeout': 180.0,
                            'title': 'Edit QLab Control Cues'},
 'qlab_edit_cue_lists': {'annotations': {'destructiveHint': True,
                                         'idempotentHint': False,
                                         'openWorldHint': True,
                                         'readOnlyHint': False},
                         'input_schema_hash': '9f4b55e29b6e5838e6273397351ef4dcf6cf78d306e1bd4dd7912c110b844163',
                         'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                         'tags': ['batch-edit',
                                  'cue-list-edit',
                                  'gated-write',
                                  'qlab',
                                  'write-mode'],
                         'timeout': 180.0,
                         'title': 'Edit QLab Cue Lists'},
 'qlab_edit_devamp_cues': {'annotations': {'destructiveHint': True,
                                           'idempotentHint': False,
                                           'openWorldHint': True,
                                           'readOnlyHint': False},
                           'input_schema_hash': '0049417b7d274dd16e5918c6f9866b6bbc7178e075e535164a2fe8686ddb72fd',
                           'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                           'tags': ['batch-edit',
                                    'cue-edit',
                                    'devamp',
                                    'gated-write',
                                    'qlab',
                                    'write-mode'],
                           'timeout': 180.0,
                           'title': 'Edit QLab Devamp Cues'},
 'qlab_edit_fade_cues': {'annotations': {'destructiveHint': True,
                                         'idempotentHint': False,
                                         'openWorldHint': True,
                                         'readOnlyHint': False},
                         'input_schema_hash': 'f884797bc9e3381ffd6b3f8b4da953d3512d4b66cfadfce089ecb6ad46ae6854',
                         'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                         'tags': ['batch-edit',
                                  'cue-edit',
                                  'fade',
                                  'gated-write',
                                  'qlab',
                                  'write-mode'],
                         'timeout': 180.0,
                         'title': 'Edit QLab Fade Cues'},
 'qlab_edit_group_cues': {'annotations': {'destructiveHint': True,
                                          'idempotentHint': False,
                                          'openWorldHint': True,
                                          'readOnlyHint': False},
                          'input_schema_hash': '863cf0c68287060f5ce394eb59acfdf5da44e7f206b6c3e8484c247c8df32785',
                          'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                          'tags': ['batch-edit',
                                   'cue-edit',
                                   'gated-write',
                                   'group',
                                   'qlab',
                                   'write-mode'],
                          'timeout': 180.0,
                          'title': 'Edit QLab Group Cues'},
 'qlab_edit_light_cues': {'annotations': {'destructiveHint': True,
                                          'idempotentHint': False,
                                          'openWorldHint': True,
                                          'readOnlyHint': False},
                          'input_schema_hash': '1ee03b202afa21390c2bb019e0c29fb27c2e95224f8ee1cf938fe402b02c0d85',
                          'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                          'tags': ['batch-edit',
                                   'cue-edit',
                                   'gated-write',
                                   'light',
                                   'qlab',
                                   'write-mode'],
                          'timeout': 180.0,
                          'title': 'Edit QLab Light Cues'},
 'qlab_edit_mic_cues': {'annotations': {'destructiveHint': True,
                                        'idempotentHint': False,
                                        'openWorldHint': True,
                                        'readOnlyHint': False},
                        'input_schema_hash': 'bd917803b0daf142230f0da1dcc7b90bfecb327a91f2d14bd3ddf5d5bf2001ca',
                        'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                        'tags': ['batch-edit',
                                 'cue-edit',
                                 'gated-write',
                                 'mic',
                                 'qlab',
                                 'write-mode'],
                        'timeout': 180.0,
                        'title': 'Edit QLab Mic Cues'},
 'qlab_edit_midi_cues': {'annotations': {'destructiveHint': True,
                                         'idempotentHint': False,
                                         'openWorldHint': True,
                                         'readOnlyHint': False},
                         'input_schema_hash': '6e2882cde0fb6e5b7d52adf72637966989a6a25a54fe0e0d8991a02b2a797c8d',
                         'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                         'tags': ['batch-edit',
                                  'cue-edit',
                                  'gated-write',
                                  'midi',
                                  'qlab',
                                  'write-mode'],
                         'timeout': 180.0,
                         'title': 'Edit QLab MIDI Cues'},
 'qlab_edit_midi_file_cues': {'annotations': {'destructiveHint': True,
                                              'idempotentHint': False,
                                              'openWorldHint': True,
                                              'readOnlyHint': False},
                              'input_schema_hash': '6fa3c840b131701cdd17bb011f8b4b8516ebd7c3d7d9559913f9add942c26758',
                              'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                              'tags': ['batch-edit',
                                       'cue-edit',
                                       'gated-write',
                                       'midi_file',
                                       'qlab',
                                       'write-mode'],
                              'timeout': 180.0,
                              'title': 'Edit QLab MIDI File Cues'},
 'qlab_edit_network_cues': {'annotations': {'destructiveHint': True,
                                            'idempotentHint': False,
                                            'openWorldHint': True,
                                            'readOnlyHint': False},
                            'input_schema_hash': '296a30e0eb8aadbe4704bdbd2a5af7a362d5ddfc878d66c16d3a5fc942bb8ffe',
                            'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                            'tags': ['batch-edit',
                                     'cue-edit',
                                     'gated-write',
                                     'network',
                                     'qlab',
                                     'write-mode'],
                            'timeout': 180.0,
                            'title': 'Edit QLab Network Cues'},
 'qlab_edit_script_cues': {'annotations': {'destructiveHint': True,
                                           'idempotentHint': False,
                                           'openWorldHint': True,
                                           'readOnlyHint': False},
                           'input_schema_hash': '62765019e6eb004265ca6bd7aa184546e43498f1a1fe7d63b5cbb6576a420e96',
                           'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                           'tags': ['batch-edit',
                                    'cue-edit',
                                    'gated-write',
                                    'qlab',
                                    'script',
                                    'write-mode'],
                           'timeout': 180.0,
                           'title': 'Edit QLab Script Cues'},
 'qlab_edit_target_cues': {'annotations': {'destructiveHint': True,
                                           'idempotentHint': False,
                                           'openWorldHint': True,
                                           'readOnlyHint': False},
                           'input_schema_hash': 'ae546bfc4a4377b3385f41a56784f6a6e521ac91e798c7f5e3d8a5baf5fe50bc',
                           'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                           'tags': ['batch-edit',
                                    'cue-edit',
                                    'gated-write',
                                    'qlab',
                                    'target',
                                    'write-mode'],
                           'timeout': 180.0,
                           'title': 'Edit QLab Target Cues'},
 'qlab_edit_text_cues': {'annotations': {'destructiveHint': True,
                                         'idempotentHint': False,
                                         'openWorldHint': True,
                                         'readOnlyHint': False},
                         'input_schema_hash': '5bced2a50232628a5678146ad29a9957a6bddf71874a232da3723c7acb800724',
                         'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                         'tags': ['batch-edit',
                                  'cue-edit',
                                  'gated-write',
                                  'qlab',
                                  'text',
                                  'write-mode'],
                         'timeout': 180.0,
                         'title': 'Edit QLab Text Cues'},
 'qlab_edit_timecode_cues': {'annotations': {'destructiveHint': True,
                                             'idempotentHint': False,
                                             'openWorldHint': True,
                                             'readOnlyHint': False},
                             'input_schema_hash': 'a73248e231cab8a9907b773eb49045308776b6af94487a58b96c161d6b888c6b',
                             'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                             'tags': ['batch-edit',
                                      'cue-edit',
                                      'gated-write',
                                      'qlab',
                                      'timecode',
                                      'write-mode'],
                             'timeout': 180.0,
                             'title': 'Edit QLab Timecode Cues'},
 'qlab_edit_video_cues': {'annotations': {'destructiveHint': True,
                                          'idempotentHint': False,
                                          'openWorldHint': True,
                                          'readOnlyHint': False},
                          'input_schema_hash': 'f8eea067a29d9eba028b0d45c84a9a07f9ab590d43908859434a6a4094aed9a1',
                          'output_schema_hash': '016e4e99ca9dbd11824e3180016b6d4612b3a53721d23db0d842e262cda7f34d',
                          'tags': ['batch-edit',
                                   'cue-edit',
                                   'gated-write',
                                   'qlab',
                                   'video',
                                   'write-mode'],
                          'timeout': 180.0,
                          'title': 'Edit QLab Video Cues'},
 'qlab_edit_video_output_route': {'annotations': {'destructiveHint': True,
                                                  'idempotentHint': False,
                                                  'openWorldHint': True,
                                                  'readOnlyHint': False},
                                  'input_schema_hash': '87941f4b1504645a27f2332e7791d83c1091c894fe52af26c1dbf55229fb267c',
                                  'output_schema_hash': '12573ab3c34f0974c9245594b5dbc752ac1717003946758cb6baadb4c15909b7',
                                  'tags': ['gated-write', 'qlab', 'settings', 'video'],
                                  'timeout': 60.0,
                                  'title': 'Edit QLab Video Output Route'},
 'qlab_edit_video_region': {'annotations': {'destructiveHint': True,
                                            'idempotentHint': False,
                                            'openWorldHint': True,
                                            'readOnlyHint': False},
                            'input_schema_hash': '78905b42fc5b37514397b3520e2b716ae294fec14cb0d8231e8ffaad3edd9fad',
                            'output_schema_hash': '12573ab3c34f0974c9245594b5dbc752ac1717003946758cb6baadb4c15909b7',
                            'tags': ['gated-write', 'qlab', 'settings', 'video'],
                            'timeout': 60.0,
                            'title': 'Edit QLab Video Region'},
 'qlab_edit_video_stage': {'annotations': {'destructiveHint': True,
                                           'idempotentHint': False,
                                           'openWorldHint': True,
                                           'readOnlyHint': False},
                           'input_schema_hash': '7080c6576d7a4fb92f6dfb248b3c17590fbb2a374dd4b70a594d07b6364e059d',
                           'output_schema_hash': '12573ab3c34f0974c9245594b5dbc752ac1717003946758cb6baadb4c15909b7',
                           'tags': ['gated-write', 'qlab', 'settings', 'video'],
                           'timeout': 60.0,
                           'title': 'Edit QLab Video Stage'},
 'qlab_edit_workspace_general_settings': {'annotations': {'destructiveHint': True,
                                                          'idempotentHint': False,
                                                          'openWorldHint': True,
                                                          'readOnlyHint': False},
                                          'input_schema_hash': '93882d40189796d64c1b69d301dc63caeaa883d34fe19b4a45bc6b9804bc4fcc',
                                          'output_schema_hash': '12573ab3c34f0974c9245594b5dbc752ac1717003946758cb6baadb4c15909b7',
                                          'tags': ['gated-write',
                                                   'general-settings',
                                                   'qlab',
                                                   'settings',
                                                   'write-mode'],
                                          'timeout': 60.0,
                                          'title': 'Edit QLab Workspace General Settings'},
 'qlab_get_audio_cue_details': {'annotations': {'destructiveHint': False,
                                                'idempotentHint': True,
                                                'openWorldHint': True,
                                                'readOnlyHint': True},
                                'input_schema_hash': '5acbfc5f33a8dba51ba87a12a3c4778395128c071cfcd0b3b6cf5abc44e6c871',
                                'output_schema_hash': 'c9eb177b86c5ffce8d64f163312f66ed694b6d6c69c098189070e02cf7e8ea47',
                                'tags': ['audio', 'details', 'qlab', 'safe-read'],
                                'timeout': 20.0,
                                'title': 'Get QLab Audio Cue Details'},
 'qlab_get_audio_cues': {'annotations': {'destructiveHint': False,
                                         'idempotentHint': True,
                                         'openWorldHint': True,
                                         'readOnlyHint': True},
                         'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                         'output_schema_hash': '39b70303e81f6529a72342a0feb325b1f0d3893c7ff8f7b6e69e0da43d6f0e54',
                         'tags': ['audio', 'inventory', 'qlab', 'safe-read'],
                         'timeout': 60.0,
                         'title': 'Get QLab Audio Cues'},
 'qlab_get_camera_cue_details': {'annotations': {'destructiveHint': False,
                                                 'idempotentHint': True,
                                                 'openWorldHint': True,
                                                 'readOnlyHint': True},
                                  'input_schema_hash': '2734838d3ecd4fe7a5d412e08777007dbe199ecc318f119cfe86999b266920ae',
                                 'output_schema_hash': '8e682fee65b79ff2581c17a03fd6c6183ff7143dbfb9e5f6785de42250a0fd9e',
                                 'tags': ['camera', 'details', 'qlab', 'safe-read'],
                                 'timeout': 20.0,
                                 'title': 'Get QLab Camera Cue Details'},
 'qlab_get_camera_cues': {'annotations': {'destructiveHint': False,
                                          'idempotentHint': True,
                                          'openWorldHint': True,
                                          'readOnlyHint': True},
                          'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                          'output_schema_hash': '7d4d5b1fa1ea4e6d9d3559891103b8043eb13460b5843414570ae729323b642e',
                          'tags': ['camera', 'inventory', 'qlab', 'safe-read'],
                          'timeout': 60.0,
                          'title': 'Get QLab Camera Cues'},
 'qlab_get_control_cue_details': {'annotations': {'destructiveHint': False,
                                                  'idempotentHint': True,
                                                  'openWorldHint': True,
                                                  'readOnlyHint': True},
                                  'input_schema_hash': '2881d9ee264949335aa89758f1bbb3d5086157942e6c1cabe03f574c21895a15',
                                  'output_schema_hash': '669d580671db6790fc74a342ff26d0a22523150b8723748caa7bfc370a3d1216',
                                  'tags': ['control', 'details', 'qlab', 'safe-read'],
                                  'timeout': 20.0,
                                  'title': 'Get QLab Control Cue Details'},
 'qlab_get_control_cues': {'annotations': {'destructiveHint': False,
                                           'idempotentHint': True,
                                           'openWorldHint': True,
                                           'readOnlyHint': True},
                           'input_schema_hash': '75d6d6aad4041afdee76b5ef37fd2d28ce55b561381606fe85257cb68f8dfdc1',
                           'output_schema_hash': 'fb0ddd27a803a7b1565d05105656706cf0e6447546305cf3e0faacd5533297d7',
                           'tags': ['control', 'inventory', 'qlab', 'safe-read'],
                           'timeout': 60.0,
                           'title': 'Get QLab Control Cues'},
 'qlab_get_cue_cart_details': {'annotations': {'destructiveHint': False,
                                               'idempotentHint': True,
                                               'openWorldHint': True,
                                               'readOnlyHint': True},
                               'input_schema_hash': '5d384b1bc7b5a4c5e36ae75a006d97e7547ae710b00cd2e744d3186f7a067f25',
                               'output_schema_hash': '80af7427b2300773f012ed1ef0687ed300107e0d02868379b7ff4ff97d54c96a',
                               'tags': ['cue-carts', 'details', 'qlab', 'safe-read'],
                               'timeout': 45.0,
                               'title': 'Get QLab Cue Cart Details'},
 'qlab_get_cue_details': {'annotations': {'destructiveHint': False,
                                          'idempotentHint': True,
                                          'openWorldHint': True,
                                          'readOnlyHint': True},
                          'input_schema_hash': 'fc0207668042fa9e62480000c05f575ecccd5cbf2d06b5556661aee43147641c',
                          'output_schema_hash': 'f5d340a970b906607ed9c3a2015c17a8da6f3eee5d70b36971c26920aa14da72',
                          'tags': ['details', 'diagnostics', 'qlab', 'safe-read'],
                          'timeout': 20.0,
                          'title': 'Get QLab Cue Details'},
 'qlab_get_cue_list_details': {'annotations': {'destructiveHint': False,
                                               'idempotentHint': True,
                                               'openWorldHint': True,
                                               'readOnlyHint': True},
                               'input_schema_hash': '68b54234cee80c21538edc3dbf02ab6a83c78959a9b1135044e00dec8a26862b',
                               'output_schema_hash': 'f5cfccd4772f9770e2a0e452132189b41a8b97a97a6bdab78bdea465dbdf05fc',
                               'tags': ['cue-lists', 'details', 'qlab', 'safe-read'],
                               'timeout': 45.0,
                               'title': 'Get QLab Cue List Details'},
 'qlab_get_cue_lists': {'annotations': {'destructiveHint': False,
                                        'idempotentHint': True,
                                        'openWorldHint': True,
                                        'readOnlyHint': True},
                        'input_schema_hash': 'a100d2c71d8a6573be48039f083c85ed16c495c4b69cc2a248b81336bb589578',
                        'output_schema_hash': 'b7487f193df9f9526fb523e78dabb86ddf7a0e43babf8f9a1338848382523262',
                        'tags': ['cue-lists', 'inventory', 'qlab', 'safe-read'],
                        'timeout': 20.0,
                        'title': 'Get QLab Cue Lists'},
 'qlab_get_fade_cue_details': {'annotations': {'destructiveHint': False,
                                               'idempotentHint': True,
                                               'openWorldHint': True,
                                               'readOnlyHint': True},
                               'input_schema_hash': '41fc52d498a749c3938a6e440a4473261991b42abe70b01a34d557c74c5fe54c',
                               'output_schema_hash': '0a7f338d05dcf640bc44acb79fc941ea83b6545e0ae7cebe6cbd2c1dbd94e0f4',
                               'tags': ['details', 'fade', 'qlab', 'safe-read'],
                               'timeout': 20.0,
                               'title': 'Get QLab Fade Cue Details'},
 'qlab_get_fade_cues': {'annotations': {'destructiveHint': False,
                                        'idempotentHint': True,
                                        'openWorldHint': True,
                                        'readOnlyHint': True},
                        'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                        'output_schema_hash': 'a0f5daf5b9b9d33ae9589c004852f03de2b6baaa46d3ec73a912a1e676e63e5f',
                        'tags': ['fade', 'inventory', 'qlab', 'safe-read'],
                        'timeout': 60.0,
                        'title': 'Get QLab Fade Cues'},
 'qlab_get_group_cue_details': {'annotations': {'destructiveHint': False,
                                                'idempotentHint': True,
                                                'openWorldHint': True,
                                                'readOnlyHint': True},
                                'input_schema_hash': 'ad523aa095115828702227d4e3cdd07569082dad9c1b55525746d1bd8a74f6e7',
                                'output_schema_hash': '53ba5d831de3cbebb784029c2b9505774a3dd09962ac501e8943e4bee10296eb',
                                'tags': ['details', 'group', 'qlab', 'safe-read'],
                                'timeout': 20.0,
                                'title': 'Get QLab Group Cue Details'},
 'qlab_get_group_cues': {'annotations': {'destructiveHint': False,
                                         'idempotentHint': True,
                                         'openWorldHint': True,
                                         'readOnlyHint': True},
                         'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                         'output_schema_hash': '4497a7eb0f64f64210bf107fd995a412ce975f15fb7a4fafae16a77fa4548e38',
                         'tags': ['group', 'inventory', 'qlab', 'safe-read'],
                         'timeout': 60.0,
                         'title': 'Get QLab Group Cues'},
 'qlab_get_light_cue_details': {'annotations': {'destructiveHint': False,
                                                'idempotentHint': True,
                                                'openWorldHint': True,
                                                'readOnlyHint': True},
                                'input_schema_hash': '7cc4a31b024156fd175127df7ab00976bac24f1bac335360075ad7633fbd82d6',
                                'output_schema_hash': '0119314af7aa0d80c0c5d14a1a01002ba8187d9714faba2c41c89755a9a7ea8f',
                                'tags': ['details', 'light', 'qlab', 'safe-read'],
                                'timeout': 20.0,
                                'title': 'Get QLab Light Cue Details'},
 'qlab_get_light_cues': {'annotations': {'destructiveHint': False,
                                         'idempotentHint': True,
                                         'openWorldHint': True,
                                         'readOnlyHint': True},
                         'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                         'output_schema_hash': 'e41a584376deb04c1f858dd1e5914bf7f0a3222422b9212c698abc6630985cb3',
                         'tags': ['inventory', 'light', 'qlab', 'safe-read'],
                         'timeout': 60.0,
                         'title': 'Get QLab Light Cues'},
 'qlab_get_mic_cue_details': {'annotations': {'destructiveHint': False,
                                              'idempotentHint': True,
                                              'openWorldHint': True,
                                              'readOnlyHint': True},
                              'input_schema_hash': '972aee57491c2c5543cf1eaf4e1ea4f87baa55ebacdd959c3674fe0eb0c33313',
                              'output_schema_hash': '5be423f6016b89906b25d8496183b3139fd762465a2e4190fc91562d06be0292',
                              'tags': ['details', 'mic', 'qlab', 'safe-read'],
                              'timeout': 20.0,
                              'title': 'Get QLab Mic Cue Details'},
 'qlab_get_mic_cues': {'annotations': {'destructiveHint': False,
                                       'idempotentHint': True,
                                       'openWorldHint': True,
                                       'readOnlyHint': True},
                       'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                       'output_schema_hash': '68223c0f34044ca515d17b8869a12eb22a1b91c2d9d31c7390819bd925a9acfe',
                       'tags': ['inventory', 'mic', 'qlab', 'safe-read'],
                       'timeout': 60.0,
                       'title': 'Get QLab Mic Cues'},
 'qlab_get_midi_cue_details': {'annotations': {'destructiveHint': False,
                                               'idempotentHint': True,
                                               'openWorldHint': True,
                                               'readOnlyHint': True},
                               'input_schema_hash': '57259aae1bb0b6a6bd624dd52cbb73c214891b86017c8844328a9c0ffbffb3b1',
                               'output_schema_hash': '6260de5108a197a0152e75e3d75a67575302d41a57ba1d84a61785534a6e993c',
                               'tags': ['details', 'midi', 'qlab', 'safe-read'],
                               'timeout': 20.0,
                               'title': 'Get QLab MIDI Cue Details'},
 'qlab_get_midi_cues': {'annotations': {'destructiveHint': False,
                                        'idempotentHint': True,
                                        'openWorldHint': True,
                                        'readOnlyHint': True},
                        'input_schema_hash': '40e3b50a6091cb04e48143d9083895bd39bd19afea7d194384deab085f303795',
                        'output_schema_hash': 'd02bfda19290045caee0a4831e718e73e7ca6e1f695d5c47adb58244052a5304',
                        'tags': ['inventory', 'midi', 'qlab', 'safe-read'],
                        'timeout': 60.0,
                        'title': 'Get QLab MIDI Cues'},
 'qlab_get_network_cue_details': {'annotations': {'destructiveHint': False,
                                                  'idempotentHint': True,
                                                  'openWorldHint': True,
                                                  'readOnlyHint': True},
                                  'input_schema_hash': 'b256789d94ca79dc1e44010edf63d1aa3e0eb91f6066add27698de463b43b3c8',
                                  'output_schema_hash': '5156aaf4c3354a8ca2d63d8e826b27f517abc77a3745dc46ebcc627ba97efee8',
                                  'tags': ['details', 'network', 'qlab', 'safe-read'],
                                  'timeout': 20.0,
                                  'title': 'Get QLab Network Cue Details'},
 'qlab_get_network_cues': {'annotations': {'destructiveHint': False,
                                           'idempotentHint': True,
                                           'openWorldHint': True,
                                           'readOnlyHint': True},
                           'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                           'output_schema_hash': 'cfa1d5efb830be16e84d77832ba61262043852c012f0e28a4e28908deb738573',
                           'tags': ['inventory', 'network', 'qlab', 'safe-read'],
                           'timeout': 60.0,
                           'title': 'Get QLab Network Cues'},
 'qlab_get_script_cue_details': {'annotations': {'destructiveHint': False,
                                                 'idempotentHint': True,
                                                 'openWorldHint': True,
                                                 'readOnlyHint': True},
                                 'input_schema_hash': '1745121f99ffbb029890d4ec42614f62bb9ce82f6f9fce10f6f62e6eb96ff295',
                                 'output_schema_hash': 'b4cac6f85463cd18c1c616c93f6943d05c8fa904813ed2ca52eea6fece2d66b8',
                                 'tags': ['details', 'qlab', 'safe-read', 'script'],
                                 'timeout': 20.0,
                                 'title': 'Get QLab Script Cue Details'},
 'qlab_get_script_cues': {'annotations': {'destructiveHint': False,
                                          'idempotentHint': True,
                                          'openWorldHint': True,
                                          'readOnlyHint': True},
                          'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                          'output_schema_hash': 'dc5c05e00596f9a6d4d92c06088b221a77fb471fd781450c82186f6dec376d6e',
                          'tags': ['inventory', 'qlab', 'safe-read', 'script'],
                          'timeout': 60.0,
                          'title': 'Get QLab Script Cues'},
 'qlab_get_text_cue_details': {'annotations': {'destructiveHint': False,
                                               'idempotentHint': True,
                                               'openWorldHint': True,
                                               'readOnlyHint': True},
                               'input_schema_hash': '98fe1a0ea512317c417efa63e169f42688348a970d36c15485234ef82078d88f',
                               'output_schema_hash': '18d53dfe9fb674400bbf94d0f57050544be2cdc3e669caf9b592b2ab90be7332',
                               'tags': ['details', 'qlab', 'safe-read', 'text'],
                               'timeout': 20.0,
                               'title': 'Get QLab Text Cue Details'},
 'qlab_get_text_cues': {'annotations': {'destructiveHint': False,
                                        'idempotentHint': True,
                                        'openWorldHint': True,
                                        'readOnlyHint': True},
                        'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                        'output_schema_hash': '5bf7b9823d164ae7112ef82b1f31735e0648012cca17d4d527b08f1ecd755461',
                        'tags': ['inventory', 'qlab', 'safe-read', 'text'],
                        'timeout': 60.0,
                        'title': 'Get QLab Text Cues'},
 'qlab_get_timecode_cue_details': {'annotations': {'destructiveHint': False,
                                                   'idempotentHint': True,
                                                   'openWorldHint': True,
                                                   'readOnlyHint': True},
                                   'input_schema_hash': '76e33807d0eeab59030a857b8a048cb3c4ea36bab6f171d8be2c618f9ff14865',
                                   'output_schema_hash': 'd3c423c65c8aa24db5fe3162be58e0f3a4cdcec1ebe606254db0d1aad6ed428e',
                                   'tags': ['details', 'qlab', 'safe-read', 'timecode'],
                                   'timeout': 20.0,
                                   'title': 'Get QLab Timecode Cue Details'},
 'qlab_get_timecode_cues': {'annotations': {'destructiveHint': False,
                                            'idempotentHint': True,
                                            'openWorldHint': True,
                                            'readOnlyHint': True},
                            'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                            'output_schema_hash': '31a3c9b1aa213e9379bc057080ecf7aaeccccc93a378e65467b7c6ea126a26ac',
                            'tags': ['inventory', 'qlab', 'safe-read', 'timecode'],
                            'timeout': 60.0,
                            'title': 'Get QLab Timecode Cues'},
 'qlab_get_video_cue_details': {'annotations': {'destructiveHint': False,
                                                'idempotentHint': True,
                                                'openWorldHint': True,
                                                'readOnlyHint': True},
                               'input_schema_hash': '2734838d3ecd4fe7a5d412e08777007dbe199ecc318f119cfe86999b266920ae',
                                'output_schema_hash': 'ed65196d4e43c7b5902e21c9abebf8d621c8baded2f6850ee243db5ee622c935',
                                'tags': ['details', 'qlab', 'safe-read', 'video'],
                                'timeout': 20.0,
                                'title': 'Get QLab Video Cue Details'},
 'qlab_get_video_cues': {'annotations': {'destructiveHint': False,
                                         'idempotentHint': True,
                                         'openWorldHint': True,
                                         'readOnlyHint': True},
                         'input_schema_hash': 'fb28972171d049ee9d9f38a37e3085371c8082aa1889df4a2b4f8a3d0371defa',
                         'output_schema_hash': '9c415d55780ad6c06b598cdf41940cd49c896bc87721581f435e2126f78f7bd5',
                         'tags': ['inventory', 'qlab', 'safe-read', 'video'],
                         'timeout': 60.0,
                         'title': 'Get QLab Video Cues'},
 'qlab_get_video_output_route': {'annotations': {'destructiveHint': False,
                                                 'idempotentHint': True,
                                                 'openWorldHint': True,
                                                 'readOnlyHint': True},
                                 'input_schema_hash': 'fa883e96fc21221c758cbdff15858a326aa8826e4c835960574d70437863f4ad',
                                 'output_schema_hash': '832f53b4052ea3a5f9cb913531fb8385c991934af03a08be55e1f99b1fa4fc3d',
                                 'tags': ['qlab', 'routing', 'safe-read', 'settings', 'video'],
                                 'timeout': 60.0,
                                 'title': 'Get QLab Video Output Route'},
 'qlab_get_video_region': {'annotations': {'destructiveHint': False,
                                           'idempotentHint': True,
                                           'openWorldHint': True,
                                           'readOnlyHint': True},
                           'input_schema_hash': '0fe19d0e4558304d80ad5547aee1ef965d3134edbe8985e84e9736328bf46798',
                           'output_schema_hash': '938f6ea9b0bb9553b1dcf48655f23c6ebe21e241cd2adbdf5ed62755b94a0295',
                           'tags': ['qlab', 'regions', 'safe-read', 'settings', 'video'],
                           'timeout': 60.0,
                           'title': 'Get QLab Video Region'},
 'qlab_get_video_stage': {'annotations': {'destructiveHint': False,
                                          'idempotentHint': True,
                                          'openWorldHint': True,
                                          'readOnlyHint': True},
                          'input_schema_hash': 'a6bfcb9c9e86f1d3b384f14dd3cff7b47db7a60e6847776690627b9209c4d2bc',
                          'output_schema_hash': 'a30f6de759094ba7ea62c4d3add5bb42815d064b9169e1504a94babe525a9637',
                          'tags': ['qlab', 'safe-read', 'settings', 'stages', 'video'],
                          'timeout': 60.0,
                          'title': 'Get QLab Video Stage'},
 'qlab_get_workspace_audio_settings': {'annotations': {'destructiveHint': False,
                                                       'idempotentHint': True,
                                                       'openWorldHint': True,
                                                       'readOnlyHint': True},
                                       'input_schema_hash': '3174667dc67bf2a6a827e2f7e1c7da40725b55f8d72b7b5cb1a025679b25ffaf',
                                       'output_schema_hash': '43b34ba9cabec1a16d44ba3ba2f39c5d98469850192fce6de43b8c8f5ff55ff1',
                                       'tags': ['audio',
                                                'patches',
                                                'qlab',
                                                'routing',
                                                'safe-read',
                                                'settings'],
                                       'timeout': 60.0,
                                       'title': 'Get QLab Workspace Audio Settings'},
 'qlab_get_workspace_general_settings': {'annotations': {'destructiveHint': False,
                                                         'idempotentHint': True,
                                                         'openWorldHint': True,
                                                         'readOnlyHint': True},
                                         'input_schema_hash': 'a100d2c71d8a6573be48039f083c85ed16c495c4b69cc2a248b81336bb589578',
                                         'output_schema_hash': '3f0b8b906ca4f7a676cf90f44ca911fcb5976f9dc908ba81779313663707135f',
                                         'tags': ['general', 'qlab', 'safe-read', 'settings'],
                                         'timeout': 60.0,
                                         'title': 'Get QLab Workspace General Settings'},
 'qlab_get_workspace_light_settings': {'annotations': {'destructiveHint': False,
                                                       'idempotentHint': True,
                                                       'openWorldHint': True,
                                                       'readOnlyHint': True},
                                       'input_schema_hash': 'cfd70c189348699a8f4f7e24a2dd2c81fc85b3aeeda35d9ff8ac4e00f607a495',
                                       'output_schema_hash': '93e4e2e0895dd0c773398ac9771cf0a32fef26a54bfc06e9ee10a9ff5e8319b9',
                                       'tags': ['light',
                                                'patches',
                                                'qlab',
                                                'safe-read',
                                                'settings'],
                                       'timeout': 60.0,
                                       'title': 'Get QLab Workspace Light Settings'},
 'qlab_get_workspace_midi_settings': {'annotations': {'destructiveHint': False,
                                                      'idempotentHint': True,
                                                      'openWorldHint': True,
                                                      'readOnlyHint': True},
                                      'input_schema_hash': 'eaaf315895e69c71d1110546fa037ae8bea54384d8eac79583a07207a2c9b86f',
                                      'output_schema_hash': 'a1246ab669e39937ba01a4f2865289a72a1354c022a1536f1aec11652dd08f9e',
                                      'tags': ['midi', 'patches', 'qlab', 'safe-read', 'settings'],
                                      'timeout': 60.0,
                                      'title': 'Get QLab Workspace MIDI Settings'},
 'qlab_get_workspace_network_settings': {'annotations': {'destructiveHint': False,
                                                         'idempotentHint': True,
                                                         'openWorldHint': True,
                                                         'readOnlyHint': True},
                                         'input_schema_hash': 'eaaf315895e69c71d1110546fa037ae8bea54384d8eac79583a07207a2c9b86f',
                                         'output_schema_hash': '048f6d873b4a6a4c5ba97f5e076e1a0d431250d04448fc90934c31cb5aff745f',
                                         'tags': ['network',
                                                  'patches',
                                                  'qlab',
                                                  'safe-read',
                                                  'settings'],
                                         'timeout': 60.0,
                                         'title': 'Get QLab Workspace Network Settings'},
 'qlab_get_workspace_overview': {'annotations': {'destructiveHint': False,
                                                 'idempotentHint': True,
                                                 'openWorldHint': True,
                                                 'readOnlyHint': True},
                                 'input_schema_hash': 'fddc30b27b0b2a8ca4fa5f9601004eaa565c724a5c9b145bcea65cb5be1317f1',
                                 'output_schema_hash': 'dcf4a4fc455bb3ebc3e62b0ca04e3cbc75bd91fc7e19fdb978283796f3f50454',
                                 'tags': ['orientation', 'qlab', 'safe-read', 'structure'],
                                 'timeout': 45.0,
                                 'title': 'Get QLab Workspace Overview'},
 'qlab_get_workspace_status': {'annotations': {'destructiveHint': False,
                                               'idempotentHint': True,
                                               'openWorldHint': True,
                                               'readOnlyHint': True},
                               'input_schema_hash': 'a85c42414b1b3a1c4405349720920ac5983f1c8933422013adaf9957e84ed45d',
                               'output_schema_hash': 'ccb2ea4d8bc34c308ddcc35e416d418d96efa6bfda67d2fc2cd4e61aa0ed949c',
                               'tags': ['diagnostics', 'qlab', 'safe-read', 'status', 'timecode'],
                               'timeout': 60.0,
                               'title': 'Get QLab Workspace Status'},
 'qlab_get_workspace_video_settings': {'annotations': {'destructiveHint': False,
                                                       'idempotentHint': True,
                                                       'openWorldHint': True,
                                                       'readOnlyHint': True},
                                       'input_schema_hash': 'a100d2c71d8a6573be48039f083c85ed16c495c4b69cc2a248b81336bb589578',
                                       'output_schema_hash': '5a23a3b35e20fcfc88e21c64eae3095ab09082d1d9f1de94170cc0bbd0acbe37',
                                       'tags': ['patches',
                                                'qlab',
                                                'routing',
                                                'safe-read',
                                                'settings',
                                                'video'],
                                       'timeout': 60.0,
                                       'title': 'Get QLab Workspace Video Settings'},
 'qlab_move_cue_lists': {'annotations': {'destructiveHint': True,
                                         'idempotentHint': False,
                                         'openWorldHint': True,
                                         'readOnlyHint': False},
                         'input_schema_hash': '91aeeabcf60ad5f868c5a1e59f8d203d73c85e77c8516d4e4a6c1f11232d39db',
                         'output_schema_hash': '1197e3de730b0fcb1d3f068942d9b0cedc796042e29697c5536fb7a570cac32d',
                         'tags': ['cue-list-move', 'gated-write', 'qlab', 'write-mode'],
                         'timeout': 180.0,
                         'title': 'Move QLab Cue Lists'},
 'qlab_move_cues': {'annotations': {'destructiveHint': True,
                                    'idempotentHint': False,
                                    'openWorldHint': True,
                                    'readOnlyHint': False},
                    'input_schema_hash': '00fe59bde570539237878a5ad71151a664fe84445384a3cdd84ea7c00e03499d',
                    'output_schema_hash': '1197e3de730b0fcb1d3f068942d9b0cedc796042e29697c5536fb7a570cac32d',
                    'tags': ['cue-move', 'gated-write', 'qlab', 'write-mode'],
                    'timeout': 180.0,
                    'title': 'Move QLab Cues'},
 'qlab_query_cues': {'annotations': {'destructiveHint': False,
                                     'idempotentHint': True,
                                     'openWorldHint': True,
                                     'readOnlyHint': True},
                     'input_schema_hash': 'd06af63d14c70324eb62b16f81c07fd3967a39cc4eebd5c3fe0a9e7e8b6dcdf9',
                     'output_schema_hash': '16613ad3378154e2b01bb1dabe40ba6d56ff1394ffea2ad960ae14cd775549a5',
                     'tags': ['details', 'inventory', 'qlab', 'query', 'safe-read'],
                     'timeout': 60.0,
                     'title': 'Query QLab Cues'}}
ADDED_TOOL_NAMES = {
    "qlab_get_video_effect_catalogue", "qlab_get_workspace_document",
    "qlab_open_workspace", "qlab_save_workspace", "qlab_close_workspace",
}
EXPECTED_TOOL_NAMES = set(EXPECTED_FASTMCP_TOOL_CONTRACTS) | ADDED_TOOL_NAMES

EXPECTED_TOOL_CONCEPTS = {"qlab_get_fonts": ("PostScript", "TCP", "family/style"),
    "qlab_get_video_effect_catalogue": ("documented FX names", "paged static catalogue", "never grants permission"),
    "qlab_get_workspace_document": ("local", "workspace UUID", "dirty"),
    "qlab_open_workspace": ("empty inventory", "single-use", "Do not retry"),
    "qlab_save_workspace": ("existing path", "unsaved", "single-use"),
    "qlab_close_workspace": ("no unsaved changes", "saving no", "single-use"),
    "qlab_analyze_audio_file": ("100 ms", "source file", "512 KiB", "FFmpeg"),
    "qlab_search_media_files": ("home folder", "fileTarget", "truncated", "dry-run"),
    "qlab_edit_audio_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_mic_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_light_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_fade_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_network_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_midi_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_midi_file_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_timecode_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),
    "qlab_edit_script_cues": ("1–50", "dry_run", "confirm_gates", "single-use", "non-atomic", "Never retry"),

    "qlab_edit_video_cues": ("1–50", "non-atomic", "fresh readback", "single-use"),
    "qlab_edit_camera_cues": ("1–50", "non-atomic", "fresh readback", "single-use"),
    "qlab_edit_text_cues": ("1–50", "non-atomic", "fresh readback", "single-use"),
    "qlab_edit_devamp_cues": ("non-atomic", "uuid", "five minutes", "never retried"),
    "qlab_edit_target_cues": ("non-atomic", "uuid", "assignedNumber", "never retried"),
    "qlab_edit_control_cues": ("non-atomic", "uuid", "five minutes", "never retried"),
    "qlab_edit_group_cues": ("one cue and one property", "Playlist setters require mode 6", "five minutes", "non-atomic"),
    "qlab_create_cue_lists": ("empty root cue lists", "cue carts", "no rollback", "current container", "qlab_move_cue_lists"),
    "qlab_edit_cue_lists": ("exact root uuids", "incoming-timecode", "excludes playhead", "unavailable through osc"),
    "qlab_move_cue_lists": ("root cue lists", "cue carts", "zero-based", "confirm:movecuelists:v1", "non-atomic"),
    "qlab_get_fade_cue_details": ("exact fade cue", "partial errors"),
    "qlab_get_fade_cues": ("exact Cue List", "Carts are rejected"),
    "qlab_get_midi_cue_details": ("exact midi cue", "partial errors"),
    "qlab_get_midi_cues": ("exact Cue List", "Carts are rejected"),
    "qlab_get_network_cue_details": ("exact network cue", "partial errors"),
    "qlab_get_network_cues": ("exact Cue List", "Carts are rejected"),
    "qlab_get_script_cue_details": ("exact script cue", "partial errors"),
    "qlab_get_script_cues": ("exact Cue List", "Carts are rejected"),
    "qlab_get_timecode_cue_details": ("exact timecode cue", "partial errors"),
    "qlab_get_timecode_cues": ("exact Cue List", "Carts are rejected"),
    "qlab_get_control_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_control_cue_details": ("type automatically", "partial errors", "Never starts"),
    "qlab_get_light_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_light_cue_details": ("exact Light cue", "command text", "partial errors"),
    "qlab_get_group_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_group_cue_details": ("exact Group cue", "Playlist", "partial errors"),
    "qlab_get_video_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_video_cue_details": ("exact Video cue", "geometry", "partial errors"),
    "qlab_get_text_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_text_cue_details": ("exact Text cue", "geometry", "partial errors"),
    "qlab_get_camera_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_camera_cue_details": ("exact Camera cue", "geometry", "partial errors"),
    "qlab_get_mic_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_mic_cue_details": ("exact Mic cue", "both channel selectors", "Audio Objects"),
    "qlab_get_audio_cues": ("exact Cue List", "nested groups", "scan_complete"),
    "qlab_get_audio_cue_details": ("exact Audio cue", "both channel selectors", "Audio Objects"),
    "qlab_get_cue_lists": ("Cue Lists and Cue Carts", "No children", "qlab_get_cue_list_details"),
    "qlab_get_cue_list_details": ("exact Cue List", "incoming timecode", "bounded tree"),
    "qlab_get_cue_cart_details": ("exact Cue Cart", "grid dimensions", "no playhead"),
    "qlab_check_connection": ("passcode", "permission scopes", "write authorization"),
    "qlab_get_workspace_overview": ("first structural read", "bounded and shallow", "qlab_query_cues"),
    "qlab_get_workspace_status": ("workspace status", "full workspace status window clone", "derived operational status"),
    "qlab_get_workspace_general_settings": ("general settings", "minimum go time", "selection/playhead"),
    "qlab_get_workspace_audio_settings": ("audio settings overview", "exact output patch", "technical"),
    "qlab_get_workspace_video_settings": ("input patches", "uniqueIDs", "no independent device inventory"),
    "qlab_get_video_stage": ("exact Video stage", "regions", "redacted OSC payload"),
    "qlab_get_video_output_route": ("exact Video output route", "guides", "hardware metadata"),
    "qlab_get_workspace_light_settings": ("light patch", "safe summary", "technical payload"),
    "qlab_get_workspace_network_settings": ("network patch inventory", "exact network patch", "complete network settings panel"),
    "qlab_get_workspace_midi_settings": ("midi patch inventory", "exact midi patch", "complete midi settings panel"),
    "qlab_query_cues": ("optional and filters", "truncation metadata", "qlab_get_cue_details"),
    "qlab_get_cue_details": ("editable for update capability discovery", "exhaustive only for deep audits", "qlab_query_cues"),
    "qlab_check_write_readiness": ("without sending any mutating osc commands", "edit mode", "read-only preflight"),
    "qlab_create_cues": ("one verified /new per item", "without automatic rollback", "confirm:createcues:v2", "mcp sends no cue number", "do not predict it from the setting or template", "do not retry"),
    "qlab_edit_workspace_general_settings": ("minGoTime", "selectionIsPlayhead", "single-use token"),
    "qlab_edit_audio_output_patch": ("patch property", "mutes/solos", "single-use token"),
    "qlab_edit_video_output_route": ("enableGuides", "output route"),
    "qlab_edit_video_stage": ("Video stage", "Rename"),
    "qlab_edit_video_region": ("OSC-coordinate", "exact indices"),
    "qlab_get_video_region": ("OSC bounds", "control point"),
    "qlab_move_cues": ("sequential qlab cue moves", "never claims atomicity", "uuid-only", "confirm:movecues:v1", "fresh parent/order readback"),
    "qlab_delete_cues": ("sequential deletions", "not atomic", "confirm:deletecues:v1", "deepest-first", "no automatic rollback", "verify disappearance", "preservation", "empty group"),
}


def _normalized_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalized_schema(child)
            for key, child in sorted(value.items())
            if key not in SCHEMA_NOISE_KEYS
        }
    if isinstance(value, list):
        return [_normalized_schema(child) for child in value]
    return value


def _schema_hash(schema: dict[str, Any]) -> str:
    normalized = json.dumps(_normalized_schema(schema), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


def _annotation_contract(tool: Any) -> dict[str, bool | None]:
    return {
        "readOnlyHint": tool.annotations.readOnlyHint,
        "destructiveHint": tool.annotations.destructiveHint,
        "idempotentHint": tool.annotations.idempotentHint,
        "openWorldHint": tool.annotations.openWorldHint,
    }


async def _tool_contract_snapshot() -> dict[str, dict[str, Any]]:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    snapshot = {}
    for tool in sorted(tools, key=lambda item: item.name):
        runtime_tool = await mcp.get_tool(tool.name)
        snapshot[tool.name] = {
            "title": tool.title,
            "timeout": runtime_tool.timeout,
            "annotations": _annotation_contract(tool),
            "tags": (tool.meta or {}).get("fastmcp", {}).get("tags", []),
            "input_schema_hash": _schema_hash(tool.inputSchema),
            "output_schema_hash": _schema_hash(tool.outputSchema or {}),
        }
    return snapshot


def _tool_context_size_report(tools: list[Any], instructions: str) -> dict[str, Any]:
    def encoded_size(value: Any) -> int:
        return len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())

    return {
        "server_instructions_bytes": len(instructions.encode()),
        "tools": {
            tool.name: {
                "description_bytes": len((tool.description or "").encode()),
                "input_schema_bytes": encoded_size(tool.inputSchema),
                "output_schema_bytes": encoded_size(tool.outputSchema or {}),
            }
            for tool in sorted(tools, key=lambda item: item.name)
        },
    }


def test_fastmcp_json_points_to_stdio_server_without_write_env() -> None:
    raw_config = json.loads((PROJECT_ROOT / "fastmcp.json").read_text())
    parsed = MCPServerConfig.model_validate(raw_config)

    assert parsed.source.path == "fastmcp_entrypoint.py"
    assert parsed.source.entrypoint == "mcp"
    assert parsed.environment.project is None
    assert parsed.environment.dependencies == ["qlab-mcp @ ."]
    assert parsed.deployment.transport == "stdio"
    assert (PROJECT_ROOT / parsed.source.path).read_text() == "from qlab_mcp.server import mcp\n"

    deployment_env = raw_config.get("deployment", {}).get("env", {})
    assert "QLAB_PASSCODE" not in deployment_env
    assert "QLAB_ENABLE_WRITE" not in deployment_env
    assert "QLAB_WRITE_DRY_RUN_DEFAULT" not in deployment_env


def test_fastmcp_initialization_reports_project_version_and_universal_guidance() -> None:
    async def initialize():
        async with Client(mcp) as client:
            return client.initialize_result

    initialize_result = asyncio.run(initialize())
    assert initialize_result.serverInfo.version == "0.4.0"
    instructions = initialize_result.instructions
    assert instructions
    for phrase in (
        "QLAB_ENABLE_WRITE",
        "workspace",
        "exact UUIDs",
        "qlab_check_write_readiness",
        "dry-run",
        "fresh readback",
        "Do not retry",
        "GO-ready",
        "Runtime evidence",
        "QLab 5.5.10",
    ):
        assert phrase in instructions
    assert "seven inspector tools" not in instructions


def test_fastmcp_tool_contract_snapshot_matches_current_public_surface() -> None:
    actual = asyncio.run(_tool_contract_snapshot())
    assert {name: actual[name] for name in EXPECTED_FASTMCP_TOOL_CONTRACTS} == EXPECTED_FASTMCP_TOOL_CONTRACTS
    assert set(actual) == EXPECTED_TOOL_NAMES


def test_fastmcp_metadata_has_nonempty_titles_and_semantic_tags() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    for tool in asyncio.run(list_tools()):
        assert tool.title
        tags = set((tool.meta or {}).get("fastmcp", {}).get("tags", []))
        assert "qlab" in tags
        assert tags - {"qlab"}


@pytest.mark.parametrize(
    ("tool_name", "expected_annotations"),
    [
        (tool_name, contract["annotations"])
        for tool_name, contract in sorted(EXPECTED_FASTMCP_TOOL_CONTRACTS.items())
    ],
)
def test_fastmcp_annotation_matrix_is_explicit(tool_name: str, expected_annotations: dict[str, bool]) -> None:
    snapshot = asyncio.run(_tool_contract_snapshot())
    assert snapshot[tool_name]["annotations"] == expected_annotations


def test_fastmcp_cross_referenced_tool_names_exist() -> None:
    async def list_tools_and_instructions():
        async with Client(mcp) as client:
            return await client.list_tools(), client.initialize_result.instructions or ""

    tools, instructions = asyncio.run(list_tools_and_instructions())
    tool_names = {tool.name for tool in tools}
    referenced_names = set(re.findall(r"\bqlab_[a-z0-9_]+\b", instructions))
    for tool in tools:
        referenced_names.update(re.findall(r"\bqlab_[a-z0-9_]+\b", tool.description or ""))
    assert referenced_names <= tool_names


def test_fastmcp_tool_context_size_report_is_deterministic() -> None:
    async def list_tools_and_instructions():
        async with Client(mcp) as client:
            return await client.list_tools(), client.initialize_result.instructions or ""

    tools, instructions = asyncio.run(list_tools_and_instructions())
    report = _tool_context_size_report(tools, instructions)
    assert list(report["tools"]) == sorted(EXPECTED_TOOL_NAMES)
    assert report["server_instructions_bytes"] > 0
    for sizes in report["tools"].values():
        assert sizes["description_bytes"] > 0
        assert sizes["input_schema_bytes"] > 0
        assert sizes["output_schema_bytes"] > 0
    print(json.dumps(report, indent=2, sort_keys=True))


def test_read_tool_call_shapes_remain_explicit() -> None:
    expected = {
        "qlab_get_control_cues": {"workspace_id", "cue_list_id", "limit", "offset", "max_cues_scanned", "cue_type"},
        "qlab_get_control_cue_details": {"workspace_id", "cue_id", "profile", "include_native_triggers"},
        "qlab_get_audio_cues": {"workspace_id", "cue_list_id", "limit", "offset", "max_cues_scanned"},
        "qlab_get_video_cues": {"workspace_id", "cue_list_id", "limit", "offset", "max_cues_scanned"},
        "qlab_get_video_cue_details": {"workspace_id", "cue_id", "profile", "input_channel", "output_channel", "video_effects", "include_native_triggers"},
        "qlab_get_text_cues": {"workspace_id", "cue_list_id", "limit", "offset", "max_cues_scanned"},
        "qlab_get_text_cue_details": {"workspace_id", "cue_id", "profile", "video_effects", "include_native_triggers"},
        "qlab_get_camera_cues": {"workspace_id", "cue_list_id", "limit", "offset", "max_cues_scanned"},
        "qlab_get_camera_cue_details": {"workspace_id", "cue_id", "profile", "input_channel", "output_channel", "video_effects", "include_native_triggers"},
        "qlab_get_mic_cues": {"workspace_id", "cue_list_id", "limit", "offset", "max_cues_scanned"},
        "qlab_get_mic_cue_details": {"workspace_id", "cue_id", "profile", "input_channel", "output_channel", "inspections", "include_native_triggers"},
        "qlab_get_audio_cue_details": {"workspace_id", "cue_id", "profile", "input_channel", "output_channel", "inspections", "include_native_triggers"},
        "qlab_get_cue_lists": {"workspace_id"},
        "qlab_get_cue_list_details": {"workspace_id", "cue_list_id", "profile", "max_depth", "max_cues"},
        "qlab_get_cue_cart_details": {"workspace_id", "cue_cart_id", "profile", "max_cues"},
        "qlab_check_connection": {"workspace_id", "require_read_access"},
        "qlab_get_workspace_overview": {
            "workspace_id", "max_depth", "max_cues", "include_live_state",
            "include_cue_index", "max_index_cues", "cue_index_profile", "include_global_count",
        },
        "qlab_get_workspace_status": {"workspace_id", "profile", "include_timecode", "max_cues_scanned", "sample_limit"},
        "qlab_get_workspace_general_settings": {"workspace_id"},
        "qlab_get_workspace_audio_settings": {
            "workspace_id", "view", "ref", "profile", "input_channel", "output_channel",
        },
        "qlab_get_workspace_video_settings": {"workspace_id"},
        "qlab_get_video_stage": {"workspace_id", "stage_id", "profile"},
        "qlab_get_video_output_route": {"workspace_id", "route_id", "profile"},
        "qlab_get_workspace_light_settings": {"workspace_id", "profile"},
        "qlab_get_workspace_network_settings": {"workspace_id", "ref", "profile"},
        "qlab_get_workspace_midi_settings": {"workspace_id", "ref", "profile"},
        "qlab_query_cues": {"workspace_id", "primary_filter", "primary_value", "optional_filters", "profile", "max_results", "max_cues_scanned"},
        "qlab_get_cue_details": {"workspace_id", "cue_ref", "profile"},
        "qlab_check_write_readiness": {"workspace_id"},
    }
    for tool_name, parameter_names in expected.items():
        assert set(inspect.signature(getattr(server_module, tool_name)).parameters) == parameter_names


def test_read_tool_limit_schemas_are_strict_and_bounded() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    tools = asyncio.run(list_tools())
    expected = {
        ("qlab_get_workspace_overview", "max_depth"): (0, 5),
        ("qlab_get_workspace_overview", "max_cues"): (1, 5000),
        ("qlab_get_workspace_overview", "max_index_cues"): (1, 5000),
        ("qlab_get_workspace_status", "max_cues_scanned"): (1, 5000),
        ("qlab_get_workspace_status", "sample_limit"): (0, 50),
        ("qlab_query_cues", "max_results"): (1, 5000),
        ("qlab_query_cues", "max_cues_scanned"): (1, 5000),
    }
    for (tool_name, field), (minimum, maximum) in expected.items():
        schema = tools[tool_name].inputSchema["properties"][field]
        assert schema["type"] == "integer"
        assert schema["minimum"] == minimum
        assert schema["maximum"] == maximum


def test_read_tool_limits_reject_coerced_values_before_reader(monkeypatch) -> None:
    reader_calls = []

    def unexpected_reader():
        reader_calls.append(True)
        raise AssertionError("invalid limits must not construct a reader")

    monkeypatch.setattr(server_module, "_reader", unexpected_reader)

    async def rejected():
        async with Client(mcp) as client:
            cases = [
                ("qlab_get_workspace_overview", {"workspace_id": "ws-1", "max_depth": True}),
                ("qlab_get_workspace_overview", {"workspace_id": "ws-1", "max_depth": "3"}),
                ("qlab_get_workspace_overview", {"workspace_id": "ws-1", "max_depth": 6}),
                ("qlab_get_workspace_status", {"workspace_id": "ws-1", "sample_limit": True}),
                (
                    "qlab_query_cues",
                    {"workspace_id": "ws-1", "primary_filter": "type", "primary_value": "Audio", "max_results": "10"},
                ),
            ]
            for tool_name, arguments in cases:
                with pytest.raises(Exception):
                    await client.call_tool(tool_name, arguments)
                assert reader_calls == []

    asyncio.run(rejected())


def test_readme_tool_inventory_matches_current_public_surface() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text()
    tool_groups = readme.split("## Tool Groups", 1)[1].split("## Read Model", 1)[0]
    documented_tools = [
        line.split("`", 2)[1]
        for line in tool_groups.splitlines()
        if line.startswith("| `qlab_")
    ]

    assert len(documented_tools) == len(EXPECTED_TOOL_NAMES)
    assert set(documented_tools) == EXPECTED_TOOL_NAMES


def test_fastmcp_public_inventory_excludes_control_and_raw_osc_surface() -> None:
    async def list_tools() -> list[Any]:
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())
    tool_names = {tool.name for tool in tools}

    assert len(tools) == 79
    assert tool_names == EXPECTED_TOOL_NAMES
    assert "qlab_create_cue" not in tool_names
    forbidden_surface_tokens = {"go", "stop", "panic", "raw", "osc", "playback", "live"}
    assert all(
        token not in tool_name.casefold()
        for tool_name in tool_names
        for token in forbidden_surface_tokens
    )

    def schema_fields(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value.get("properties", {})).union(
                *(schema_fields(child) for child in value.values())
            )
        if isinstance(value, list):
            return set().union(*(schema_fields(child) for child in value))
        return set()

    public_input_fields = set().union(
        *(schema_fields(tool.inputSchema) for tool in tools)
    )
    assert public_input_fields.isdisjoint(
        {"address", "osc_address", "osc_path", "raw_osc", "raw_osc_message"}
    )

    real_write_specs = [
        property_spec
        for profile in UPDATE_PROFILES.values()
        for property_spec in profile.properties
        if property_spec.real_write_enabled
    ]
    assert {
        property_spec.name
        for property_spec in real_write_specs
        if "live" in property_spec.modes
    } == {"secondColorName"}

    control_properties = {
        "playbackPosition",
        "playbackPositionID",
        "playbackPosition/next",
        "playbackPosition/previous",
        "playbackPosition/none",
        "playbackPosition/nextSequence",
        "playbackPosition/previousSequence",
        "playlist/next",
        "playlist/previous",
        "panic",
        "auditionGo",
        "auditionPreview",
        "preview",
    }
    assert not {
        property_spec.name
        for property_spec in real_write_specs
        if property_spec.name in control_properties
    }


def test_move_cues_fastmcp_schema_limits_and_nested_model() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_move_cues")

    schema = asyncio.run(get_tool_schema())
    moves = schema["properties"]["moves"]

    assert moves["minItems"] == 1
    assert moves["maxItems"] == 50
    assert moves["items"]["required"] == ["cue_id"]
    assert moves["items"]["properties"]["cue_id"]["format"] == "uuid"


def test_move_cues_fastmcp_returns_structured_plan(monkeypatch) -> None:
    class FakeReader:
        def move_cues(self, workspace_id, moves, dry_run, confirm_token):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert moves == [{"cue_id": "11111111-1111-4111-8111-111111111111", "position": "last"}]
            assert dry_run is True
            assert confirm_token is None
            return {
                "ok": True,
                "status": "planned",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 1,
                "moved_count": 0,
                "failed_count": 0,
                "results": [{"cue_id": moves[0]["cue_id"], "position": "last"}],
                "confirm_token": "confirm:moveCues:v1:payload:signature",
                "rollback": None,
                "errors": None,
                "warnings": ["Dry run only."],
                "message": "Cue move batch planned.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_move_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "moves": [{"cue_id": "11111111-1111-4111-8111-111111111111", "position": "last"}],
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.structured_content["status"] == "planned"
    assert result.structured_content["confirm_token"].startswith("confirm:moveCues:v1:")


def test_create_cues_fastmcp_forwards_ordered_types_and_destination(monkeypatch) -> None:
    class FakeReader:
        def create_cues(self, workspace_id, cue_types, dry_run, cue_list_id, group_id, cue_cart_id, after_cue_id, confirm_token):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_types == ["memo", "audio", "video"]
            assert dry_run is True
            assert cue_list_id == "22222222-2222-4222-8222-222222222222"
            assert group_id is None
            assert cue_cart_id is None
            assert after_cue_id is None
            assert confirm_token is None
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 3,
                "planned_count": 3,
                "created_count": 0,
                "results": [],
                "planned_operations": [
                    {"operation": "new", "args": ["memo", "<anchor>"]},
                    {"operation": "new", "args": ["audio", "<previous_created_cue_id>"]},
                    {"operation": "new", "args": ["video", "<previous_created_cue_id>"]},
                ],
                "executed_operations": [],
                "confirm_token": "confirm:createCues:v2:payload:signature",
                "errors": None,
                "warnings": [],
                "message": "planned",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_create_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cue_types": ["memo", "audio", "video"],
                    "cue_list_id": "22222222-2222-4222-8222-222222222222",
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.is_error is False
    assert result.structured_content["status"] == "dry_run"
    assert result.structured_content["requested_count"] == 3
    assert result.structured_content["confirm_token"].startswith("confirm:createCues:v2:")


def test_create_cues_fastmcp_accepts_one_fifty_and_hundred_but_rejects_out_of_range(monkeypatch) -> None:
    observed: list[list[str]] = []

    class FakeReader:
        def create_cues(self, workspace_id, cue_types, **kwargs):
            observed.append(cue_types)
            return {
                "ok": True, "status": "dry_run", "workspace_id": workspace_id,
                "dry_run": True, "requested_count": len(cue_types), "message": "planned",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())
    base = {
        "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "cue_list_id": "22222222-2222-4222-8222-222222222222",
        "dry_run": True,
    }

    async def run() -> None:
        async with Client(mcp) as client:
            for types in (["audio"], ["video"] * 30 + ["audio"] * 20, ["wait"] * 100):
                result = await client.call_tool("qlab_create_cues", {**base, "cue_types": types})
                assert result.structured_content["requested_count"] == len(types)
            for types in ([], ["audio"] * 101, ["script"]):
                with pytest.raises(Exception):
                    await client.call_tool("qlab_create_cues", {**base, "cue_types": types})

    asyncio.run(run())
    assert [len(types) for types in observed] == [1, 50, 100]
    assert observed[1] == ["video"] * 30 + ["audio"] * 20


def test_delete_cues_fastmcp_schema_limits_and_nested_uuid_model() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_delete_cues")

    schema = asyncio.run(get_tool_schema())
    cue_ids = schema["properties"]["cue_ids"]["anyOf"][0]

    assert cue_ids["minItems"] == 0
    assert cue_ids["maxItems"] == 50
    assert cue_ids["items"]["format"] == "uuid"
    assert "confirm_token" in schema["properties"]


def test_delete_cues_fastmcp_returns_structured_plan(monkeypatch) -> None:
    class FakeReader:
        def delete_cues(self, workspace_id, cue_ids, dry_run, confirm_token, container_id=None, recursive=False, delete_container=False):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_ids == ["11111111-1111-4111-8111-111111111111"]
            assert dry_run is True
            assert confirm_token is None
            assert container_id is None
            assert recursive is False
            return {
                "ok": True,
                "status": "planned",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 1,
                "deleted_count": 0,
                "failed_count": 0,
                "timeout_confirmed_count": 0,
                "results": [{"cue_id": cue_ids[0]}],
                "confirm_token": "confirm:deleteCues:v1:payload:signature",
                "errors": None,
                "warnings": ["Dry run only."],
                "message": "Cue delete batch planned.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_delete_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cue_ids": ["11111111-1111-4111-8111-111111111111"],
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.structured_content["status"] == "planned"
    assert result.structured_content["confirm_token"].startswith("confirm:deleteCues:v1:")


def test_delete_cues_fastmcp_forwards_recursive_container(monkeypatch) -> None:
    class FakeReader:
        def delete_cues(self, workspace_id, cue_ids, dry_run, confirm_token, container_id=None, recursive=False, delete_container=False):
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert cue_ids is None
            assert dry_run is True
            assert confirm_token is None
            assert container_id == "22222222-2222-4222-8222-222222222222"
            assert recursive is True
            return {
                "ok": True,
                "status": "planned",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 2,
                "deleted_count": 0,
                "failed_count": 0,
                "expanded_count": 2,
                "container_id": container_id,
                "recursive": True,
                "preserved_container_id": container_id,
                "results": [],
                "confirm_token": "confirm:deleteCues:v1:payload:signature",
                "errors": None,
                "warnings": [],
                "message": "planned",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_delete_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "container_id": "22222222-2222-4222-8222-222222222222",
                    "recursive": True,
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    assert result.is_error is False
    assert result.structured_content["recursive"] is True
    assert result.structured_content["preserved_container_id"] == "22222222-2222-4222-8222-222222222222"


def test_fastmcp_tool_descriptions_keep_agent_behavior_concepts() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    assert set(tools) == set(EXPECTED_TOOL_CONCEPTS)
    for tool_name, concepts in EXPECTED_TOOL_CONCEPTS.items():
        description = (tools[tool_name].description or "").casefold()
        for concept in concepts:
            assert concept.casefold() in description, f"{tool_name} description lost concept: {concept!r}"


def test_fastmcp_tool_contract_keeps_safety_annotations_and_output_schemas() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    write_tools = {"qlab_edit_audio_cues", "qlab_edit_mic_cues", "qlab_edit_light_cues", "qlab_edit_fade_cues", "qlab_edit_network_cues", "qlab_edit_midi_cues", "qlab_edit_midi_file_cues", "qlab_edit_timecode_cues", "qlab_edit_script_cues", "qlab_edit_video_cues", "qlab_edit_camera_cues", "qlab_edit_text_cues", "qlab_create_cue_lists", "qlab_edit_cue_lists", "qlab_create_cues", "qlab_edit_devamp_cues", "qlab_edit_target_cues", "qlab_edit_control_cues", "qlab_edit_group_cues", "qlab_edit_workspace_general_settings", "qlab_edit_audio_output_patch", "qlab_edit_video_output_route", "qlab_edit_video_stage", "qlab_edit_video_region", "qlab_move_cues", "qlab_move_cue_lists", "qlab_delete_cues", "qlab_open_workspace", "qlab_save_workspace", "qlab_close_workspace"}
    read_only_tools = EXPECTED_TOOL_NAMES - write_tools

    for tool_name in read_only_tools:
        assert tools[tool_name].annotations.readOnlyHint is True, f"{tool_name} lost readOnlyHint"
        if tool_name != "qlab_delete_cues":
            assert tools[tool_name].annotations.destructiveHint is False, f"{tool_name} became destructive"
        assert tools[tool_name].outputSchema, f"{tool_name} lost outputSchema"

    for tool_name in write_tools:
        assert tools[tool_name].annotations.readOnlyHint is False, f"{tool_name} was marked read-only"
        if tool_name in {"qlab_edit_audio_cues", "qlab_edit_mic_cues", "qlab_edit_light_cues", "qlab_edit_fade_cues", "qlab_edit_network_cues", "qlab_edit_midi_cues", "qlab_edit_midi_file_cues", "qlab_edit_timecode_cues", "qlab_edit_script_cues", "qlab_edit_video_cues", "qlab_edit_camera_cues", "qlab_edit_text_cues", "qlab_edit_devamp_cues", "qlab_edit_target_cues", "qlab_edit_control_cues", "qlab_edit_group_cues", "qlab_edit_cue_lists", "qlab_edit_workspace_general_settings", "qlab_edit_audio_output_patch", "qlab_edit_video_output_route", "qlab_edit_video_stage", "qlab_edit_video_region", "qlab_move_cues", "qlab_move_cue_lists", "qlab_delete_cues", "qlab_save_workspace", "qlab_close_workspace"}:
            assert tools[tool_name].annotations.destructiveHint is True
        else:
            assert tools[tool_name].annotations.destructiveHint is False, f"{tool_name} became destructive"
        assert tools[tool_name].annotations.idempotentHint is False, f"{tool_name} was marked idempotent"
        assert tools[tool_name].outputSchema, f"{tool_name} lost outputSchema"


def test_edit_cues_fastmcp_schema_keeps_batch_contract() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    update_schema = tools["qlab_edit_control_cues"].inputSchema
    update_properties = update_schema["properties"]
    update_items = update_properties["updates"]["items"]
    update_item_properties = update_items["properties"]
    update_output = tools["qlab_edit_control_cues"].outputSchema

    assert update_schema["required"] == ["workspace_id", "updates"]
    assert set(update_properties) == {"workspace_id", "updates", "dry_run"}
    assert update_properties["updates"]["minItems"] == 1
    assert update_properties["updates"]["maxItems"] == 50
    assert update_items["required"] == ["cue_id", "properties"]
    assert set(update_item_properties) == {"cue_id", "properties", "confirm_gates"}
    assert "profile" not in update_item_properties
    assert "qlab_edit_cues" not in tools
    assert not hasattr(server_module, "qlab_edit_cues")
    assert update_output["required"] == [
        "ok",
        "status",
        "workspace_id",
        "dry_run",
        "requested_count",
        "planned_count",
        "updated_count",
        "failed_count",
        "timeout_confirmed_count",
        "results",
        "message",
    ]
    assert "updated_with_confirmed_timeouts" in update_output["properties"]["status"]["enum"]
    assert "updateq_plan" in update_output["properties"]["results"]["items"]["properties"]


def test_qlab_edit_fade_cues_fastmcp_response_keeps_fade_basic_token(monkeypatch) -> None:
    token = "confirm:controlCue:v1:test-payload:test-signature"
    calls = []

    class FakeReader:
        def edit_result(self, workspace_id, updates, dry_run):
            calls.append((workspace_id, updates, dry_run))
            assert workspace_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            assert dry_run is True
            assert updates == [
                {
                    "cue_ref": "11111111-1111-4111-8111-111111111111",
                    "profile": "fade_basic",
                    "properties": {"name": "Renamed Fade"},
                    "operations": None,
                    "confirm_gates": None,
                }
            ]
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace_id,
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 1,
                "updated_count": 0,
                "failed_count": 0,
                "timeout_confirmed_count": 0,
                "results": [
                    {
                        "cue_ref": updates[0]["cue_ref"],
                        "cue_id": updates[0]["cue_ref"],
                        "profile": "fade_basic",
                        "status": "dry_run",
                        "properties": updates[0]["properties"],
                        "planned_operations": [
                            {
                                "operation": "set_property",
                                "property": "name",
                                "confirm_token": token,
                            }
                        ],
                        "executed_operations": [],
                    }
                ],
                "message": "Dry run succeeded.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    monkeypatch.setattr(server_module, "edit_remaining_cues", lambda reader, ws, updates, dry, **kwargs:
        reader.edit_result(workspace_id=ws, updates=[{
            "cue_ref": str(item.cue_id), "profile": "fade_basic",
            "properties": item.properties.model_dump(by_alias=True, exclude_unset=True),
            "operations": None, "confirm_gates": None,
        } for item in updates], dry_run=dry))

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_fade_cues",
                {
                    "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "updates": [
                        {
                            "cue_id": "11111111-1111-4111-8111-111111111111",
                            "properties": {"name": "Renamed Fade"},
                        }
                    ],
                    "dry_run": True,
                },
            )

    result = asyncio.run(call_tool())
    planned = result.structured_content["results"][0]["planned_operations"]

    assert len(calls) == 1
    assert result.is_error is False
    assert result.structured_content["dry_run"] is True
    assert result.structured_content["planned_count"] == 1
    assert result.structured_content["updated_count"] == 0
    assert planned[0]["confirm_token"].startswith("confirm:controlCue:v1:")
    assert result.structured_content["results"][0]["executed_operations"] == []


def test_qlab_edit_group_cues_fastmcp_response_keeps_structured_group_failure(monkeypatch) -> None:
    workspace_uuid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_id": cue_id,
        "properties": {"mode": 6},
    }

    class FakeReader:
        def edit_result(self, *, workspace_id: str, updates, dry_run):
            assert workspace_id == workspace_uuid
            assert dry_run is False
            assert updates[0]["properties"] == {"mode": 6}
            return {
                "ok": False,
                "status": "verification_failed",
                "workspace_id": workspace_uuid,
                "dry_run": False,
                "requested_count": 1,
                "planned_count": 1,
                "updated_count": 0,
                "failed_count": 1,
                "timeout_confirmed_count": 0,
                "results": [
                    {
                        "cue_ref": cue_id,
                        "cue_id": cue_id,
                        "profile": "group_basic",
                        "status": "verification_failed",
                        "properties": {"mode": 6},
                        "before": {"mode": 3},
                        "after": {"mode": 3},
                        "executed_operations": [
                            {
                                "operation": "set_property",
                                "property": "mode",
                                "address": f"/workspace/{workspace_uuid}/cue_id/{cue_id}/mode",
                                "args": [6],
                                "mode": "saved",
                                "status": "ok",
                            }
                        ],
                        "errors": {"verification": "Fresh readback did not match requested mode."},
                        "warnings": [],
                    }
                ],
                "message": "Group write was not confirmed by fresh readback.",
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    monkeypatch.setattr(server_module, "edit_group_cues", lambda reader, ws, updates, dry:
        reader.edit_result(workspace_id=ws, updates=[{
            "cue_ref": str(item.cue_id), "profile": "group_basic",
            "properties": item.properties.model_dump(by_alias=True, exclude_unset=True),
            "operations": None, "confirm_gates": None,
        } for item in updates], dry_run=dry))

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_group_cues",
                {"workspace_id": workspace_uuid, "updates": [update], "dry_run": False},
            )

    result = asyncio.run(call_tool())
    payload = result.structured_content
    item = payload["results"][0]

    assert result.is_error is False
    assert payload["status"] == "verification_failed"
    assert item["status"] == "verification_failed"
    assert len(item["executed_operations"]) == 1
    assert item["executed_operations"][0]["address"].endswith("/mode")
    assert item["after"]["mode"] == 3


def test_tool_metadata_exposes_titles_descriptions_and_read_only_annotations() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    assert set(tools) == {
        "qlab_get_fonts",
        "qlab_analyze_audio_file",
        "qlab_search_media_files",
        "qlab_get_video_effect_catalogue",
        "qlab_get_workspace_document",
        "qlab_open_workspace",
        "qlab_save_workspace",
        "qlab_close_workspace",
        "qlab_edit_audio_cues",
        "qlab_edit_mic_cues",
        "qlab_edit_light_cues",
        "qlab_edit_fade_cues",
        "qlab_edit_network_cues",
        "qlab_edit_midi_cues",
        "qlab_edit_midi_file_cues",
        "qlab_edit_timecode_cues",
        "qlab_edit_script_cues",

        "qlab_edit_video_cues",
        "qlab_edit_camera_cues",
        "qlab_edit_text_cues",
        "qlab_edit_control_cues",
        "qlab_edit_group_cues",
        "qlab_edit_devamp_cues",
        "qlab_edit_target_cues",
        "qlab_get_fade_cue_details",
        "qlab_get_fade_cues",
        "qlab_get_midi_cue_details",
        "qlab_get_midi_cues",
        "qlab_get_network_cue_details",
        "qlab_get_network_cues",
        "qlab_get_script_cue_details",
        "qlab_get_script_cues",
        "qlab_get_timecode_cue_details",
        "qlab_get_timecode_cues",
        "qlab_get_control_cues",
        "qlab_get_control_cue_details",
        "qlab_get_light_cues",
        "qlab_get_light_cue_details",
        "qlab_get_group_cues",
        "qlab_get_group_cue_details",
        "qlab_get_video_cues",
        "qlab_get_video_cue_details",
        "qlab_get_text_cues",
        "qlab_get_text_cue_details",
        "qlab_get_camera_cues",
        "qlab_get_camera_cue_details",
        "qlab_get_mic_cues",
        "qlab_get_mic_cue_details",
        "qlab_get_audio_cues",
        "qlab_get_audio_cue_details",
        "qlab_get_cue_lists",
        "qlab_get_cue_list_details",
        "qlab_get_cue_cart_details",
        "qlab_check_connection",
        "qlab_get_workspace_overview",
        "qlab_get_workspace_status",
        "qlab_get_workspace_general_settings",
        "qlab_get_workspace_audio_settings",
        "qlab_get_workspace_video_settings",
        "qlab_get_video_stage",
        "qlab_get_video_output_route",
        "qlab_get_video_region",
        "qlab_get_workspace_light_settings",
        "qlab_get_workspace_network_settings",
        "qlab_get_workspace_midi_settings",
        "qlab_query_cues",
        "qlab_get_cue_details",
        "qlab_check_write_readiness",
        "qlab_create_cues",
        "qlab_create_cue_lists",
        "qlab_edit_cue_lists",
        "qlab_edit_workspace_general_settings",
        "qlab_edit_audio_output_patch",
        "qlab_edit_video_output_route",
        "qlab_edit_video_stage",
        "qlab_edit_video_region",
        "qlab_move_cues",
        "qlab_move_cue_lists",
        "qlab_delete_cues",
    }

    check = tools["qlab_check_connection"]
    assert check.title == "Check QLab Connection"
    assert "passcode" in check.description
    assert "/connect permission scopes" in check.description
    assert check.annotations.readOnlyHint is True
    assert check.annotations.destructiveHint is False

    overview = tools["qlab_get_workspace_overview"]
    assert overview.title == "Get QLab Workspace Overview"
    assert "first structural read" in overview.description
    assert overview.inputSchema["properties"]["cue_index_profile"]["default"] == "minimal"
    assert overview.inputSchema["properties"]["max_cues"]["maximum"] == 5000
    assert overview.inputSchema["properties"]["max_index_cues"]["maximum"] == 5000
    assert overview.inputSchema["properties"]["max_index_cues"]["default"] == 5000
    assert overview.inputSchema["properties"]["include_global_count"]["default"] is False
    assert "cueLists/uniqueIDs" in overview.inputSchema["properties"]["include_global_count"]["description"]
    assert "cue list roots" in overview.inputSchema["properties"]["include_global_count"]["description"]
    assert "agent_summary" in overview.outputSchema["properties"]
    agent_summary_schema = overview.outputSchema["properties"]["agent_summary"]
    agent_summary_variants = agent_summary_schema.get("anyOf", [agent_summary_schema])
    assert any(variant.get("type") == "object" for variant in agent_summary_variants)
    assert overview.annotations.readOnlyHint is True
    assert overview.annotations.destructiveHint is False
    assert overview.annotations.idempotentHint is True
    assert overview.annotations.openWorldHint is True

    create_cues = tools["qlab_create_cues"]
    planned_count_description = create_cues.outputSchema["properties"]["planned_count"]["description"]
    assert "plan operations" in planned_count_description
    assert "requested_count" in planned_count_description
    assert "created_count" in planned_count_description

    status = tools["qlab_get_workspace_status"]
    assert status.title == "Get QLab Workspace Status"
    assert "Workspace Status" in status.description
    assert status.inputSchema["properties"]["profile"]["default"] == "summary"
    assert "enum" not in status.inputSchema["properties"]["profile"]
    assert status.inputSchema["properties"]["max_cues_scanned"]["default"] == 1000
    assert status.inputSchema["properties"]["sample_limit"]["maximum"] == 50
    assert "sections" in status.outputSchema["properties"]
    sections_schema = status.outputSchema["properties"]["sections"]
    sections_properties = sections_schema["properties"]
    warnings_properties = sections_properties["warnings_summary"]["properties"]
    assert {
        "coverage",
        "evidence_sources",
        "cue_evidence_available",
        "settings_evidence_available",
        "sample_flagged_cues",
        "known_settings_problem_count",
        "known_settings_problem_counts",
        "sample_settings_problems",
    } <= set(warnings_properties)
    assert status.annotations.readOnlyHint is True
    assert status.annotations.destructiveHint is False

    settings_tools = {
        name: tools[name]
        for name in (
            "qlab_get_workspace_general_settings",
            "qlab_get_workspace_audio_settings",
            "qlab_get_workspace_video_settings",
            "qlab_get_workspace_light_settings",
            "qlab_get_workspace_network_settings",
            "qlab_get_workspace_midi_settings",
        )
    }
    for settings in settings_tools.values():
        assert settings.annotations.readOnlyHint is True
        assert settings.annotations.destructiveHint is False
        assert "data" in settings.outputSchema["properties"]
        assert "domain" in settings.outputSchema["properties"]
        assert "coverage" in settings.outputSchema["properties"]
        assert {"section", "mode", "sections", "requests", "kind"}.isdisjoint(
            settings.inputSchema["properties"]
        )

    audio_settings = settings_tools["qlab_get_workspace_audio_settings"]
    assert audio_settings.title == "Get QLab Workspace Audio Settings"
    assert audio_settings.inputSchema["properties"]["view"]["default"] == "overview"
    assert audio_settings.inputSchema["properties"]["profile"]["enum"] == ["safe", "technical", "exhaustive"]

    video_settings = settings_tools["qlab_get_workspace_video_settings"]
    assert video_settings.title == "Get QLab Workspace Video Settings"
    assert set(video_settings.inputSchema["properties"]) == {"workspace_id"}

    query = tools["qlab_query_cues"]
    assert query.title == "Query QLab Cues"
    assert "optional AND filters" in query.description
    assert query.inputSchema["properties"]["max_results"]["default"] == 500
    assert query.inputSchema["properties"]["max_results"]["maximum"] == 5000
    assert query.inputSchema["properties"]["max_cues_scanned"]["default"] == 500
    assert query.inputSchema["properties"]["max_cues_scanned"]["maximum"] == 5000
    assert "enum" not in query.inputSchema["properties"]["primary_filter"]
    assert "query_completeness" in query.outputSchema["properties"]
    assert "query_completeness_reasons" in query.outputSchema["properties"]
    assert "id_only_unscanned_count" in query.outputSchema["properties"]
    assert "omitted_branches" in query.outputSchema["properties"]
    assert "partial_branches" in query.outputSchema["properties"]
    assert "warnings" in query.outputSchema["properties"]
    assert query.annotations.readOnlyHint is True
    assert query.annotations.destructiveHint is False

    details = tools["qlab_get_cue_details"]
    assert details.title == "Get QLab Cue Details"
    assert "valuesForKeys" in details.description
    assert "enum" not in details.inputSchema["properties"]["profile"]
    assert "Inspector-style" in details.inputSchema["properties"]["profile"]["description"]
    assert "heavy/sensitive" in details.inputSchema["properties"]["profile"]["description"]
    assert "enum" not in query.inputSchema["properties"]["profile"]
    cue_ref_schema = details.inputSchema["properties"]["cue_ref"]
    assert cue_ref_schema["anyOf"][0]["type"] == "string"
    assert cue_ref_schema["anyOf"][1]["type"] == "array"
    assert cue_ref_schema["anyOf"][1]["maxItems"] == 50
    assert "exact cue number or unique ID" in cue_ref_schema["description"]
    assert details.annotations.readOnlyHint is True

    readiness = tools["qlab_check_write_readiness"]
    assert readiness.title == "Check QLab Write Readiness"
    assert "without sending any mutating OSC commands" in readiness.description
    assert readiness.annotations.readOnlyHint is True
    assert readiness.annotations.destructiveHint is False
    assert "workspace_id" in readiness.inputSchema["required"]
    assert "write_disabled" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "workspace_not_found" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "workspace_ambiguous" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "workspace_unavailable" in readiness.outputSchema["properties"]["status"]["enum"]
    assert "suggested_action" in readiness.outputSchema["properties"]

    create = tools["qlab_create_cues"]
    assert create.title == "Create QLab Cues"
    assert "Cue Templates" in create.description
    assert create.annotations.readOnlyHint is False
    assert create.annotations.destructiveHint is False
    assert create.annotations.idempotentHint is False
    assert create.inputSchema["properties"]["cue_types"]["items"]["enum"] == [
        "memo",
        "group",
        "wait",
        "audio",
        "mic",
        "video",
        "camera",
        "text",
        "light",
        "fade",
        "network",
        "midi",
        "midi_file",
        "timecode",
        "start",
        "stop",
        "pause",
        "load",
        "reset",
        "devamp",
        "goto",
        "target",
        "arm",
        "disarm",
    ]
    assert "dry_run" in create.inputSchema["properties"]
    assert "workspace_id" in create.inputSchema["required"]
    assert "cue_types" in create.inputSchema["required"]
    assert "after_cue_id" not in create.inputSchema.get("required", [])
    assert {"cue_list_id", "group_id", "cue_cart_id"} <= set(create.inputSchema["properties"])
    assert "parent_container_id" not in create.inputSchema["properties"]
    assert create.outputSchema["properties"]["status"]["enum"] == [
        "dry_run",
        "created",
        "partial_failed",
        "preflight_failed",
        "verification_failed",
        "workspace_not_found",
        "workspace_ambiguous",
        "workspace_unavailable",
    ]
    assert "destination" in create.outputSchema["properties"]
    assert "results" in create.outputSchema["properties"]

    edit = tools["qlab_edit_control_cues"]
    assert edit.title == "Edit QLab Control Cues"
    assert "Tokens expire after five minutes" in edit.description
    assert "batch-edit" in edit.meta["fastmcp"]["tags"]
    assert edit.annotations.readOnlyHint is False
    assert edit.annotations.destructiveHint is True
    assert edit.annotations.idempotentHint is False
    assert "workspace_id" in edit.inputSchema["required"]
    assert "updates" in edit.inputSchema["required"]
    assert "cue_ref" not in edit.inputSchema["properties"]
    assert edit.inputSchema["properties"]["updates"]["minItems"] == 1
    assert edit.inputSchema["properties"]["updates"]["maxItems"] == 50
    edit_item = edit.inputSchema["properties"]["updates"]["items"]["properties"]
    assert edit_item["cue_id"]["format"] == "uuid"
    assert "profile" not in edit_item
    assert "updated_with_confirmed_timeouts" in edit.outputSchema["properties"]["status"]["enum"]
    assert "workspace_not_found" in edit.outputSchema["properties"]["status"]["enum"]
    assert "workspace_ambiguous" in edit.outputSchema["properties"]["status"]["enum"]
    assert "workspace_unavailable" in edit.outputSchema["properties"]["status"]["enum"]
    assert "per cue item" in edit.outputSchema["properties"]["timeout_confirmed_count"]["description"]
    result_item = edit.outputSchema["properties"]["results"]["items"]["properties"]
    assert "dry_run_preflight_failed" in result_item["status"]["enum"]
    assert "QLAB_UPDATE_DEBUG" in result_item["debug"]["description"]

    move = tools["qlab_move_cues"]
    assert move.annotations.destructiveHint is True
    move_item = move.inputSchema["properties"]["moves"]["items"]["properties"]
    assert "Exact source cue UUID" in move_item["cue_id"]["description"]
    assert "exactly one linear placement field" in move_item["destination_index"]["description"]
    assert "both cart_row and cart_column" in move_item["cart_row"]["description"]

    delete = tools["qlab_delete_cues"]
    assert delete.title == "Delete QLab Cues"
    assert "explicit leaves" in delete.description
    assert delete.annotations.readOnlyHint is False
    assert delete.annotations.destructiveHint is True
    assert delete.annotations.idempotentHint is False
    delete_cue_ids_schema = delete.inputSchema["properties"]["cue_ids"]["anyOf"][0]
    assert delete_cue_ids_schema["minItems"] == 0
    assert delete_cue_ids_schema["maxItems"] == 50
    assert delete_cue_ids_schema["items"]["format"] == "uuid"
    assert "container_id" in delete.inputSchema["properties"]
    assert "recursive" in delete.inputSchema["properties"]
    assert "recursive=false" in delete.inputSchema["properties"]["container_id"]["description"]
    assert "empty Group" in delete.inputSchema["properties"]["container_id"]["description"]
    assert "confirm:deleteCues:v1:" in delete.inputSchema["properties"]["confirm_token"]["description"]
    assert "verification_failed" in delete.outputSchema["properties"]["status"]["enum"]


def test_workspace_settings_tool_schema_and_annotations_are_conservative() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tool = next(tool for tool in asyncio.run(list_tools()) if tool.name == "qlab_edit_workspace_general_settings")
    schema = tool.inputSchema
    assert schema["properties"]["workspace_id"]["format"] == "uuid"
    operation_schema = schema["properties"]["operation"]
    assert len(operation_schema["anyOf"]) == 2
    numeric_operation = operation_schema["anyOf"][0]
    assert numeric_operation["properties"]["kind"]["const"] == "general.minGoTime"
    value_schema = numeric_operation["properties"]["value"]
    assert value_schema["anyOf"][0]["type"] == "integer"
    assert value_schema["anyOf"][1]["type"] == "number"
    assert value_schema["minimum"] == 0
    assert set(schema["properties"]) == {"workspace_id", "operation", "dry_run", "confirm_token"}
    assert "oneOf" not in schema["properties"]["operation"]
    assert "selectionIsPlayhead" in json.dumps(schema)
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.destructiveHint is True
    assert tool.annotations.idempotentHint is False
    assert tool.annotations.openWorldHint is True
    assert set(tool.meta["fastmcp"]["tags"]) == {
        "qlab", "settings", "general-settings", "write-mode", "gated-write"
    }


@pytest.mark.parametrize("value", ["0.6", True, False, None, -0.1, math.inf, math.nan])
def test_general_settings_tool_rejects_coercible_non_numeric_values_before_handler(
    monkeypatch: pytest.MonkeyPatch,
    value: object,
) -> None:
    called = False

    class FakeReader:
        def edit_workspace_settings(self, **_kwargs: object) -> None:
            nonlocal called
            called = True
            raise AssertionError("invalid input reached the settings handler")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_workspace_general_settings",
                {
                    "workspace_id": "11111111-1111-4111-8111-111111111111",
                    "operation": {"kind": "general.minGoTime", "value": value},
                    "dry_run": True,
                },
            )

    with pytest.raises(ToolError, match=r"validation error(?:s)? for call\[qlab_edit_workspace_general_settings\]"):
        asyncio.run(call_tool())
    assert called is False


def test_workspace_settings_tool_rejects_non_enabled_operation_before_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    class FakeReader:
        def edit_workspace_settings(self, **_kwargs: object) -> None:
            nonlocal called
            called = True
            raise AssertionError("non-enabled operation reached the settings handler")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_workspace_general_settings",
                {
                    "workspace_id": "11111111-1111-4111-8111-111111111111",
                    "operation": {"kind": "general.unknown", "value": True},
                    "dry_run": True,
                },
            )

    with pytest.raises(ToolError, match=r"validation error(?:s)? for call\[qlab_edit_workspace_general_settings\]"):
        asyncio.run(call_tool())
    assert called is False


@pytest.mark.parametrize(
    "workspace_id",
    [
        "11111111111141118111111111111111",
        "{11111111-1111-4111-8111-111111111111}",
        "urn:uuid:11111111-1111-4111-8111-111111111111",
    ],
)
def test_workspace_settings_tool_rejects_non_canonical_uuid_before_handler(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: str,
) -> None:
    called = False

    class FakeReader:
        def edit_workspace_settings(self, _request: object) -> None:
            nonlocal called
            called = True
            raise AssertionError("non-canonical UUID reached the settings handler")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_edit_workspace_general_settings",
                {
                    "workspace_id": workspace_id,
                    "operation": {"kind": "general.minGoTime", "value": 0.4},
                    "dry_run": True,
                },
            )

    with pytest.raises(ToolError, match=r"validation error(?:s)? for call\[qlab_edit_workspace_general_settings\]"):
        asyncio.run(call_tool())
    assert called is False


def test_workspace_settings_tool_forwards_typed_request_to_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeReader:
        def edit_workspace_settings(self, request: Any) -> dict[str, object]:
            captured.update(request.model_dump(mode="json"))
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": str(request.workspace_id),
                "operation": "general.minGoTime",
                "dry_run": True,
                "requested_value": request.operation.value,
                "baseline": 0.2,
                "readback": None,
                "planned_operations": [{"operation": "set_workspace_setting"}],
                "executed_operations": [],
                "confirm_token": "confirm:workspaceSettings:v1:test",
                "readiness": {"ok": True},
                "activity": {"active_count": 0},
                "verification": None,
                "timeout_confirmation": None,
                "retry_unsafe": False,
                "errors": None,
                "warnings": [],
                "error_code": None,
                "suggested_action": None,
                "message": "dry run",
            }

        def close(self) -> None:
            return None

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())
    result = server_module.qlab_edit_workspace_general_settings(
        UUID("11111111-1111-4111-8111-111111111111"),
        {"kind": "general.minGoTime", "value": 0.4},
        True,
        None,
    )
    assert result.status == "dry_run"
    assert captured == {
        "workspace_id": "11111111-1111-4111-8111-111111111111",
        "operation": {"kind": "general.minGoTime", "value": 0.4},
        "dry_run": True,
        "confirm_token": None,
    }


def test_overview_partial_result_suggests_bounded_follow_up() -> None:
    result = overview_success_payload(
        {
            "limits": {"truncated": True, "truncation_reasons": ["max_depth"]},
            "summary": {"health_counts_status": "partial_non_authoritative"},
            "warnings": ["Tree preview is partial (max_depth)."],
        }
    )

    assert result["partial"] is True
    assert "qlab_query_cues" in result["suggested_action"]
    assert "max_depth" in result["suggested_action"]


def test_create_tool_uses_qlab_template_defaults_without_property_input() -> None:
    async def get_tool_schema() -> dict[str, Any]:
        async with Client(mcp) as client:
            tools = await client.list_tools()
        return next(tool.inputSchema for tool in tools if tool.name == "qlab_create_cues")

    schema = asyncio.run(get_tool_schema())

    assert "properties" not in schema["properties"]


def test_server_masks_internal_error_details_and_sets_tool_timeouts() -> None:
    async def tool_timeouts():
        return {
            name: (await mcp.get_tool(name)).timeout
            for name in (
                "qlab_check_connection",
                "qlab_get_workspace_overview",
                "qlab_get_workspace_status",
                "qlab_get_workspace_general_settings",
                "qlab_get_workspace_audio_settings",
                "qlab_get_workspace_video_settings",
                "qlab_get_workspace_light_settings",
                "qlab_get_workspace_network_settings",
                "qlab_get_workspace_midi_settings",
                "qlab_query_cues",
                "qlab_get_cue_details",
                "qlab_check_write_readiness",
                "qlab_create_cues",
                "qlab_edit_control_cues",
                    )
        }

    assert mcp._mask_error_details is True
    assert asyncio.run(tool_timeouts()) == {
        "qlab_check_connection": CHECK_CONNECTION_TIMEOUT,
        "qlab_get_workspace_overview": WORKSPACE_OVERVIEW_TIMEOUT,
        "qlab_get_workspace_status": WORKSPACE_STATUS_TIMEOUT,
        "qlab_get_workspace_general_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_audio_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_video_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_light_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_network_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_midi_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_query_cues": QUERY_CUES_TIMEOUT,
        "qlab_get_cue_details": CUE_DETAILS_TIMEOUT,
        "qlab_check_write_readiness": WRITE_READINESS_TIMEOUT,
        "qlab_create_cues": CREATE_CUES_TIMEOUT,
        "qlab_edit_control_cues": UPDATE_CUES_TIMEOUT,
    }


def test_run_tool_closes_reader_on_success(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    result = _run_tool(lambda supplied_reader: supplied_reader)

    assert result is reader
    assert reader.closed is True


def test_run_tool_sets_read_deadline_and_closes_reader(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False
            self.deadline: float | None = None

        def set_read_deadline(self, timeout: float) -> None:
            self.deadline = timeout

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    assert _run_tool(lambda supplied_reader: supplied_reader, timeout=3.0) is reader
    assert reader.deadline == 3.0
    assert reader.closed is True


def test_read_tool_wrappers_pass_their_fastmcp_timeout_to_run_tool(monkeypatch) -> None:
    timeouts: list[float | None] = []

    def capture(_factory, timeout=None):
        timeouts.append(timeout)
        return "ok"

    monkeypatch.setattr(server_module, "_run_tool", capture)

    assert server_module.qlab_check_connection() == "ok"
    assert server_module.qlab_check_write_readiness("ws-1") == "ok"
    assert timeouts == [CHECK_CONNECTION_TIMEOUT, WRITE_READINESS_TIMEOUT]


def test_write_tool_wrappers_do_not_pass_outer_reader_deadlines(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    def capture(_factory, **kwargs):
        calls.append(kwargs)
        return "ok"

    monkeypatch.setattr(server_module, "_run_tool", capture)

    assert server_module.qlab_edit_control_cues("00000000-0000-0000-0000-000000000001", [], dry_run=True) == "ok"
    assert server_module.qlab_move_cues("ws-1", [], dry_run=True) == "ok"
    assert server_module.qlab_delete_cues("ws-1", [], dry_run=True) == "ok"
    assert calls == [{}, {}, {}]


def test_run_tool_closes_reader_on_failure(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    try:
        _run_tool(lambda _reader: (_ for _ in ()).throw(QLabReplyError("denied", "badpass", "/workspaces")))
    except ToolError:
        pass
    else:
        raise AssertionError("Expected ToolError")

    assert reader.closed is True


def test_expected_tool_errors_are_sanitized() -> None:
    def denied_with_sensitive_payload(_reader: Any) -> None:
        raise QLabReplyError(
            "denied",
            {"fileTarget": "/Users/stage/secret.wav", "passcode": "1234"},
            "/workspace/ws-1/settings/network/patchList",
        )

    try:
        _run_tool(denied_with_sensitive_payload)
    except ToolError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ToolError")

    assert "denied" in message
    assert "secret.wav" not in message
    assert "1234" not in message
    assert "patchList" not in message


def test_public_tool_validation_returns_structured_json_error() -> None:
    result = qlab_query_cues("ws-1", "type", "Audio", max_results=0)
    payload = result.model_dump()

    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["partial"] is False
    assert payload["error_code"] == "validation_failed"
    assert "max_results must be 1 or greater" in payload["message"]
    assert payload["received"]["max_results"] == 0
    assert payload["allowed"]["max_results"] == "1..5000"
    assert "Traceback" not in json.dumps(payload)


def test_schema_validation_rejects_invalid_domain_input_before_tool_call() -> None:
    async def call_tool():
        async with Client(mcp) as client:
            return await client.call_tool(
                "qlab_query_cues",
                {"workspace_id": "ws-1", "primary_filter": "type", "primary_value": "Audio", "max_results": 0},
            )

    with pytest.raises(ToolError, match="greater than or equal to 1"):
        asyncio.run(call_tool())


def test_python_surface_has_no_plural_update_alias() -> None:
    alias = "update_" + "cues"
    public_alias = "qlab_" + alias
    pattern = re.compile(rf"\b(?:{re.escape(alias)}|{re.escape(public_alias)})\b")
    paths = [*sorted((PROJECT_ROOT / "src").rglob("*.py")), *sorted((PROJECT_ROOT / "tests").rglob("*.py"))]
    matches = [str(path.relative_to(PROJECT_ROOT)) for path in paths if pattern.search(path.read_text())]
    assert matches == []


def test_query_cues_rejects_exhaustive_profile_before_reader(monkeypatch) -> None:
    class ExplodingReader:
        def query_cues(self, **kwargs):
            raise AssertionError("exhaustive query profile must be rejected before reading cues")

    monkeypatch.setattr(server_module, "_reader", lambda: ExplodingReader())

    payload = qlab_query_cues("ws-1", "type", "Audio", profile="exhaustive").model_dump()

    assert payload["ok"] is False
    assert payload["error_code"] == "cue_profile_not_supported"
    assert payload["received"]["profile"] == "exhaustive"


def test_sensitive_cue_query_limit_rejects_large_result_count_before_reader(monkeypatch) -> None:
    class ExplodingReader:
        def query_cues(self, **kwargs):
            raise AssertionError("large sensitive query must be rejected before reading cues")

    monkeypatch.setattr(server_module, "_reader", lambda: ExplodingReader())

    payload = qlab_query_cues("ws-1", "type", "Audio", profile="full_sensitive", max_results=51).model_dump()

    assert payload["ok"] is False
    assert payload["error_code"] == "cue_payload_too_large"
    assert payload["allowed"]["max_results"] == 50


def test_public_cue_details_reports_clear_batch_limit_as_structured_json(monkeypatch) -> None:
    class FakeReader:
        def get_cue_details(self, workspace_id, cue_ref, profile):
            raise ValueError("cue_ref list can include at most 50 cues")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_cue_details("ws-1", ["10"] * 51)
    payload = result.model_dump()

    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["partial"] is False
    assert payload["error_code"] == "cue_batch_too_large"
    assert payload["allowed"] == {"max_cues": 50}
    assert "cue_ref list can include at most 50 cues" in payload["message"]
    assert payload["requested_count"] == 51
    assert payload["failed_count"] == 51


def test_structured_read_error_keeps_original_sanitized_message(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            raise OscTimeoutError("read deadline exhausted")

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    payload = qlab_get_workspace_overview("ws-1").model_dump()

    assert payload["message"] == "read deadline exhausted"


def test_public_read_tools_redact_internal_exception_paths(monkeypatch) -> None:
    internal_message = "/Users/filarmonica/Documents/qlab-mcp-osc/src/qlab_mcp/server.py: bad profile"

    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            raise ValueError(internal_message)

        def get_workspace_status(self, **kwargs):
            raise ValueError(internal_message)

        def get_workspace_settings(self, **kwargs):
            raise ValueError(internal_message)

        def get_workspace_setting_details(self, **kwargs):
            raise ValueError(internal_message)

        def query_cues(self, **kwargs):
            raise ValueError(internal_message)

        def get_cue_details(self, workspace_id, cue_ref, profile):
            raise ValueError(internal_message)

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    results = [
        qlab_get_workspace_overview("ws-1").model_dump(),
        qlab_get_workspace_status("ws-1").model_dump(),
        qlab_get_workspace_general_settings("ws-1").model_dump(),
        qlab_get_workspace_audio_settings("ws-1").model_dump(),
        qlab_get_workspace_video_settings("ws-1").model_dump(),
        qlab_get_workspace_light_settings("ws-1").model_dump(),
        qlab_get_workspace_network_settings("ws-1").model_dump(),
        qlab_get_workspace_midi_settings("ws-1").model_dump(),
        qlab_query_cues("ws-1", "type", "Audio").model_dump(),
        qlab_get_cue_details("ws-1", "10", "bad_profile").model_dump(),
    ]

    for payload in results:
        serialized = json.dumps(payload)
        assert payload["ok"] is False
        assert payload["status"] == "error"
        assert payload["partial"] is False
        assert payload["error_code"] == "validation_failed"
        assert payload["message"] == "[redacted_internal_path]"
        assert "/qlab-mcp-osc/" not in serialized
        assert "Traceback" not in serialized
        assert "pydantic" not in serialized.lower()


def test_public_read_success_shapes_have_meaningful_ok_status_partial(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "workspace": {"displayName": "demo.qlab5"},
                "cue_count": 1,
                "summary": {"total_cue_ids_status": "known", "health_counts_status": "known"},
                "cue_lists": [],
                "limits": {"truncated": False},
                "warnings": [],
                "errors": None,
            }

        def query_cues(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "filters": [{"filter": "type", "value": "Audio"}],
                "profile": "basic_safe",
                "scanned_count": 1,
                "matched_count": 1,
                "returned_count": 1,
                "total_cue_ids": 1,
                "query_completeness": "complete",
                "truncated": False,
                "scanned_all_cues": True,
                "result_limited": False,
                "limits": {"max_results": 500, "max_cues_scanned": 500},
                "cues": [{"uniqueID": "cue-1", "type": "Audio"}],
                "warnings": [],
                "errors": None,
            }

        def get_cue_details(self, workspace_id, cue_ref, profile):
            return {
                "workspace_id": workspace_id,
                "cue_ref": cue_ref,
                "profile": profile,
                "cue_type": "Audio",
                "properties": {"uniqueID": "cue-1", "type": "Audio"},
                "errors": None,
                "warnings": [],
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    overview = qlab_get_workspace_overview("ws-1").model_dump()
    query = qlab_query_cues("ws-1", "type", "Audio").model_dump()
    details = qlab_get_cue_details("ws-1", "cue-1").model_dump()

    for payload in (overview, query, details):
        assert payload["ok"] is True
        assert payload["status"] == "ok"
        assert payload["partial"] is False


def test_public_read_partial_success_shapes_have_meaningful_ok_status_partial(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "workspace": {"displayName": "demo.qlab5"},
                "cue_count": 1,
                "summary": {"total_cue_ids_status": "partial", "health_counts_status": "partial_non_authoritative"},
                "cue_lists": [],
                "limits": {"truncated": True},
                "warnings": ["partial"],
                "errors": None,
            }

        def query_cues(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "filters": [{"filter": "type", "value": "Audio"}],
                "profile": "basic_safe",
                "scanned_count": 1,
                "matched_count": 1,
                "returned_count": 1,
                "total_cue_ids": 2,
                "query_completeness": "partial",
                "query_completeness_reasons": ["max_cues_scanned"],
                "truncated": True,
                "truncation_reasons": ["max_cues_scanned"],
                "scanned_all_cues": False,
                "result_limited": False,
                "limits": {"max_results": 500, "max_cues_scanned": 1},
                "cues": [{"uniqueID": "cue-1", "type": "Audio"}],
                "warnings": ["partial"],
                "errors": None,
            }

        def get_cue_details(self, workspace_id, cue_ref, profile):
            return {
                "workspace_id": workspace_id,
                "cue_ref": cue_ref,
                "profile": profile,
                "cue_type": None,
                "properties": {},
                "errors": {"error_code": "cue_ref_unresolved"},
                "warnings": ["partial"],
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    overview = qlab_get_workspace_overview("ws-1").model_dump()
    query = qlab_query_cues("ws-1", "type", "Audio", max_cues_scanned=1).model_dump()
    details = qlab_get_cue_details("ws-1", "missing").model_dump()

    for payload in (overview, query, details):
        assert payload["status"] in {"partial", "error"}
        if payload["status"] == "partial":
            assert payload["ok"] is True
            assert payload["partial"] is True
        else:
            assert payload["ok"] is False
            assert payload["partial"] is False


def test_public_cue_details_batch_normalizes_item_shapes(monkeypatch) -> None:
    class FakeReader:
        def get_cue_details(self, workspace_id, cue_ref, profile):
            return {
                "ok": True,
                "workspace_id": workspace_id,
                "requested_count": 3,
                "succeeded_count": 2,
                "failed_count": 1,
                "profile": profile,
                "results": [
                    {
                        "workspace_id": workspace_id,
                        "cue_ref": "ok",
                        "profile": profile,
                        "cue_type": "Audio",
                        "properties": {"uniqueID": "ok"},
                        "errors": None,
                        "warnings": [],
                    },
                    {
                        "workspace_id": workspace_id,
                        "cue_ref": "partial",
                        "profile": profile,
                        "cue_type": "Audio",
                        "properties": {"uniqueID": "partial"},
                        "errors": {"notes": "read failed"},
                        "warnings": [],
                    },
                    {
                        "workspace_id": workspace_id,
                        "cue_ref": "missing",
                        "profile": profile,
                        "cue_type": None,
                        "properties": {},
                        "errors": {"error_code": "cue_ref_unresolved", "message": "Cue ref could not be resolved or read."},
                        "warnings": [],
                    },
                ],
                "errors": {"missing": "cue_ref_unresolved"},
                "warnings": ["partial"],
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    payload = qlab_get_cue_details("ws-1", ["ok", "partial", "missing"]).model_dump()

    assert payload["ok"] is True
    assert payload["status"] == "partial"
    assert payload["partial"] is True
    assert [(item["ok"], item["status"], item["partial"]) for item in payload["results"]] == [
        (True, "ok", False),
        (True, "partial", True),
        (False, "error", False),
    ]


def test_overview_public_tool_preserves_agent_summary(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_overview(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "workspace": {"displayName": "demo.qlab5"},
                "cue_count": 879,
                "cue_count_meaning": "inspected_cues",
                "known_total_cues": 1424,
                "known_total_cues_status": "partial",
                "known_total_cues_source": "bounded_shallow_traversal+children/uniqueIDs/shallow",
                "known_total_cues_meaning": "cue_items_including_cue_lists",
                "summary": {"cue_lists": 7, "inspected_cues": 879},
                "agent_summary": {
                    "workspace_total_for_humans": "1417 cues in 7 lists",
                    "workspace_total_status": "partial",
                    "known_total_cue_items": 1424,
                    "cue_lists": 7,
                    "metadata_inspected_cues": 879,
                    "id_only_counted_cues": 545,
                    "metadata_partial": True,
                    "main_partial_branches": [{"number": "TEKNO", "child_count": 545}],
                },
                "cue_lists": [],
                "limits": {"truncated": True, "truncation_reasons": ["child_metadata_unavailable"]},
                "warnings": ["metadata partial"],
                "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_workspace_overview()
    payload = result.model_dump()

    assert payload["agent_summary"]["workspace_total_for_humans"] == "1417 cues in 7 lists"
    assert payload["agent_summary"]["id_only_counted_cues"] == 545
    assert payload["known_total_cues_meaning"] == "cue_items_including_cue_lists"


def test_workspace_status_public_tool_preserves_sections(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_status(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "profile": "summary",
                "sections": {
                    "warnings_summary": {"source": "derived_from_cues", "available": True, "broken_count": 1},
                    "logs": {"source": "not_exposed", "available": False},
                    "timecode_live_status": {
                        "source": "qlab_osc",
                        "available": True,
                        "sample": [{"cue_ref": "list-1", "currentTimecode/text": "01:02:03:04"}],
                    },
                },
                "summary": {"cue_scan_completeness": "complete", "scanned_count": 12},
                "limits": {"max_cues_scanned": 1000, "sample_limit": 10},
                "warnings": [],
                "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_get_workspace_status("ws-1")
    payload = result.model_dump()

    assert payload["sections"]["warnings_summary"]["broken_count"] == 1
    assert payload["sections"]["logs"]["source"] == "not_exposed"
    assert payload["sections"]["timecode_live_status"]["sample"][0] == {
        "cue_ref": "list-1",
        "currentTimecode/text": "01:02:03:04",
    }


def test_query_public_tool_preserves_completeness_fields(monkeypatch) -> None:
    class FakeReader:
        def query_cues(self, **kwargs):
            return {
                "workspace_id": "ws-1",
                "filters": [{"filter": "type", "value": "Light"}],
                "profile": "basic_safe",
                "scanned_count": 879,
                "matched_count": 391,
                "returned_count": 20,
                "total_cue_ids": 879,
                "query_completeness": "partial",
                "query_completeness_reasons": ["id_only_unscanned"],
                "id_only_unscanned_count": 545,
                "omitted_branches": [
                    {
                        "cue_ref": "C7105E58-F911-4A2E-9BD9-40CEDDC79AE1",
                        "number": "TEKNO",
                        "child_count": 545,
                        "fallback_used": True,
                    }
                ],
                "partial_branches": [
                    {
                        "cue_ref": "C7105E58-F911-4A2E-9BD9-40CEDDC79AE1",
                        "number": "TEKNO",
                        "child_count": 545,
                        "fallback_used": True,
                    }
                ],
                "truncated": True,
                "truncation_reasons": ["child_metadata_unavailable"],
                "scanned_all_cues": False,
                "result_limited": False,
                "limits": {"max_results": 20, "max_cues_scanned": 5000},
                "cues": [],
                "warnings": ["Query scanned only cues with metadata available."],
                "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())

    result = qlab_query_cues("ws-1", "type", "Light", max_cues_scanned=5000, max_results=20)
    payload = result.model_dump()

    assert payload["query_completeness"] == "partial"
    assert payload["query_completeness_reasons"] == ["id_only_unscanned"]
    assert payload["id_only_unscanned_count"] == 545
    assert payload["omitted_branches"][0]["number"] == "TEKNO"
    assert payload["partial_branches"][0]["child_count"] == 545
    assert "metadata available" in payload["warnings"][0]


def test_move_delete_capture_records_full_mcp_envelopes_and_redacts_secrets(monkeypatch):
    import runpy

    capture = runpy.run_path(str(PROJECT_ROOT / "scripts" / "capture_move_delete.py"))
    root_id = "22222222-2222-4222-8222-222222222222"
    secret = "confirm:deleteCues:v1:private:signature"

    class FakeReader:
        def delete_cues(self, **kwargs):
            assert kwargs["delete_container"] is True
            assert kwargs["cue_ids"] is None
            assert kwargs["recursive"] is True
            return dict(ok=False, status="partial_failed", workspace_id=kwargs["workspace_id"],
                dry_run=False, requested_count=1, planned_count=2, deleted_count=1, failed_count=1,
                results=[{"cue_id": root_id, "status": "partial_failed"}],
                pending_cue_ids=[root_id], uncertain_cue_ids=[], delete_container=True,
                container_id=root_id, recursive=True, preserved_container_id=None,
                message="synthetic failure", confirm_token=secret,
                errors={"test": f"synthetic error {secret}"})

    monkeypatch.setattr(server_module, "_reader", lambda: FakeReader())
    request = {"tool": "qlab_delete_cues", "arguments": {
        "workspace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "container_id": root_id,
        "recursive": True, "delete_container": True, "dry_run": False, "confirm_token": secret}}

    async def calls():
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert len(tools) == 79
            assert tools["qlab_delete_cues"].inputSchema["properties"]["delete_container"]["default"] is False
            for name in ("qlab_move_cues", "qlab_delete_cues"):
                assert {"pending_cue_ids", "uncertain_cue_ids"} <= tools[name].outputSchema["properties"].keys()
            result = await capture["capture_call"](client, request)
            request["arguments"]["container_id"] = "invalid uuid"
            error = await capture["capture_call"](client, request)
        return result, error

    result, error = asyncio.run(calls())
    envelope = result["response"]
    assert envelope["isError"] is False  # application partial failure is structured
    assert envelope["content"] and envelope["structuredContent"]["pending_cue_ids"] == [root_id]
    assert envelope["structuredContent"]["delete_container"] is True
    assert envelope["structuredContent"]["preserved_container_id"] is None
    assert error["response"]["isError"] is True
    assert error["response"]["content"]
    assert secret not in json.dumps([result, error])
    assert "[redacted]" in json.dumps(result)
    assert capture["redact"]({"passcode": "secret", "notes": "private", "fileTarget": "/private/media"}) == {
        "passcode": "[redacted]", "notes": "[redacted]", "fileTarget": "[redacted]"}


def test_move_delete_capture_preserves_transport_exception():
    import runpy
    capture = runpy.run_path(str(PROJECT_ROOT / "scripts" / "capture_move_delete.py"))

    class BrokenClient:
        async def call_tool_mcp(self, *a):
            raise OscTimeoutError("synthetic transport timeout")

    result = asyncio.run(capture["capture_call"](BrokenClient(), {"tool": "qlab_move_cues", "arguments": {}}))
    assert result["response"]["exception_type"] == "OscTimeoutError"
    assert result["response"]["error"] == "synthetic transport timeout"

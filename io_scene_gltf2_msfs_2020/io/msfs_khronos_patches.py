# Copyright 2026 FlightSimStudio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Behaviour changes to the bundled Khronos glTF exporter that the FSS production pipeline relies on.

The production Blender 3.6 install (tools/blender) shipped an edited copy of Khronos io_scene_gltf2.
Bundled add-ons cannot be edited on Blender 4.2+, so the same behaviour is applied here at runtime,
only while the MSFS extension is enabled.
"""

import importlib

import bpy

# Khronos module holding PrimitiveCreator, newest layout first
_PRIMITIVE_EXTRACT_MODULES = (
    "io_scene_gltf2.blender.exp.primitive_extract",                    # Blender 4.5+
    "io_scene_gltf2.blender.exp.gltf2_blender_gather_primitives_extract",  # Blender 3.6 .. 4.4
)

_patched = None  # (PrimitiveCreator class, original __get_bone_data)


def _msfs_extension_enabled() -> bool:
    settings = getattr(bpy.context.scene, "msfs_exporter_settings", None)
    return bool(settings and settings.enable_msfs_extension)


def _find_primitive_creator():
    for name in _PRIMITIVE_EXTRACT_MODULES:
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue
        creator = getattr(module, "PrimitiveCreator", None)
        if creator is not None and hasattr(creator, "_PrimitiveCreator__get_bone_data"):
            return creator
    return None


def register():
    """
    No neutral bone for skinned vertices without bone weights.

    Khronos binds vertices that have no bone influence to an extra "neutral bone" joint it appends
    to the skin. The FSS production exporter disabled that ("compatibility fix for msfs" in
    gltf2_blender_gather_primitives_extract.py), so it is reproduced here to keep the exported
    models identical.
    """
    global _patched
    if _patched is not None:
        return
    creator = _find_primitive_creator()
    if creator is None:
        print("[MSFS2020] Khronos PrimitiveCreator not found, neutral bone patch not applied")
        return

    original = creator._PrimitiveCreator__get_bone_data

    def get_bone_data(self):
        original(self)
        if _msfs_extension_enabled():
            self.need_neutral_bone = False

    creator._PrimitiveCreator__get_bone_data = get_bone_data
    _patched = (creator, original)


def unregister():
    global _patched
    if _patched is None:
        return
    creator, original = _patched
    creator._PrimitiveCreator__get_bone_data = original
    _patched = None

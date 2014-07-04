# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import shutil
import os
import shutil

def copy_if_newer(src, dst):
    pass

def run(action, asset_dir, out_dir):
    input_files = []
    if 'input' in action:
        for f in action['input']:
            # The input file needs to be relative to the asset_dir.
            input_files.append(os.path.relpath(os.path.join(asset_dir, f),
                                               asset_dir))
    else:
        for dirname, dirs, files in os.walk(asset_dir):
            for f in files:
                full_filename = os.path.join(dirname, f)
                input_files.append(os.path.relpath(full_filename, asset_dir))

    for f in input_files:
        os.makedirs(os.path.normpath(os.path.join(out_dir,
                                                  os.path.dirname(f))),
                    exist_ok=True)
        shutil.copy2(os.path.join(asset_dir, f), os.path.join(out_dir, f))

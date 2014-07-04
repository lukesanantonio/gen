# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import os
import json
import imp

def find_asset_files(asset_dir, asset_filename = "asset.json"):
    """Return a list of relative paths to all asset json files.

    Keyword Arguments:
    asset_dir -- root directory to be searched.
    """

    # If we aren't even given a directory, bail.
    if not os.path.isdir(asset_dir):
        return []

    files = []

    contents = os.listdir(asset_dir);
    if asset_filename not in contents:
        for dirname in contents:
            next_dir = os.path.join(asset_dir, dirname)
            files.extend(find_asset_files(next_dir))
    else:
        # The asset.json or equivalent lives in this directory.
        # Add whatever it's called to the list.
        files.append(os.path.join(asset_dir, asset_filename))

    return files

if __name__ == '__main__':
    # Root is absolute, as are the rest.
    root = os.path.abspath(os.path.dirname(__file__))
    assets = os.path.join(root, 'assets')
    dist = os.path.join(root, 'dist')
    types = os.path.join(root, 'types')

    os.chdir(root)

    for asset_json in find_asset_files(os.path.relpath(assets)):

        # Extract the action object!
        action = json.load(open(asset_json))

        # Get the relative path to the asset folder containing the asset.json.
        this_asset = os.path.dirname(asset_json)

        # Figure out the distribution directory for this asset. The default is
        # to use the name of the folder containing the asset.json file.
        # However, if output_dir is specified in the action object, that is
        # preferred.
        this_dist = os.path.join(dist, os.path.relpath(this_asset, assets))
        if 'output_dir' in action:
            this_dist = os.path.join(dist, action['output_dir'])

        # Extract the python module to load:
        module_tuple = imp.find_module(action['type'], [types])
        action_module = imp.load_module(action['type'], module_tuple[0],
                                                        module_tuple[1],
                                                        module_tuple[2])

        action_module.run(action, this_asset, this_dist)

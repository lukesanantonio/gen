# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import os

def find_asset_files(asset_dir, asset_filename = "asset.json"):
    """Return a list of relative paths to all asset json files.

    Keyword Arguments:
    asset_dir -- A relative path to the assets directory to be searched.
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
    # Move into the directory of the script, assumed to be the root of the
    # project we are dealing with.
    root_dir = os.path.abspath(os.path.dirname(__file__))
    os.chdir(root_dir)

    for asset in find_asset_files('assets/'):
        print('Found ' + asset);

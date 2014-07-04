# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import os
import json
import imp

if __name__ == '__main__':
    # Enter the directory of this script assumed to be the project root.
    root = os.path.abspath(os.path.dirname(__file__))
    os.chdir(root)

    # Figure out some other useful paths
    dist = os.path.join(root, 'dist')

    # Parse the assets.json file.
    assets_json = json.load(open('assets.json'))

    # For each asset
    for asset in assets_json:
        # Load our extension
        try:
            module = imp.find_module(asset['type'], ['types/'])
            action = imp.load_module(asset['type'], module[0],
                                     module[1], module[2])
        except ImportError as i:
            print("Invalid or unknown type: '" + asset['type'] + "'")
            continue
        # Find the dist path
        this_dist = os.path.join(dist, asset.get('dist', asset['root']))
        # Run the action
        action.run(asset, asset['root'], this_dist)

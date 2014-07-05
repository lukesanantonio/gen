# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import os
import shutil
import json

def get_input_output_file(asset_root, dist_root, f):
    return os.path.join(asset_root, f), os.path.join(dist_root, f)

class WrongSourceType(Exception):
    pass

class Environment:
    def _notify_transform(self, input_file, output_file):
        print(os.path.relpath(input_file) + ' => ' +
              os.path.relpath(output_file))

    def _notify_skip(self, out_file):
        print('Skipping ' + os.path.relpath(out_file))

    def copy_if_newer(self, input_file, output_file):
        if (not os.path.exists(output_file) or
            os.path.getmtime(input_file) > os.path.getmtime(output_file)):
            # Make sure the destination directory exists.
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            # Copy the file
            shutil.copy(input_file, output_file)
            # Notify the environment
            self._notify_transform(input_file, output_file)
        else:
            # Notify the environment we are skipping this file.
            self._notify_skip(output_file)

class BaseContentProvider:
    def __init__(self, asset_root, dist_root, env):
        # Don't rely on the cwd directory staying as it throughout the
        # lifetime of the object. That is, make absolute paths now.
        self.asset_root = os.path.abspath(asset_root)
        self.dist_root = os.path.abspath(dist_root)
        self.env = env
        self._sources = []

    def install_content(self):
        """Install all files necessary and return a list of those files."""
        out_files = []
        for source in self._sources:
            out_files.append(self._install(source))
        return out_files

class StaticContentProvider(BaseContentProvider):
    def add_input(self, input_obj):
        # We just expect a string here.
        if not isinstance(input_obj, str):
            raise WrongSourceType

        # If we are given a directory, use all the files in that directory.
        input_abspath = os.path.join(self.asset_root, input_obj)
        if os.path.isdir(input_abspath):
            for child in os.listdir(input_abspath):
                self.add_input(os.path.join(input_abspath, child))
        # Otherwise it's just a file, easy.
        else:
            self._sources.append(os.path.normpath(input_abspath))

    def _install(self, source):
        source_rel = os.path.relpath(source, self.asset_root)
        input_file, output_file = get_input_output_file(self.asset_root,
                                                        self.dist_root,
                                                        source_rel)
        self.env.copy_if_newer(input_file, output_file)
        return output_file

if __name__ == '__main__':
    # Enter the directory of this script assumed to be the project root.
    root = os.path.abspath(os.path.dirname(__file__))
    os.chdir(root)

    # Figure out some other useful paths
    dist_root = os.path.join(root, 'dist')

    builtins = {'static': StaticContentProvider}

    # Parse the assets.json file.
    assets_json = json.load(open('assets.json'))

    output = []
    for asset in assets_json:
        # Find the asset-specific dist path.
        asset_dist = os.path.join(dist_root, asset.get('dist', asset['root']))

        # Check our built-in list of supported types.
        if asset['type'] in builtins.keys():
            env = Environment()
            provider = builtins[asset['type']](asset['root'], asset_dist, env)
        else:
            print('No plugin available to handle ' + asset['type'] +
                  ' assets.')
            continue

        # Tell the provider about it's input.
        for i in asset['input']:
            provider.add_input(i)
        # Install everything.
        output.extend(provider.install_content())

    # TODO Remove all files not required to be there.

# Gen v0.1
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import os
import shutil
import json
import subprocess
import jinja2
import sys
import imp
import argparse

def get_input_output_file(asset_root, dist_root, f):
    return os.path.join(asset_root, f), os.path.join(dist_root, f)

# Exceptions
class AssetRootNotFound(Exception):
    pass
class WrongSourceType(Exception):
    pass

class Environment:
    def __init__(self, root, dist_root):
        """Initialize the root and the dist root with given values."""
        self.root = os.path.abspath(root)
        self.dist_root = os.path.abspath(dist_root)

    def _notify_transform(self, input_file, output_file):
        print(os.path.relpath(input_file) + ' => ' +
              os.path.relpath(output_file))

    def _notify_skip(self, out_file):
        print('Skipping ' + os.path.relpath(out_file))

    def _notify_command(self, args):
        sys.stdout.write('Running:')
        for part in args:
            sys.stdout.write(' ' + part)
        sys.stdout.write('\n')

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

    def file_from_content(self, input_file, content, output_file):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            f.write(content)
        self._notify_transform(input_file, output_file)

    def subprocess_transform(self, prg, options, input_file, output_file):
        args = [prg, input_file, output_file]
        args[1:1] = options

        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        self._notify_command(args)
        if subprocess.call(args):
            self._notify_transform(input_file, output_file)

class BaseContentProvider:
    def __init__(self, asset_root, dist_root, type_options, env):
        # Don't rely on the cwd directory staying as it throughout the
        # lifetime of the object. That is, make absolute paths now.
        self.asset_root = os.path.abspath(asset_root)
        if not os.path.exists(self.asset_root):
            raise AssetRootNotFound
        self.dist_root = os.path.abspath(dist_root)
        self.options = type_options
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

class Jinja2ContentProvider(BaseContentProvider):
    def __init__(self, asset_root, dist_root, type_options, env):
        BaseContentProvider.__init__(self, asset_root, dist_root,
                                     type_options, env)
        self._jinja2env = (
               jinja2.Environment(loader=jinja2.FileSystemLoader(asset_root)))

    def add_input(self, input_obj):
        # Here we expect an object with a filename and parameters.
        if not isinstance(input_obj, dict):
            raise WrongSourceType

        # Do some basic validation, then just add it to our list. As long as
        # we should be fine.
        if 'filename' in input_obj:
            self._sources.append(input_obj)
        else:
            raise WrongSourceType("Filename required in source object!")

    def _install(self, source):
        # Remember, our filename is relative to the asset root.
        filename = source['filename']
        template = self._jinja2env.get_template(filename)

        parameters = source.get('parameters')
        if 'parameters' in source:
            rendered_template = template.render(source['parameters'])
        else:
            rendered_template = template.render()

        input_file, output_file = get_input_output_file(self.asset_root,
                                                        self.dist_root,
                                                        filename)
        self.env.file_from_content(input_file, rendered_template, output_file)
        return output_file

class ScssContentProvider(StaticContentProvider):
    def _install(self, source):
        source_rel = os.path.relpath(source, self.asset_root)
        input_file, output_file = get_input_output_file(self.asset_root,
                                                        self.dist_root,
                                                        source_rel)
        output_file = os.path.splitext(output_file)[0] + '.css'

        # Check for search paths provided.
        search_paths = self.options.get('search_paths', [])
        command_options = []
        for path in search_paths:
            command_options.extend(['--load-path',
                                    os.path.join(self.env.dist_root, path)])

        self.env.subprocess_transform('scss', command_options,
                                      input_file, output_file)
        return output_file

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--assets-file', default=None,
                        help="Specify the assets json file " +
                             "(default ./assets.json).")
    arguments = parser.parse_args()

    # Parse the assets.json file.
    try:
        assets_json = json.load(open(arguments.assets_file or 'assets.json'))
    except OSError:
        sys.exit('Failed to open the assets.json file!\n' +
                 'Make sure you are running gen from the correct ' +
                 'directory.')

    env = Environment(os.getcwd(),
                      os.path.abspath(assets_json.get('dist', 'dist/')))

    transformations = {'static': StaticContentProvider,
                       'jinja2': Jinja2ContentProvider,
                       'scss'  : ScssContentProvider}

    # This way, plugins can import gen.py!
    sys.path.insert(0, os.path.abspath(__file__))

    # Add user-defined plugin objects.
    for plugin_object in assets_json.get('plugins', []):
        plugin_name = os.path.splitext(plugin_object['file'])[0]
        plugin_path, plugin_name = os.path.split(plugin_name)

        module_descriptor = imp.find_module(plugin_name, [plugin_path])
        module = imp.load_module(os.path.splitext(plugin_object['file'])[0],
                                 module_descriptor[0],
                                 module_descriptor[1],
                                 module_descriptor[2])

        transformations[plugin_object['type']] = (
                                      getattr(module, plugin_object['class']))

    output = []
    for asset in assets_json.get('assets', []):
        # Find the asset-specific dist dir.
        asset_dist = os.path.join(env.dist_root,
                                  asset.get('dist', asset['root']))

        # Find our class!
        provider_class = transformations.get(asset['type'])
        if provider_class:
            try:
                provider = provider_class(asset['root'], asset_dist,
                                          asset.get('type_options', {}), env)
            except AssetRootNotFound:
                sys.stderr.write("Asset root '" + asset['root']  +
                                 "' not found.\n")
                continue
        else:
            sys.stderr.write('No plugin available to handle ' +
                             asset['type'] + ' assets.\n')
            continue

        # Tell the provider about it's input.
        for i in asset['input']:
            provider.add_input(i)
        # Install everything while recording what files were produced.
        output.extend(provider.install_content())

    for dirname, dirs, files in os.walk(env.dist_root, topdown=False):
        for f in files:
            # Check if the file should be there.
            f = os.path.join(dirname, f)
            if f not in output:
                print('Removing old file: ' + os.path.relpath(f))
                os.remove(os.path.join(env.dist_root, f))

        # Also remove empty children directories.
        for d in dirs:
            d = os.path.join(dirname, d)
            if len(os.listdir(d)) == 0:
                print('Removing empty directory: ' + os.path.relpath(d))
                os.rmdir(d)

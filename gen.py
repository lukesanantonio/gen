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
import logging

# Helper functions
def in_out_file(asset_root, dist_root, f):
    return os.path.join(asset_root, f), os.path.join(dist_root, f)
def is_newer(i_file, o_file):
    if (not os.path.exists(o_file) or
        os.path.getmtime(i_file) > os.path.getmtime(o_file)):
        return True
    return False

def find_asset_object(assets, directory):
    directory = os.path.normpath(directory)
    # Go as long as we don't repeat ourselves.
    while directory != os.path.dirname(directory):
        for cur_asset in assets:
            if cur_asset['root'] == directory:
                return cur_asset
        # Remove the last component of the directory, effectively pointing to
        # it's parent.
        directory = os.path.dirname(directory)
    return None

# Exceptions
class AssetRootNotFound(Exception):
    pass
class WrongInputType(Exception):
    pass

class Environment:
    def __init__(self, root, dist_root):
        """Initialize the root and the dist root with given values."""
        self.root = os.path.abspath(root)
        self.dist_root = os.path.abspath(dist_root)

class Output:
    def __init__(self, logger=None):
        self.log = logger or logging.getLogger(__name__)
        self.log.addHandler(logging.StreamHandler(sys.stdout))
        self.log.setLevel(logging.WARNING)

    def on_transform(self, in_file, out_file):
        self.log.info(os.path.relpath(in_file) + ' => ' +
                      os.path.relpath(out_file))

    def on_skip(self, out_file):
        self.log.debug('Skipping ' + os.path.relpath(out_file))

    def on_command(self, args):
        self.log.info('Running: ' + ' '.join(args))

    def on_error(self, msg):
        self.log.error(msg)

    def on_remove(self, filename, **kwargs):
        adj = kwargs.get('adj', '') + ' '
        filetype = kwargs.get('filetype') or 'file'
        self.log.info("Removing " + adj + filetype + ': ' + filename)

class Operations:
    def __init__(self, out=None):
        self.out = out or Output()

    def copy(self, input_file, output_file):
        if is_newer(input_file, output_file):
            # Make sure the destination directory exists.
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            # Copy the file
            shutil.copy(input_file, output_file)
            shutil.copystat(input_file, output_file)
            # Notify the environment
            self.out.on_transform(input_file, output_file)
        else:
            # Notify the environment we are skipping this file.
            self.out.on_skip(output_file)

    def file_from_content(self, input_file, content, output_file):
        if is_newer(input_file, output_file):
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "w") as f:
                f.write(content)
            shutil.copystat(input_file, output_file)
            self.out.on_transform(input_file, output_file)
        else:
            self.out.on_skip(output_file)

    def subprocess_transform(self, prg, options, input_file, output_file):
        if is_newer(input_file, output_file):
            args = [prg, input_file, output_file]
            args[1:1] = options

            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            self.out.on_command(args)
            if subprocess.call(args):
                self.out.on_transform(input_file, output_file)
                shutil.copystat(input_file, output_file)
        else:
            self.out.on_skip(output_file)

class BaseContentProvider:
    def __init__(self, asset_root, dist_root, type_options, env, ops=None):
        if not os.path.exists(asset_root):
            raise AssetRootNotFound
        # Don't rely on the cwd directory staying as it throughout the
        # lifetime of the object. That is, make absolute paths now.
        self.asset_root = os.path.abspath(asset_root)
        self.dist_root = os.path.abspath(dist_root)
        self.options = type_options
        self.env = env
        self.operations = ops or Operations()
        def list_compiled_files(self, input_obj):
            """Return a list of files that would be installed.

            The files returned will be relative to the distribution root.
            """
            raise NotImplementedError

        def install_input(self, input_obj):
            raise NotImplementedError


class StaticContentProvider(BaseContentProvider):
    def _get_source_list(self, input_obj):
        # We just expect a string here.
        if not isinstance(input_obj, str):
            raise WrongInputType('A static input object must be a string')

        # If we are given a directory, use all the files in that directory.
        input_abspath = os.path.join(self.asset_root, input_obj)
        if os.path.isdir(input_abspath):
            files = []
            for child in os.listdir(input_abspath):
                child = os.path.join(input_abspath, child)
                files.extend(self._get_source_list(child))
            return files
        # Otherwise it's just a file, easy.
        else:
            return [os.path.normpath(input_abspath)]

    def list_compiled_files(self, input_obj):
        source_list = _get_source_list(input_obj)
        compiled_list = []
        for source in source_list:
            compiled_list.append(os.path.relpath(source, self.asset_root))
        return compiled_list

    def install_input(self, input_obj):
        source_list = self._get_source_list(input_obj)
        installed_files = []
        for source in source_list:
            source_rel = os.path.relpath(source, self.asset_root)
            in_f, out_f = in_out_file(self.asset_root, self.dist_root,
                                     source_rel)
            self.operations.copy(in_f, out_f)
            installed_files.append(os.path.join(self.dist_root, out_f))
        return installed_files

class Jinja2ContentProvider(BaseContentProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        loader = jinja2.FileSystemLoader(self.asset_root)
        self.__jinja2env = jinja2.Environment(loader=loader)

    def __validate_input(self, input_obj):
        # Here we expect an object with a filename and parameters.
        if not isinstance(input_obj, dict):
            raise WrongInputType('A Jinja2 input object must be a dict!')

        # As long as we have a filename we should be fine.
        if 'filename' not in input_obj:
            raise WrongInputType('A filename is required in Jinja2 input ' +
                                 'objects!')

    def list_compiled_files(self, input_obj):
        self.__validate_input(input_obj)
        return input_obj['filename']

    def install_input(self, input_obj):
        self.__validate_input(input_obj)

        # Remember, our filename is relative to the asset root.
        filename = input_obj['filename']
        template = self.__jinja2env.get_template(filename)

        if 'parameters' in input_obj:
            rendered_template = template.render(input_obj['parameters'])
        else:
            rendered_template = template.render()

        in_f, out_f = in_out_file(self.asset_root, self.dist_root,
                                  filename)
        self.operations.file_from_content(in_f, rendered_template, out_f)
        return [out_f]

class ScssContentProvider(StaticContentProvider):
    def list_compiled_files(self, input_obj):
        source_list = self._get_source_list(input_obj)
        compiled_list = []
        for source in source_list:
            source = os.path.splitext(source)[0] + '.css'
            compiled_list.append(os.path.relpath(source, self.asset_root))
        return compiled_list

    def install_input(self, input_obj):
        source_list = self._get_source_list(input_obj)
        installed_files = []
        for source in source_list:
            source_rel = os.path.relpath(source, self.asset_root)
            in_f, out_f = in_out_file(self.asset_root, self.dist_root,
                                      source_rel)
            out_f = os.path.splitext(out_f)[0] + '.css'

            # Check for search paths provided.
            search_paths = self.options.get('search_paths', [])
            command_options = []
            for path in search_paths:
                command_options.extend(['--load-path',
                                        os.path.join(self.env.dist_root,path)])

            self.operations.subprocess_transform('scss', command_options,
                                                 in_f, out_f)
            installed_files.append(os.path.join(self.dist_root, out_f))
        return installed_files

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--assets-file', default=None,
                        help="Specify the assets json file " +
                             "(default ./assets.json).")
    parser.add_argument('-v', '--verbose', action="count",
                        help="Log files copied to stderr.")
    arguments = parser.parse_args()

    out = Output()
    if arguments.verbose == 1:
        out.log.setLevel(logging.INFO)
    elif arguments.verbose > 1:
        out.log.setLevel(logging.DEBUG)

    # Parse the assets.json file.
    try:
        assets_json_filename = arguments.assets_file or 'assets.json'
        assets_json = json.load(open(assets_json_filename))
    except OSError:
        out.on_error("Failed to open '" + assets_json_filename + "'!")
        sys.exit(1)

    env = Environment(os.getcwd(),
                      os.path.abspath(assets_json.get('dist', 'dist/')))

    transformations = {'static': StaticContentProvider,
                       'jinja2': Jinja2ContentProvider,
                       'scss'  : ScssContentProvider}

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
                                          asset.get('type_options', {}), env,
                                          Operations(out))
            except AssetRootNotFound:
                out.on_error("Invalid asset root: '" + asset['root'] +
                             "' - Skipping")
                continue
        else:
            out.on_error("No plugin available to handle '" +
                         asset['type'] + "' assets.")
            continue

        # Tell the provider to install each input.
        for i in asset['input']:
            output.extend(provider.install_input(i))

    for dirname, dirs, files in os.walk(env.dist_root, topdown=False):
        for f in files:
            # Check if the file should be there.
            f = os.path.join(dirname, f)
            if f not in output:
                out.on_remove(os.path.relpath(f), adj='old')
                os.remove(os.path.join(env.dist_root, f))

        # Also remove empty children directories.
        for d in dirs:
            d = os.path.join(dirname, d)
            if len(os.listdir(d)) == 0:
                out.on_remove(os.path.relpath(f), adj='empty',
                              filetype='directory')
                os.rmdir(d)

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

class ValidationError(Exception):
    def __init__(self, msg, obj):
        super().__init__(msg)
        self.obj = obj
class InputTypeError(ValidationError):
    def __init__(self, obj, expected_type):
        super().__init__("Input object '{0}' must be type: '{1}'"
                         .format(repr(obj), str(expected_type)), obj)
        self.expected_type = expected_type
class InputAttributeError(ValidationError):
    def __init__(self, obj, attr):
        super().__init__("Input object '{0}' must have attribute: '{1}'"
                         .format(repr(obj), str(attr)), obj)
        self.attr = attr
class SourceNotFoundError(ValidationError):
    def __init__(self, obj, fname):
        super().__init__("Source file '{0}' doesn't exist.".format(fname), obj)
        self.fname = fname

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

class BaseAsset:
    def __init__(self, root, dist, inputs, ops, options, env):
        self.root = os.path.abspath(root)
        self.dist = os.path.abspath(dist)

        # Validate each input.
        for i in range(len(inputs)):
            try:
                self.validate(inputs[i])
            except ValidationError as e:
                # Rethrow with a modified message.
                tb = sys.exc_info()[2]
                e.args[0] = 'input[{0}]: '.format(i) + e.args[0]
                raise e.with_traceback(tb)
            except NotImplementedError:
                # If validation isn't implemented that doesn't really matter.
                # Just bail.
                break
        # If there was validation, it passed.
        self.inputs = inputs

        self.operations = ops
        self.options = options
        self.env = env

    def list_output(self):
        raise NotImplementedError
    def install(self, filename):
        raise NotImplementedError
    def validate(self, input_obj):
        raise NotImplementedError

    def install_all(self):
        """Install all files and return what files were installed."""
        to_install = self.list_output()
        for f in to_install:
            self.install(f)
        return to_install

class StaticAsset(BaseAsset):
    def validate(self, fname):
        # Make sure it's a string.
        if not isinstance(fname, str):
            raise InputTypeError(fname, str)
        # Make sure the file exists!
        if not os.path.exists(os.path.join(self.root, fname)):
            raise SourceNotFoundError(fname, fname)

    def _get_source_list(self, input_obj):
        # If we are given a directory, use all the files in that directory.
        abs_input = os.path.join(self.root, input_obj)
        if os.path.isdir(abs_input):
            files = []
            for child in os.listdir(abs_input):
                child = os.path.join(abs_input, child)
                files.extend(self._get_source_list(os.path.normpath(child)))
            return files
        # Otherwise it's just a file, easy.
        else:
            return [os.path.relpath(abs_input, self.root)]

    def list_output(self):
        files = []
        for i in self.inputs:
            files.extend(self._get_source_list(i))
        return files

    def install(self, filename):
        in_f, out_f = in_out_file(self.root, self.dist, filename)
        self.operations.copy(in_f, out_f)

class Jinja2Asset(BaseAsset):
    def validate(self, input_obj):
        # Here we expect an object with a filename and parameters.
        if not isinstance(input_obj, dict):
            raise InputTypeError(input_obj, dict)

        # Make sure we have a filename and that it exists.
        f = input_obj.get('filename', None)
        if f is None:
            raise InputAttributeError(input_obj, 'filename')
        if not os.path.exists(os.path.join(self.root, f)):
            raise SourceNotFoundError(input_obj, f)

    def list_output(self):
        output = []
        for i in self.inputs:
            output.append(i['filename'])
        return output

    def install(self, filename):
        # Set up our Jinja2 environment.
        loader = jinja2.FileSystemLoader(self.root)
        self.__jinja2env = jinja2.Environment(loader=loader)

        # Find the asset object based off it's filename.
        # TODO Make this process automatic in the base class.
        input_obj = None
        for i in self.inputs:
            if i['filename'] == filename:
                input_obj = i
                break
        if input_obj is None:
            raise ValueError("Cannot find input object with filename: '{0}'"
                             .format(filename))

        # The filename is relative to the asset root, but that is where Jinja2
        # looks, so it works out.
        template = self.__jinja2env.get_template(filename)

        if 'parameters' in input_obj:
            rendered_template = template.render(input_obj['parameters'])
        else:
            rendered_template = template.render()

        in_f, out_f = in_out_file(self.root, self.dist, filename)
        self.operations.file_from_content(in_f, rendered_template, out_f)

class ScssAsset(StaticAsset):
    def list_output(self):
        output = super().list_output()
        for i in range(len(output)):
            output[i] = os.path.splitext(output[i])[0] + '.css'
        return output

    def install(self, filename):
        in_f = os.path.join(self.root, os.path.splitext(filename)[0] + '.scss')
        out_f = os.path.join(self.dist, filename)

        # Check for search paths provided.
        search_paths = self.options.get('search_paths', [])
        command_options = []
        for path in search_paths:
            command_options.extend(['--load-path',
                                    os.path.join(self.env.dist_root, path)])

        self.operations.subprocess_transform('scss', command_options,
                                             in_f, out_f)
if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--assets-file', default=None,
                        help="Specify the assets json file " +
                             "(default ./assets.json).")
    parser.add_argument('-v', '--verbose', action="count", default=0,
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

    transformations = {'static': StaticAsset, 'jinja2': Jinja2Asset,
                       'scss': ScssAsset}

    output = []
    for asset in assets_json.get('assets', []):
        # Find the asset-specific dist dir.
        asset_dist = os.path.join(env.dist_root,
                                  asset.get('dist', asset['root']))
        asset_dist = os.path.normpath(asset_dist)

        # Find our class!
        provider_class = transformations.get(asset['type'])
        if provider_class:
            try:
                provider = provider_class(asset['root'], asset_dist,
                                          asset['input'], Operations(out),
                                          asset.get('type_options', {}), env)
            except ValidationError as e:
                out.on_error(e)
                continue;
        else:
            out.on_error("No plugin available to handle '" +
                         asset['type'] + "' assets.")
            continue

        for f in provider.install_all():
            output.append(os.path.join(asset_dist, f))

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

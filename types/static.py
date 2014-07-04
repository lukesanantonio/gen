# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

from gen import recursive_contents, recursive_directories

import shutil
import os
import shutil

def get_input_output_file(asset_root, dist_root, f):
    return os.path.join(asset_root, f), os.path.join(dist_root, f)

def get_input_files(action, asset_root):
    """Return a list of files to be preprocessed using an action object.

    The files in the list are relative the asset_root.
    """
    input_files = []
    try:
        # Try to use a provided list of files.
        input_files.extend(action['input'])
    except KeyError:
        # Otherwise walk the tree and build it ourself.
        for dirname, dirs, files in os.walk(asset_root):
            for filename in files:
                filename = os.path.join(dirname, filename)
                input_files.append(os.path.relpath(filename, asset_root))
    return input_files



def run(action, asset_root, dist_root):
    asset_root = os.path.relpath(asset_root)
    dist_root = os.path.relpath(dist_root)

    input_files = get_input_files(action, asset_root)

    for filename in recursive_contents(dist_root):
        if filename not in input_files:
            # Make the filename relative to the current directory.
            filename = os.path.join(dist_root, filename)
            print('Removing file: ' + filename)
            os.remove(filename)

    # Now our dist folder should only hold files that could still be relevant.
    # In other words we should only copy over if the new files are newer than
    # the old files. Otherwise nothing really has to change!
    for f in input_files:
        input_file, output_file = get_input_output_file(asset_root,
                                                        dist_root, f)
        # Only if the input is newer than the output
        if (not os.path.exists(output_file) or
            os.path.getmtime(input_file) > os.path.getmtime(output_file)):
            # Make the required directory, if necessary.
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Print a prompt then actually do the copy.
            print(input_file + ' => ' + output_file)
            shutil.copy2(input_file, output_file)
        else:
            print('Skipping: ' + output_file)


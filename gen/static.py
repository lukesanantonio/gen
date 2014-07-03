# Gen v0
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

import shutil

def run(action, in_dir, out_dir):
    # Literally just copy the folder 1:1. This could be much more efficient
    # and only copy files that are newer than their corresponding out file but
    # for now this should work fine.
    print('Copying: ' + in_dir + ' => ' + out_dir)
    shutil.copytree(in_dir, out_dir)

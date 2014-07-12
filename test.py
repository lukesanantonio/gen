# Gen v0.1
# A generic, JSON-based asset pipeline for heterogeneous setups and
# unusual configurations.
#
# This is free and unencumbered software released into the public domain.
# For more information, please refer to <http://unlicense.org/>

from gen import find_asset_object
import json
import unittest

class AssetDiscoveryTest(unittest.TestCase):
    def test_discovery(self):
        assets = json.loads("""\
        [
            { "root":"top" }, { "root":"top/middle" },
            { "root":"top/middle/bottom" }
        ]""")
        self.assertTrue(
                   find_asset_object(assets, 'top/middle/other') is assets[1])
        self.assertTrue(
                  find_asset_object(assets, 'top/middle/other/') is assets[1])
        self.assertTrue(
                   find_asset_object(assets, 'top/other/other/') is assets[0])
        self.assertTrue(
                 find_asset_object(assets, 'top/middle/bottom/') is assets[2])
        self.assertTrue(
               find_asset_object(assets, '/top/middle/bottom/') not in assets)

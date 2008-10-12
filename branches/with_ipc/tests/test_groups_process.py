# test_groups_process.py
from pysage.network import *
import unittest

nmanager = NetworkManager.get_singleton()

class TestGroupsProcess(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_setgroups(self):
        nmanager.add_process_group('resource_loading')
        nmanager.shutdown_children()
        nmanager.reset()
    def test_shutdown(self):
        pass



# test_groups_process.py
from pysage.network import *
import multiprocessing
import unittest

nmanager = NetworkManager.get_singleton()

class TestMessage(Packet):
    properties = ['amount']
    types = ['i']
    packet_type = 101

class TestGroupsProcess(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        nmanager.clear_process_group()
        nmanager.reset()
    def test_add_group_single(self):
        nmanager.add_process_group('resource_loading')
        assert len(nmanager.groups) == 1
        assert len(multiprocessing.active_children()) == 1
    def test_add_group_multi(self):
        nmanager.add_process_group('a')
        nmanager.add_process_group('b')
        assert len(nmanager.groups) == 2
        assert len(multiprocessing.active_children()) == 2
        nmanager.clear_process_group()
        assert len(nmanager.groups) == 0
        assert len(multiprocessing.active_children()) == 0
    def test_remove_group_individual(self):
        nmanager.add_process_group('a')
        nmanager.add_process_group('b')

        assert len(nmanager.groups) == 2
        assert len(multiprocessing.active_children()) == 2

        nmanager.remove_process_group('a')

        assert len(nmanager.groups) == 1
        assert len(multiprocessing.active_children()) == 1



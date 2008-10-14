# test_groups_process.py
from pysage.network import *

processing = None

try:
    import multiprocessing as processing
except ImportError:
    pass
else:
    active_children = processing.active_children

try:
    import processing as processing
except ImportError:
    pass
else:
    active_children = processing.activeChildren

if not processing:
    raise Exception('pysage requires either python2.6 or the "processing" module')

import unittest

nmanager = NetworkManager.get_singleton()

class PingMessage(Packet):
    properties = ['secret']
    types = ['i']
    packet_type = 101
    
class PongMessage(Packet):
    properties = ['secret']
    types = ['i']
    packet_type = 102
    
class PingReceiver(PacketReceiver):
    subscriptions = ['PingMessage']
    def handle_PingMessage(self, msg):
        pass
    
class PongReceiver(PacketReceiver):
    subscriptions = ['PongMessage']
    def handle_PongMessage(self, msg):
        pass

class TestGroupsProcess(unittest.TestCase):
    def setUp(self):
        pass
    def tearDown(self):
        nmanager.clear_process_group()
        nmanager.reset()
    def test_add_group_single(self):
        nmanager.add_process_group('resource_loading')
        assert len(nmanager.groups) == 1
        assert len(active_children()) == 1
    def test_add_group_multi(self):
        nmanager.add_process_group('a', )
        nmanager.add_process_group('b')
        assert len(nmanager.groups) == 2
        assert len(active_children()) == 2
        nmanager.clear_process_group()
        assert len(nmanager.groups) == 0
        assert len(active_children()) == 0
    def test_remove_group_individual(self):
        nmanager.add_process_group('a')
        nmanager.add_process_group('b')

        assert len(nmanager.groups) == 2
        assert len(active_children()) == 2

        nmanager.remove_process_group('a')

        assert len(nmanager.groups) == 1
        assert len(active_children()) == 1
    def test_sending_message(self):
        nmanager.add_process_group('a', PingReceiver)


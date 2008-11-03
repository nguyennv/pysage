# test_network.py
from pysage.system import Message, ActorManager, Actor
import unittest

nmanager = ActorManager.get_singleton()

class TestMessage1(Message):
    properties = ['amount']
    types = ['i']
    packet_type = 103
    
class TestMessage2(Message):
    properties = ['size']
    types = [('i', 'i')]
    packet_type = 106

class LongMessage(Message):
    properties = ['data']
    types = ['ti']
    packet_type = 107

class PascalMessage(Message):
    properties = ['data']
    types = ['p']
    packet_type = 108
    
class TestReceiver(Actor):
    pass

class TestNetwork(unittest.TestCase):
    def test_packet_creation(self):
        p = TestMessage1(amount=1)
    def test_packing(self):
        p = TestMessage1(amount=1)
        assert p.to_string() == 'g\x00\x00\x00\x01'
    def test_manager_gid(self):
        assert nmanager.gid == 0
    def test_receiver_gid(self):
        r = TestReceiver()
        assert r.gid == (nmanager.gid, id(r))
    def test_packing_tuple(self):
        m = TestMessage2(size=(1,1))
        assert len(m.to_string()) == 9
        assert m.to_string() == 'j\x00\x00\x00\x01\x00\x00\x00\x01'
        
        print TestMessage2().from_string('j\x00\x00\x00\x01\x00\x00\x00\x01').get_property('size')
        assert TestMessage2().from_string('j\x00\x00\x00\x01\x00\x00\x00\x01').get_property('size') == [1,1]
    def test_long_list(self):
        m = LongMessage(data=[1] * 10000)
        assert len(m.to_string()) == 1 + 4 + 10000 * 4
        assert len('k' + "\x00\x00'\x10" + '\x00\x00\x00\x01' * 10000) == 1 + 4 + 10000 * 4
        assert m.to_string() == 'k' + "\x00\x00'\x10" + '\x00\x00\x00\x01' * 10000
        assert LongMessage().from_string('k' + "\x00\x00'\x10" + '\x00\x00\x00\x01' * 10000).get_property('data') == [1] * 10000
    def test_long_pascal_string(self):
        m = PascalMessage(data='a' * 255)
        assert len(m.to_string()) == 257
        assert m.to_string() == 'l' + '\xff' + '\x61' * 255
        assert m.to_string() == 'l' + '\xff' + 'a' * 255
        m = PascalMessage(data='a' * 256)
        self.assertRaises(ValueError, m.to_string)
        








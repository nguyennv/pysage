'''pysage is a high-level message passing library with currency in mind.

For more information: http://code.google.com/p/pysage/

Copyright (c) 2007-2008 Shuo Yang (John) <bigjhnny@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
# network.py
import struct
import system
import messaging
import transport
import logging
import util
import time

__all__ = ('Packet', 'NetworkManager', 'PacketReceiver', 'PacketError', 'PacketTypeError', 'GroupAlreadyExists', 'GroupDoesNotExist', 'CreateGroupError')

processing = None

try:
    import processing as processing
except ImportError:
    pass

try:
    import multiprocessing as processing
except ImportError:
    pass

if not processing:
    raise Exception('pysage requires either python2.6 or the "processing" module')

class PacketError(Exception):
    pass

class PacketTypeError(Exception):
    pass

class GroupAlreadyExists(Exception):
    pass

class GroupDoesNotExist(Exception):
    pass

class CreateGroupError(Exception):
    pass

def _subprocess_main(name, default_actor_class, max_tick_time, interval, server_addr, _should_quit):
    '''interval is in milliseconds of how long to sleep before another tick'''
    # creating a client mode manager
    manager = NetworkManager.get_singleton()
    manager._ipc_connect(server_addr, _should_quit)
    if default_actor_class:
        manager.register_object(default_actor_class())
    while not manager._should_quit.value:
        start = util.get_time()
        manager.tick(maxTime=max_tick_time)
        # we want to sleep the different between the time it took to process and the interval desired
        _time_to_sleep = interval - (util.get_time() - start)
        time.sleep(_time_to_sleep)
    return False

class NetworkManager(system.ObjectManager):
    '''extends objectmanager to provide network functionality'''
    MAIN_GROUP_NAME = '__MAIN_GROUP__'
    def init(self):
        system.ObjectManager.init(self)
        # self.gid = network_id.next()
        self.gid = 0
        if transport.RAKNET_AVAILABLE:
            self.transport = transport.RakNetTransport()
        else:
            self.transport = transport.Transport()
        self.clients = {}
        self.packet_types = {}
        # using either Domain Socket (Unix) or Named Pipe (windows) as means
        # for IPC
        self.groups = {}
        self.is_main_process = None
        self.ipc_transport = transport.IPCTransport()
    def _ipc_listen(self):
        # starting server mode
        self.is_main_process = True
        self.ipc_transport.listen()
    def _ipc_connect(self, server_addr, _should_quit):
        # starting client mode
        self.is_main_process = False
        self.ipc_transport.connect(server_addr)
        self._should_quit = _should_quit
        self.groups[self.MAIN_GROUP_NAME] = (None,server_addr,None)
    def listen(self, port):
        def connection_handler(client_address):
            logging.debug('connected to client: %s' % client_address)
        self.transport.listen(port, connection_handler)
        return self
    def connect(self, host, port):
        self.transport.connect(host, port)
        return self
    def send_message(self, msg, clientid):
        self.transport.send(msg.to_string(), id=self.clients[clientid])
        return self
    def queue_message_to_group(self, msg, group):
        '''message is serialized and sent to the group (process) specified'''
        p, _clientid, switch = self.groups[group]
        self.ipc_transport.send(msg.to_string(), _clientid)
    def broadcast_message(self, msg):
        self.transport.send(msg.to_string(), broadcast=True)
        return self
    def tick(self, *args, **kws):
        '''first poll process for packets, then network messages, then object updates'''
        self.ipc_transport.poll(self.packet_handler)
        self.transport.poll(self.packet_handler)
        return system.ObjectManager.tick(self, *args, **kws)
    def packet_handler(self, packet):
        packetid = ord(packet.data[0])
        logging.debug('Received packet of type "%s"' % type)
        if packetid < 100:
            logging.warning('internal packet unhandled: "%s"' % self.transport.packet_type_info(packetid))
            return self
        p = self.packet_types[packetid]().from_string(packet.data)
        self.queue_message(self.packet_types[packetid]().from_string(packet.data)) 
        return self
    def register_packet_type(self, packet_class):
        # skip the base packet class
        if packet_class.__name__ == 'Packet':
            return
        if packet_class.packet_type <= 100:
            raise PacketTypeError('Packet_type must be greater than 100.  Had "%s"' % packet_class.packet_type)
        self.packet_types[packet_class.packet_type] = packet_class
    def add_process_group(self, name, default_actor_class=None, max_tick_time=None, interval=.03):
        '''adds a process group to the pool'''
        if self.is_main_process == None:
            self._ipc_listen()
        # make sure we have a str
        g = str(name)
        if self.groups.has_key(g):
            raise GroupAlreadyExists('Group name "%s" already exists.' % g) 
        server_addr = self.ipc_transport.address
        # shared should quit switch
        switch = processing.Value('B', 0)
        actor_class = default_actor_class or DefaultActor
        p = processing.Process(target=_subprocess_main, args=(name, actor_class, max_tick_time, interval, server_addr, switch))
        p.start()
        _clientid = self.ipc_transport.accept()
        self.groups[g] = (p, _clientid, switch)
    def remove_process_group(self, name):
        '''removes a process group from the pool'''
        p, _clientid, switch = self.groups[name]
        switch.value = 1
        p.join()
        del self.groups[name]
        return self
    def clear_process_group(self):
        '''shuts down all children processes'''
        if self.is_main_process:
            # if we are the server manager, take care to shut down all children
            for name in self.groups.keys():
                self.remove_process_group(name)
                
class AutoPacketRegister(type):
    def __init__(cls, name, bases, dct):
        super(AutoPacketRegister, cls).__init__(name, bases, dct)
        NetworkManager.get_singleton().register_packet_type(cls)
        
class PacketReceiver(system.MessageReceiver):
    @property
    def gid(self):
        '''return a globally unique id that is good cross processes'''
        return (NetworkManager.get_singleton().gid, id(self))
    
class DefaultActor(PacketReceiver):
    subscriptions = [messaging.WildCardMessageType]
    def handle_message(self, msg):
        processing.get_logger().info('Default actor received message "%s"' % msg)
        return False

class Packet(system.Message):
    '''a packet is a network message'''
    __metaclass__ = AutoPacketRegister
    types = []
    packet_type = None
    def to_string(self):
        '''packs message into binary stream'''
        # first encode the message type identifier
        buf = struct.pack('!B', self.packet_type)
        # iterate thru all attributes
        for i,_type in enumerate(self.types):
            # get name and value of the attribute
            name = self.properties[i]
            value = self.get_property(name)
            # for composite type, pack it looping over each subtype
            if type(_type) == type(()):
                for j,v in enumerate(getattr(self, 'pack_' + name)(value)):
                    buf = self.pack_attr(_type[j], buf, v, name)
            # for mono types, just pack it
            else:
                buf = self.pack_attr(_type, buf, value, name)
        return buf
    def from_string(self, data):
        '''unpacks the property data into the object, from binary stream'''
        pos = 1
        # iterate over all types we need to unpack
        for i, _type in enumerate(self.types):
            # get the name of the property we are currently unpacking
            name = self.properties[i]
            # if type of this value is a composite one, unpack subtypes individually
            # then pass all of them together to unpack the higher level property
            if type(_type) == type(()):
                values = []
                # after packing children, pass children to parent to process
                for subtype in _type:
                    value, size = self.unpack_attr(subtype, data, pos)
                    values.append(value)
                    pos += size
                self.set_property(name, getattr(self, 'unpack_' + name)(values))
            # if not composite, just unpack them and set the property
            else:
                value, size = self.unpack_attr(_type, data, pos)
                pos += size
                self.set_property(name, value)
        if pos != len(data):
            raise PacketError('incorrect length upon unpacking %s: got %i expected %i' % (self.__class__.__name__, len(data), pos))
        return self
    def pack_attr(self, _type, buf, value, name):
        '''pack a single attribute into the running buffer'''
        # custom types
        # p: pascal string, a short variable length string
        # packed like this:
        # [unsigned char: length of string][string itself]
        if _type == 'p':
            buf += struct.pack('!B%is' % len(value), len(value), value)
        # tn: variable length list of type 'n'
        # packed like this:
        # [int: items in list][item1][item2][...]
        elif _type[0] == 't':
            buf += struct.pack('!i', len(value))
            for item in value:
                buf += struct.pack('!%s' % _type[1], item)
        # default types
        else:
            try:
                buf += struct.pack('!' + _type, value)
            except struct.error, err:
                raise PacketError('%s.%s(%s,%s): %s' % (self.__class__.__name__, name, value, type(value), err))
        return buf
    def unpack_attr(self, _type, data, pos):
        '''unpack a single attribute from binary stream given current pos'''
        # handle pascal string
        if _type == 'p':
            # the first byte in pascal string is the length of the string
            size = struct.unpack('!B', data[pos:pos+1])[0]
            value = struct.unpack('!%is' % size, data[pos+1:pos+1+size])[0]
            # add one byte to the total size of this attribute
            size += 1
        # handle variable length list type
        elif _type[0] == 't':
            # get the size of the list, first 4 bytes (type "i")
            items = struct.unpack('!i', data[pos:pos+4])[0]
            # type of the items on this list is given as the second element in the type tuple
            list_type = '!%s' % _type[1]
            list_type_size = struct.calcsize(list_type)
            # total size is the 4 bytes (length) plus the type size times number of elements
            size = 4 + items * list_type_size
            value = []
            for a in range(items):
                offset = list_type_size*a+pos+4
                value.append(struct.unpack(list_type, data[offset:offset+list_type_size])[0])
        # handle built-in struct type
        else:
            size = struct.calcsize(_type)
            try:
                value = struct.unpack('!'+_type, data[pos:pos+size])[0]
            except struct.error, err:
                raise PacketError('Error unpacking "%s": %s' % (self.__class__.__name__, err))
        return value, size




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
# system.py
import struct
import messaging
import transport
import logging
import util
import time

__all__ = ('Message', 'ActorManager', 'Actor', 'PacketError', 'PacketTypeError', 'GroupAlreadyExists', 'GroupDoesNotExist', 'CreateGroupError')

processing = None

try:
    import processing as processing
except ImportError:
    pass
else:
    processing.enableLogging(level=logging.INFO)
    logger = processing.getLogger()

try:
    import multiprocessing as processing
except ImportError:
    pass
else:
    logger = processing.get_logger()

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
    
def _subprocess_main(name, default_actor_class, max_tick_time, interval, server_addr, _should_quit, packet_types):
    '''interval is in milliseconds of how long to sleep before another tick'''
    # creating a client mode manager
    manager = ActorManager.get_singleton()
    # the new manager may not have all packet types registered, register them here
    if manager.packet_types:
        # on windows, packet types will be auto-registered
        assert set(manager.packet_types) == set(packet_types)
    else:
        # on *nix, forking would cause packets NOT be auto-registered
        manager.packet_types = packet_types
    manager._ipc_connect(server_addr, _should_quit)
    logger.info('process "%s" is bound to address: "%s"' % (processing.current_process().pid, manager.ipc_transport._connection.fileno()))
    if default_actor_class:
        manager.register_actor(default_actor_class())
    while not manager._should_quit.value:
        start = util.get_time()
        manager.tick(maxTime=max_tick_time)
        # we want to sleep the different between the time it took to process and the interval desired
        _time_to_sleep = interval - (util.get_time() - start)
        time.sleep(_time_to_sleep)
    return False

class ActorManager(messaging.MessageManager):
    '''provides actor, IPC and network functionality'''
    MAIN_GROUP_NAME = '__MAIN_GROUP__'
    def init(self):
        messaging.MessageManager.init(self)
        self.objectIDMap = {}
        self.objectNameMap = {}
        
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
    def find(self, name):
        '''returns an object by its name, None if not found'''
        return self.get_actor_by_name(name)
    def get_actor(self, id):
        return self.objectIDMap.get(id, None)
    def get_actor_by_name(self, name):
        return self.objectNameMap.get(name, None)
    @property
    def actors(self):
        return self.objectIDMap.values()
    def trigger_to_actor(self, id, msg):
        '''
        sends a particular game object a message if that game object implements this message type
        
        return:
        
        - `True`: if event was consumed
        - `False`: otherwise
        '''
        obj = self.objectIDMap[id]
        for recr in self.messageReceiverMap[messaging.WildCardMessageType]:
            recr.handle_message(msg)
        return obj.handle_message(msg)
    def queue_message_to_actor(self, id, msg):
        msg.receiverID = id
        self.queue_message(msg)
        return True
    def register_actor(self, obj, name=None):
        messaging.MessageManager.registerReceiver(self, obj)
        self.objectIDMap[obj.gid] = obj
        if name:
            self.objectNameMap[name] = obj
        return obj
    def unregister_actor(self, obj):
        messaging.MessageManager.unregisterReceiver(self, obj)
        del self.objectIDMap[obj.gid]
        
        # deleting the object from the dictionary the safe way
        n = None
        for name,o in self.objectNameMap.items():
            if o == obj:
                n = name
                break
        if not n == None:
            del self.objectNameMap[n]
                
        return self
    def designated_to_handle(self, r, m):
        '''handles designated messages'''
        if m.receiverID:
            if m.receiverID == r.gid:
                return True
            else:
                return False
        else:
            # if receiverID isn't specified, whoever registers can handle this message
            return True
    def tick(self, evt=None, **kws):
        '''calls update on all objects before message manager ticks'''
        '''first poll process for packets, then network messages, then object updates'''
        self.ipc_transport.poll(self.packet_handler)
        self.transport.poll(self.packet_handler)
        logger.debug('process "%s" queue length: %s' % (processing.current_process().pid, self.queue_length))
        
        # process all messages first
        ret = messaging.MessageManager.tick(self, **kws)
        # then update all the game objects
        objs = self.objectIDMap.values()
        objs.sort(lambda x,y: y._SYNC_PRIORITY - x._SYNC_PRIORITY)
        map(lambda x: x.update(evt), objs)
        return ret
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
        logger.info('queuing message "%s" to "%s"' % (msg, self.ipc_transport.peers[_clientid].fileno()))
        self.ipc_transport.send(msg.to_string(), _clientid)
    def broadcast_message(self, msg):
        self.transport.send(msg.to_string(), broadcast=True)
        return self
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
        if packet_class.__name__ == 'Message':
            return
        if not packet_class.packet_type:
            raise PacketTypeError('Packet_type must be specified by class "%s"' % packet_class)
        if packet_class.packet_type <= 100:
            raise PacketTypeError('Packet_type must be greater than 100.  Had "%s"' % packet_class.packet_type)
        if self.packet_types.has_key(packet_class.packet_type):
            raise PacketTypeError('Packet_type is already registered with packet "%s"' % self.packet_types[packet_class.packet_type])
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
        p = processing.Process(target=_subprocess_main, name=name, args=(name, actor_class, max_tick_time, interval, server_addr, switch, self.packet_types))
        p.start()
        logger.info('started group "%s" in process "%s"' % (name, p.pid))
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
        self.groups = {}
    @property
    def queue_length(self):
        return len(self.activeQueue)
    def reset(self):
        '''mainly used for testing'''
        messaging.MessageManager.reset(self)
        self.objectIDMap = {}
        self.objectNameMap = {}
        
        self.clear_process_group()
        self.gid = 0
        if transport.RAKNET_AVAILABLE:
            self.transport = transport.RakNetTransport()
        else:
            self.transport = transport.Transport()
        self.clients = {}
        # not removing the auto-registered packet types
        # self.packet_types = {}
        self.groups = {}
        self.is_main_process = None
        self.ipc_transport = transport.IPCTransport()
                
class Actor(messaging.MessageReceiver):
    @property
    def gid(self):
        '''return a globally unique id that is good cross processes'''
        return (ActorManager.get_singleton().gid, id(self))
    
class DefaultActor(Actor):
    subscriptions = [messaging.WildCardMessageType]
    def handle_message(self, msg):
        processing.get_logger().info('Default actor received message "%s"' % msg)
        return False

class AutoMessageRegister(type):
    def __init__(cls, name, bases, dct):
        super(AutoMessageRegister, cls).__init__(name, bases, dct)
        ActorManager.get_singleton().register_packet_type(cls)
        
class Message(messaging.Message):
    '''a packet is a network message'''
    __metaclass__ = AutoMessageRegister
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

# system.py
from __future__ import with_statement
import messaging

MessageReceiver = messaging.MessageReceiver
Message = messaging.Message

class ObjectManager(messaging.MessageManager):
    '''a generic object manager
    '''
    def init(self):
        messaging.MessageManager.init(self)
        self.objectIDMap = {}
        self.objectNameMap = {}
    def find(self, name):
        '''returns an object by its name, None if not found'''
        return self.get_object_by_name(name)
    def get_object(self, id):
        return self.objectIDMap.get(id, None)
    def get_object_by_name(self, name):
        return self.objectNameMap.get(name, None)
    @property
    def objects(self):
        return self.objectIDMap.values()
    def trigger_to_object(self, id, msg):
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
    def queue_message_to_object(self, id, msg):
        msg.receiverID = id
        self.queue_message(msg)
        return True
    def register_object(self, obj, name=None):
        messaging.MessageManager.registerReceiver(self, obj)
        self.objectIDMap[obj.gid] = obj
        if name:
            self.objectNameMap[name] = obj
        return obj
    def unregister_object(self, obj):
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
    def reset(self):
        '''mainly used for testing'''
        messaging.MessageManager.reset(self)
        self.objectIDMap = {}
        self.objectNameMap = {}
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
        # process all messages first
        ret = messaging.MessageManager.tick(self, **kws)
        # then update all the game objects
        objs = self.objectIDMap.values()
        objs.sort(lambda x,y: y._SYNC_PRIORITY - x._SYNC_PRIORITY)
        map(lambda x: x.update(evt), objs)
        return ret



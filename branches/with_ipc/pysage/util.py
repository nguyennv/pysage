# util.py
import sys
import time
import threading
import os

class Singleton(object):
    def __new__(cls, *args, **kwds):
        return cls.get_singleton(*args, **kwds)
    @classmethod
    def get_singleton(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = object.__new__(cls)
        it.init(*args, **kwds)
        return it      
    def init(self, *args, **kwds):
        pass

class ProcessLocalSingleton(object):
    '''fork safe'''
    def __new__(cls, *args, **kwds):
        return cls.get_singleton(*args, **kws)
    @classmethod
    def get_singleton(cls, *args, **kwds):
        it = cls.__dict__.get("__it__")
        if it is not None and it[0] == os.getpid():
            return it[1]
        cls.__it__ = it = (os.getpid(), object.__new__(cls))
        it[1].init(*args, **kwds)
        return it
    def init(self, *args, **kwds):
        pass
    @classmethod
    def _clear_singleton(cls):
        cls.__it__ = None
    
class ThreadLocalSingleton(object):
    '''not fork safe'''
    def __new__(cls, *args, **kwds):
        return cls.get_singleton(*args, **kwds)
    @classmethod
    def get_singleton(cls, *args, **kwds):
        pool = cls.__dict__.get("__singleton_pool__")
        if not pool:
            pool = cls.__singleton_pool__ = threading.local()
            
        if not getattr(pool, '__singleton__',None):
            pool.__singleton__ = object.__new__(cls)
            pool.__singleton__.init(*args, **kwds)
        return pool.__singleton__
    def init(self, *args, **kwds):
        pass
    @classmethod
    def _clear_singleton(cls):
        cls.__singleton_pool__ = None

if sys.platform.startswith("win"):
    get_time = time.clock
else:
    get_time = time.time
    

# test_singleton.py
from pysage.util import *
import unittest
import thread
import time

processing = None

try:
    import multiprocessing as processing
except ImportError:
    pass

try:
    import processing as processing
except ImportError:
    pass

if not processing:
    raise Exception('pysage requires either python2.6 or the "processing" module')

class TestClass(ThreadLocalSingleton):
    pass

def return_instance_id():
    return id(TestClass.get_singleton())

def proc_change_id(q):
    q.put(id(TestClass.get_singleton()))

class TestSingleton(unittest.TestCase):
    def tearDown(self):
        TestClass._clear_singleton()
    def test_same_thread(self):
        return return_instance_id() == return_instance_id()
    def test_singleton_threadlocal(self):
        '''tests that each thread has its own manager'''
        threads = []
        def change_id():
            sid = id(TestClass.get_singleton())
            print 'new thread "%s": %s' % (thread.get_ident(), sid)
            threads.append(sid)
        
        assert not threads
        thread.start_new_thread(change_id, ())
        
        nid = id(TestClass.get_singleton())
        print 'existing thread "%s": %s' % (thread.get_ident(), nid)
        time.sleep(1)
        print 'list contains: %s' % threads[0]
        assert not threads[0] == id(TestClass.get_singleton())
    def test_singleton_process(self):
        '''tests that all processes have their own manager, --> unnecessary'''
        queue = processing.Queue()
        assert queue.empty()
        
        p = processing.Process(target=proc_change_id, args=(queue,))
        p.start()
        p.join()
        
        assert not queue.empty()
        assert not queue.get() == id(TestClass.get_singleton())
    def test_singleton_process_before_fork(self):
        '''tests that all processes have their own manager, --> unnecessary'''
        s = TestClass.get_singleton()
        queue = processing.Queue()
        assert queue.empty()
        
        p = processing.Process(target=proc_change_id, args=(queue,))
        p.start()
        p.join()
        
        assert not queue.empty()
        assert not queue.get() == id(TestClass.get_singleton())
        
        
        

# test_singleton.py
from pysage.util import *
import unittest
import thread
import processing
import time

class TestClass(ThreadLocalSingleton):
    pass

def return_instance_id():
    return id(TestClass.get_singleton())

class TestSingleton(unittest.TestCase):
    def test_same_thread(self):
        return return_instance_id() == return_instance_id()
    def test_singleton_threadlocal(self):
        threads = []
        def change_id():
            threads.append(id(TestClass.get_singleton()))
        
        assert not threads
        thread.start_new_thread(change_id, ())
        time.sleep(1)
        assert threads[0]
        assert not threads[0] == id(TestClass.get_singleton())
        
        
        
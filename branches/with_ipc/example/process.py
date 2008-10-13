import processing
import time

def run(shutdown):
    while not shutdown.value:
        print 'hi'
        time.sleep(3)
        
if __name__ == '__main__':
    v = processing.Value('B', 0)
    p = processing.Process(target=run, args=(v,))
    p.start()
    
    
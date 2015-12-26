## Migration ##
In pysage 1.6.0, `ActorManager.listen(...)` and `ActorManager.connect(...)` only accepts keyword arguments:

```
ActorManager.get_singleton().listen(host='localhost', port='8888')

# and

ActorManager.get_singleton().connect(host='localhost', port='8888')
```

## About ##
[pysage](http://community.nobotgames.com) is a lightweight high-level message passing library supporting actor based concurrency.

It also extends the "[actor model](http://en.wikipedia.org/wiki/Actor_model)" to support actor partitioning/grouping to further scalability.  pysage has a simple high-level interface.  Messages are serialized and sent lightweight using pipes or domain sockets across local "groups".  In the case of network messages, UDP is used.
  * simple pythonic API
  * efficient message propagation within group, across group, across network
  * network messages can optionally be configured to be reliable and/or ordered using UDP
  * grouping - actors can be partitioned into groups that are run in separate os processes
  * process-local singleton manager - actor registration, discovery, message propagation
  * publisher/subscriber pattern built-in
  * message handlers can be a coroutine / generator
  * optionally use mongodb as the message transport / queue

pysage strives to stay thin and lightweight.

Web site: http://community.nobotgames.com/pysage

```
import time
from pysage import Actor, ActorManager, Message

mgr = ActorManager.get_singleton()

class BombMessage(Message):
    properties = ['damage']

class Player(Actor):
    subscriptions = ['BombMessage']
    def handle_BombMessage(self, msg):
        print 'I took %s damage from the bomb' % msg.get_property('damage')

mgr.register_actor(Player(), 'player1')
mgr.queue_message(BombMessage(damage=10))

while True:
    processed = mgr.tick()
    time.sleep(.03)
```

## Coroutines! ##

Here's a slightly more involved version incorporating async message handing.  Coroutines are cool!

```

import time
from pysage import Actor, ActorManager, Message

mgr = ActorManager.get_singleton()

class TimeBombMessage(Message):
    properties = ['damage']

class Player(Actor):
    subscriptions = ['TimeBombMessage']
    def handle_TimeBombMessage(self, msg):
        print 'thinking'
        # waits until the next "tick"
        yield
        print 'thinking'
        # waits until the next "tick"
        yield
        print 'I took %s damage from the bomb' % msg.get_property('damage')

mgr.register_actor(Player(), 'player1')
mgr.queue_message(TimeBombMessage(damage=10))

while True:
    processed = mgr.tick()
    # uncomment below to see the timing of coroutines
    # print 'ticked'
    time.sleep(.03)
```

Documentation: http://community.nobotgames.com/documentation.html
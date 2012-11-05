from tornado import websocket
import tornado.web
import tornado.ioloop
from multiprocessing import Process
import time
import os

from pyzmq_stream_poller import *

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')

server_pub_port  = '5558'
        
class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        self.times = {}
        Process(target=server_pub, args=(server_pub_port,)).start()
        client(server_pub_port, self)
        print "WebSocket opened"

    def on_message(self, message):
        self.times[int(message)].append(time.time())

    def write_message(self, msg):
        if msg != 'close':
            self.times[msg[0]] = [time.time()]
        super(ZMQWebSocket, self).write_message(unicode(msg))
        
    def on_close(self):
        print "WebSocket closed"
        for k, (s, e) in self.times.iteritems():
            print k, e - s

settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
    "login_url": "/login",
    "xsrf_cookies": True,
    "debug" : True
}

app = tornado.web.Application([
    (r"/", MainHandler),
    (r"/websocket", ZMQWebSocket),
], **settings)

if __name__ == "__main__":
    app.listen(8888)
    tornado.ioloop.IOLoop.instance().start()

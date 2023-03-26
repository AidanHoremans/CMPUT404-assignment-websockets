#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, Response
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, value):
        self.queue.put_nowait(value)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()
clients = list()

def set_listener( entity, data ):
    ''' do something with the update ! '''
    for client in clients:
        client.put({entity: data})

myWorld.add_set_listener( set_listener )
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return flask.redirect("/static/index.html")

def read_ws(ws,client:Client):
    '''A greenlet function that reads from the websocket and updates the world'''
    try:
        while True:
            msg = ws.receive()
            if (msg is not None):
                packet = json.loads(msg)
                entity, = packet
                myWorld.set(entity, packet[entity])
            else:
                break
    except:
        pass

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    # XXX: TODO IMPLEMENT ME
    client = Client()
    clients.append(client)
    g_event = gevent.spawn(read_ws, ws, client)
    try:
        while True:
            message = json.dumps(client.get())
            ws.send(message)
    except Exception as e:
        print(e)
    finally:
        clients.remove(client)
        gevent.kill(g_event)

def is_json():
    if request.mimetype == "application/json":
        return True
    return False

# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    if request.method == 'POST': #update an existing entity?
        if not is_json():
            return Response(status=400)
        entity_body = flask_post_json()
        for key in entity_body:
            myWorld.update(entity, key, entity_body[key]) #update each key to match the value. If the entity doesn't exist it creates it
        return Response(json.dumps(myWorld.get(entity)), status=200, mimetype='application/json')
    
    elif request.method == 'PUT': #add a new entity
        if not is_json():
            return Response(status=400)
        entity_body = flask_post_json()
        myWorld.set(entity, entity_body)
        return Response(json.dumps(myWorld.get(entity)), status=200, mimetype='application/json')

    return Response(status=405)

@app.route("/world", methods=['POST','GET'])
def world():
    '''you should probably return the world here'''
    if request.method == 'GET':
        return Response(json.dumps(myWorld.world()), status=200, mimetype='application/json')
    elif request.method == 'POST':
        if not is_json():
            return Response(status=400)
        space = flask_post_json()
        myWorld.replace(space)
        return Response(json.dumps(myWorld.world()), status=200, mimetype='application/json')
    return Response(status=405)

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    if request.method == 'GET':
        return Response(json.dumps(myWorld.get(entity)), status=200, mimetype='application/json')
    return Response(status=405)


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    if request.method == 'POST':
        myWorld.clear()
        return Response(json.dumps(myWorld.world()), status=200, mimetype='application/json')
    
    return Response(status=405)



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    #app.run()
    os.system("gunicorn -k flask_sockets.worker sockets:app")

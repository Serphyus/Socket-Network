import socket
import pickle
import dill
import zlib
from os import urandom
from time import sleep
from random import randint
from threading import Thread



class NetworkUtils:
    class transmission_types:
        ping = 0
        data_transfer = 1

    class data_encoders:
        simple_encoder = pickle
        complex_encoder = pickle


    @classmethod
    def ping(cls, _socket):
        cls._sendData(
            _socket, cls.transmission_types.ping, urandom(64), 
            False, cls.data_encoders.simple_encoder
        )


    @classmethod
    def _check_transmission_type(cls, _type):
        if not _type in [getattr(cls.transmission_types, i) for i in dir(cls.transmission_types) if not i.startswith('__')]:
            return False
        return True


    @classmethod
    def _sendData(cls, _socket, data, transmission_type, compress, encoder):
        if not cls._check_transmission_type(transmission_type):
            raise TypeError('invalid transmission_type provided')

        if type(data) != bytes:
            body = encoder.dumps(data)
            pre_encoded = False
        else:
            body = data
            pre_encoded = True
        
        if compress:
            body = zlib.compress(body)
        
        header = encoder.dumps(
            {
                'transmission_type': transmission_type,
                'body_size': len(body),
                'compressed': compress,
                'pre_encoded': pre_encoded
            }
        )

        _socket.send(header)
        _socket.send(body)


    @classmethod
    def _recvData(cls, _socket, header_size, encoder):
        header = encoder.loads(_socket.recv(header_size))
        body = _socket.recv(header['body_size'])

        if header['compressed']:
            body = zlib.decompress(body)

        if not header['pre_encoded']:
            body = encoder.loads(body)

        return [header, body]



class Server:
    class Client:
        def __init__(self, server, address, clientsocket, socket_timeout=None):
            # set attributes for the client
            self.address = address
            self.clientsocket = clientsocket
            
            # (optional) set a timeout for the socket
            if socket_timeout != None:
                self.clientsocket.settimeout(socket_timeout)



    def __init__(self, server_address, **kwargs):
        # setup the server socket
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(server_address)
        self.s.listen(kwargs.get('backlog', 1))

        # set max client connections and create clients pool and queue
        self.max_clients = kwargs.get('max_clients', 4)
        self.clients_pool = []
        self.clients_queue = []

        # create a list for banned ip addresses
        self.banned_clients = []

        # set settings from kwargs
        self.max_header_size = kwargs.get('max_header_size', 256)
        self.accepting_clients = kwargs.get('accepting_clients', True)
        self.disconnect_at_timeout = kwargs.get('disconnect_at_timeout', False)

        # create threads to run in background
        self.server_threads = type(
            'obj', (object,),
            {
                'client_listener': Thread(target=self._listenForClients, args=(self.max_clients,), daemon=True),
            }
        )

        # start the client listener thread
        self.server_threads.client_listener.start()
    

    def _listenForClients(self, max_clients, delay=0.1):
        while True:
            # if the flag accepting_clients is True then enter this loop
            while self.accepting_clients:

                # accept a new client and create a client instance
                clientsocket, address = self.s.accept()
                if not address[0] in self.banned_clients:
                    client = self.Client(self, address, clientsocket)

                    if not self.accepting_clients:
                        break

                    # add new client to the queue
                    self._updateClientQueue(client)
                    del(client)

                else: clientsocket.close()
                del(clientsocket, address)

            # while server is not accepting clients wait 0.1 seconds for each time it checks
            sleep(0.1)


    def _updateClientQueue(self, client=None):
        if client != None:
            self.clients_queue.append(client)

        if len(self.clients_pool) < self.max_clients:
            if len(self.clients_queue) > 0:
                self.clients_pool.append(self.clients_queue[0])
                self.clients_queue.pop(0)


    def _getClientIndex(self, client_address: tuple):
        # go through each client in the pool and return the index that matches the address 
        for index, client in enumerate(self.clients_pool):
            if client_address == client.address:
                return index
        raise IndexError(f'{client_address} was not found in self.client_pool')


    def getClients(self):
        return [client.address for client in self.clients_pool]


    def ban_ip_address(self, ip_address):
        if ip_address not in self.banned_clients:
            self.banned_clients.append(ip_address)


    def unban_ip_address(self, ip_address):
        if ip_address in self.banned_clients:
            self.banned_clients.remove(ip_address)


    def removeClient(self, client_address: tuple, ban_ip=False):
        # get client index that matches the client_address parameter from client pool
        client_index = self._getClientIndex(client_address)

        # try to disconnect the client
        try:
            self.clients_pool[client_index].clientsocket.close()

        except:
            pass

        # remove client from the pool
        self.clients_pool.pop(client_index)
        
        # update the client queue so that more clients may connect
        self._updateClientQueue()

        if ban_ip:
            self.ban_ip_address(client_address[0])


    def sendData(self, client_address: tuple, data, transmission_type=NetworkUtils.transmission_types.data_transfer, compress=False, encoder=NetworkUtils.data_encoders.simple_encoder, max_timeouts=5):
        # get the clientsocket of the client in self.clients_pool matching the address
        clientsocket = self.clients_pool[
            self._getClientIndex(client_address)
        ].clientsocket

        # try to send the data to client
        try:
            NetworkUtils._sendData(clientsocket, data, transmission_type, compress, encoder)

        # if the client connection is broken remove the client
        except ConnectionError:
            self.removeClient(client_address)

        # if the client times out check the internal flag for disconnecting on timeout
        except socket.timeout:
            if self.disconnect_at_timeout:
                self.removeClient(client_address)



    def recvData(self, client_address: tuple, encoder=NetworkUtils.data_encoders.simple_encoder, max_timeouts=4):
        # get the clientsocket of the client in self.clients_pool matching the address
        clientsocket = self.clients_pool[
            self._getClientIndex(client_address)
        ].clientsocket

        # try to recv data from client
        try:
            return NetworkUtils._recvData(clientsocket, self.max_header_size, encoder)

        # if the client connection is broken remove the client
        except ConnectionError:
            self.removeClient(client_address)
            return False
        
        # if the client times out check the internal flag for disconnecting on timeout
        except socket.timeout:
            if self.disconnect_at_timeout:
                self.removeClient(client_address)



class Client:
    def __init__(self, socket_timeout=None, **kwargs):
        # setup the client socket and establish a connection with the server
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # (optional) set a timeout for the socket
        if socket_timeout != None:
            self.s.settimeout(socket_timeout)

        self.max_header_size = kwargs.get('max_header_size', 256)


    def connect(self, server_address):
        # connect to server
        self.s.connect(server_address)


    def disconnect(self):
        # disconnect from the server
        self.s.close()


    def sendData(self, data, transmission_type=NetworkUtils.transmission_types.data_transfer, compress=False, encoder=NetworkUtils.data_encoders.simple_encoder):
        # send data using the socket self.s
        NetworkUtils._sendData(self.s, data, transmission_type, compress, encoder)


    def recvData(self, encoder=NetworkUtils.data_encoders.simple_encoder):
        # receieve data using the socket self.s
        return NetworkUtils._recvData(self.s, self.max_header_size, encoder)
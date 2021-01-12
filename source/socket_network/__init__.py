import socket
import dill
import zlib
from time import sleep
from random import randint
from threading import Thread



class NetworkUtils:
    @staticmethod
    def ping(): ...


    @staticmethod
    def _sendData(_socket, transmission_type, data, compress):
        if type(data) != bytes:
            body = dill.dumps(data)
            pre_encoded = False
        else:
            body = data
            pre_encoded = True
        
        if compress:
            body = zlib.compress(body)

        header = dill.dumps(
            {
                'transmission_type': transmission_type,
                'body_size': len(body),
                'compressed': compress,
                'pre_encoded': pre_encoded
            }
        )

        _socket.send(header)
        _socket.send(body)


    @staticmethod
    def _recvData(_socket, header_size):
        header = dill.loads(_socket.recv(header_size))
        body = _socket.recv(header['body_size'])

        if header['compressed']:
            body = zlib.decompress(body)

        if not header['pre_encoded']:
            body = dill.loads(body)

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
                client = self.Client(self, address, clientsocket)
                
                if not self.accepting_clients:
                    break

                # add new client to the queue
                self._updateClientQueue(client)

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
        for client in self.clients_pool:
            if client_address == client.address:
                return self.clients_pool.index(client)
        raise IndexError(f'{client_address} was not found in self.client_pool')


    def getClients(self):
        return [client.address for client in self.clients_pool]


    def removeClient(self, client_address: tuple):
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


    def sendData(self, client_address: tuple, data, compress=False, transmission_type='data_transfer', max_timeouts=5):
        # get the clientsocket of the client in self.clients_pool matching the address
        clientsocket = self.clients_pool[
            self._getClientIndex(client_address)
        ].clientsocket

        # try to send the data to client
        try:
            NetworkUtils._sendData(clientsocket, transmission_type, data, compress)

        # if the client connection is broken remove the client
        except ConnectionError:
            self.removeClient(client_address)

        # if the client times out check the internal flag for disconnecting on timeout
        except socket.timeout:
            if self.disconnect_at_timeout:
                self.removeClient(client_address)



    def recvData(self, client_address: tuple, max_timeouts):
        # get the clientsocket of the client in self.clients_pool matching the address
        clientsocket = self.clients_pool[
            self._getClientIndex(client_address)
        ].clientsocket

        # try to recv data from client
        try:
            return NetworkUtils._recvData(clientsocket, self.max_header_size)

        # if the client connection is broken remove the client
        except ConnectionError:
            self.removeClient(client_address)
            return False
        
        # if the client times out check the internal flag for disconnecting on timeout
        except socket.timeout:
            if self.disconnect_at_timeout:
                self.removeClient(client_address)



class Client:
    def __init__(self, server_address, socket_timeout=None, **kwargs):
        # setup the client socket and establish a connection with the server
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect(server_address)
        
        # (optional) set a timeout for the socket
        if socket_timeout != None:
            self.s.settimeout(socket_timeout)

        self.max_header_size = kwargs.get('max_header_size', 256)


    def sendData(self, data, compress=False, transmission_type='data_transfer'):
        # send data using the socket self.s
        NetworkUtils._sendData(self.s, transmission_type, data, compress)


    def recvData(self):
        # receieve data using the socket self.s
        return NetworkUtils._recvData(self.s, self.max_header_size)
    

    def disconnect(self):
        # disconnect from the server
        self.s.close()
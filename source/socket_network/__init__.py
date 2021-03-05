import socket
import pickle
import zlib
import msgpack
from time import sleep
from threading import Thread, ThreadError
from ._version import __version__



class NetworkUtils:
    class data_encoders:
        simple = pickle
        advanced = msgpack


    @classmethod
    def _sendData(cls, _socket, data: any, encoder: str, compress: bool) -> None:
        encoder = getattr(NetworkUtils.data_encoders, encoder)
        
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
                'body_size': len(body),
                'compressed': compress,
                'pre_encoded': pre_encoded
            }
        )

        _socket.send(header)
        _socket.send(body)


    @classmethod
    def _recvData(cls, _socket, encoder: str, header_size: int) -> any:
        encoder = getattr(NetworkUtils.data_encoders, encoder)

        header = encoder.loads(_socket.recv(header_size))
        body = _socket.recv(header['body_size'])

        if header['compressed']:
            body = zlib.decompress(body)

        if not header['pre_encoded']:
            body = encoder.loads(body)

        return body



class Server:
    class Client:
        def __init__(self, address: tuple, clientsocket, socket_timeout=None):
            # set attributes for the client
            self.address = address
            self.clientsocket = clientsocket
            
            # (optional) set a timeout for the socket
            if socket_timeout != None:
                self.clientsocket.settimeout(socket_timeout)


    def __init__(self, server_address: tuple, max_clients: int, **kwargs):
        # setup the server socket
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(server_address)
        self.s.listen(kwargs.get('backlog', 1))

        # set max client connections and create clients pool and queue
        self.address = server_address
        self.max_clients = max_clients
        self.clients_pool = []
        self.clients_queue = []

        # create a list for banned ip addresses
        self.banned_clients = []

        # set settings from kwargs
        self.max_header_size = kwargs.get('max_header_size', 256)
        self.accepting_clients = kwargs.get('accepting_clients', True)
        self.disconnect_at_timeout = kwargs.get('disconnect_at_timeout', False)

    
    def listen(self, callback=None, *callback_args) -> None:
        # create daemon threads to be run in background
        if hasattr(self, 'client_listener'):
            if self.client_listener.is_alive:
                raise ThreadError('client_listener thread is already running')
            self.client_listener.start()

        self.client_listener = Thread(target=self._listenForClients, args=(callback, *callback_args), daemon=True)
        self.client_listener.start()


    def _listenForClients(self, callback=None, *callback_args) -> None:
        while True:
            # if the flag accepting_clients is True then enter this loop
            while self.accepting_clients:

                # accept a new client and create a client instance
                clientsocket, address = self.s.accept()
                if not address[0] in self.banned_clients:
                    client = self.Client(address, clientsocket)

                    if not self.accepting_clients:
                        break

                    # add new client to the queue
                    self._updateClientQueue(client)

                    if callback != None:
                        if callable(callback):
                            callback(client=client, *callback_args)
                        else:
                            raise TypeError(f'{type(callback)} is not callable')

                    del(client)

                else: clientsocket.close()
                del(clientsocket, address)
            
            # while server is not accepting clients wait 0.1 seconds for each time it checks
            sleep(0.1)


    def _updateClientQueue(self, client=None) -> None:
        if isinstance(client, self.Client):
            self.clients_queue.append(client)

        while len(self.clients_pool) < self.max_clients:
            if len(self.clients_queue) > 0:
                self.clients_pool.append(self.clients_queue[0])
                self.clients_queue.pop(0)
            else:
                break


    def _getClientIndex(self, client_address: tuple) -> int:
        # go through each client in the pool and return the index that matches the address 
        for index, client in enumerate(self.clients_pool):
            if client_address == client.address:
                return index
        raise IndexError(f'{client_address} was not found in self.client_pool')


    def updateMaxClients(self, max_clients: int) -> None:
        self.max_clients = max_clients
        self._updateClientQueue()


    def getClient(self, client_address: tuple) -> object:
        return self.clients_pool[self._getClientIndex(client_address)]


    def getAllClients(self) -> list:
        return [client for client in self.clients_pool]


    def checkAddress(self, ip_address: tuple) -> bool:
        split_ip = ip_address[0].split('.')
        if len(split_ip) != 4:
            return False
        
        for i in split_ip:
            if not i.isdigit():
                return False
        
        if not ip_address[1].isdigit():
            return False
        
        return True


    def ban_ip_address(self, ip_address: tuple) -> None:
        if not self.checkAddress(ip_address):
            raise TypeError('%s is not a valid addres' % ip_address)
        
        if ip_address in self.banned_clients:
            raise IndexError('%s is already banned' % ip_address)

        self.banned_clients.append(ip_address)
        return True


    def unban_ip_address(self, ip_address) -> None:
        if ip_address in self.banned_clients:
            raise TypeError('%s is not a valid addres' % ip_address)
        
        if ip_address in self.banned_clients:
            raise IndexError('%s is not already banned' % ip_address)

        self.banned_clients.remove(ip_address)
        return True


    def removeClient(self, client_address: tuple, ban_ip=False) -> None:
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


    def sendData(self, client_address: tuple, data, data_encoder='simple', compress=False) -> None:
        # get the clientsocket of the client in self.clients_pool matching the address
        clientsocket = self.clients_pool[
            self._getClientIndex(client_address)
        ].clientsocket

        # try to send the data to client
        try:
            NetworkUtils._sendData(clientsocket, data, data_encoder, compress)

        # if the client connection is broken remove the client
        except ConnectionError:
            self.removeClient(client_address)

        # if the client times out check the internal flag for disconnecting on timeout
        except socket.timeout:
            if self.disconnect_at_timeout:
                self.removeClient(client_address)



    def recvData(self, client_address: tuple, data_encoder='simple') -> any:
        # get the clientsocket of the client in self.clients_pool matching the address
        clientsocket = self.clients_pool[
            self._getClientIndex(client_address)
        ].clientsocket

        # try to recv data from client
        try:
            return NetworkUtils._recvData(clientsocket, data_encoder, self.max_header_size)

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


    def connect(self, server_address) -> None:
        # connect to server
        self.s.connect(server_address)


    def disconnect(self) -> None:
        # disconnect from the server
        self.s.close()


    def sendData(self, data, data_encoder='simple', compress=False) -> None:
        # send data using the socket self.s
        NetworkUtils._sendData(self.s, data, data_encoder, compress)


    def recvData(self, data_encoder='simple',) -> any:
        # receieve data using the socket self.s
        return NetworkUtils._recvData(self.s, data_encoder, self.max_header_size)
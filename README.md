Socket-Network
==============


Description
-----------
A simple server and client module for general use in socket communication


Pip Requirements
------------
- dill


Features
--------
- Automated server queue and pool for clients.
- Able to send every type of object using dill encoder.
- Automaticly removes clients when unable connection is broken and socket timeout if disconnect_at_timeout is True


Future Improvements
-------------------
- Fix bugs with timeout
- Add a data transfer queue for each client
- Add a pinging functionality to each client which can optionally run in background to make sure client is connected


Usage (Server)
--------------
<pre>
- Initialize the class while parsing the server_address like ('192.168.10.100', 1234)
- server.sendData         required params: client_address, data   # sends data to client_address
- server.recvData         required params: client_address         # receives data from client_address
- server.removeClient     required params: client_address         # removes client matching client_address
- server.getClients       required params: None                   # returns a list of all client addresses in server.client_pool
- server.start            required params: None                   # starts threads that will run in the background with the server 
</pre>


Usage (Client)
--------------
<pre>
- Initialize the class while parsing server_address like ``('192.168.10.100', 1234)`` (This will connect you automatilcally
- client.sendData         required params: data                   # sends data to server
- client.recvData         required params: None                   # receives data from server
- client.disconnect       required params: None                   # disconnects from server
</pre>

import zmq
import datetime
import json

class PcbDrillClient(object):
    """ Client to wrap the RPC into a friendly method to call (i.e. handles serialization)"""
    def __init__(self):
        self._context = zmq.Context() 
        self._socket = self._context.socket(zmq.REQ)
        #self._session = datetime.datetime.now().strftime('%Y%m%d_%H%M%S.%f')
    def __call__(self, command, **kwargs):
        updated_kwargs = kwargs
        #updated_kwargs['session'] = self._session
        response = self._request(command, **updated_kwargs)
        return response
    def _request(self, command, **kwargs):
        data = {'command': command}
        data.update(kwargs)
        data_serialized = json.dumps(data)
        self._socket.send(data_serialized)
        response = self._socket.recv()
        data = json.loads(response)
        return data
    def connect(self, *args):
        """ Connect to the server """
        self._socket.connect(*args)

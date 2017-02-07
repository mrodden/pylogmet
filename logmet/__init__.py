# Copyright 2016 Mathew Odden
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import select
import socket
import ssl
import struct
import time

LOG = logging.getLogger(__name__)


class SendError(Exception):
    pass


class Logmet(object):
    """
    Simple client for sending metrics and logs to Logmet.

    To use for Metrics::

        import logmet

        lm = logmet.Logmet(
            logmet_host='metrics.opvis.bluemix.net',
            logmet_port=9095,
            space_id='deadbbeef1234567890',
            token='put_your_logmet_logging_token_here'
        )

        lm.emit_metric(name='logmet.test.1', value=1)
        lm.emit_metric(name='logmet.test.2', value=2)
        lm.emit_metric(name='logmet.test.3', value=3)


    To use for Logs::
        import logmet

        lm = logmet.Logmet(
            logmet_host='logs.opvis.bluemix.net',
            logmet_port=9091,
            space_id='deadbbeef1234567890',
            token='put_your_logmet_logging_token_here'
        )

        # Emitting a string will map the string to the "message" field
        lm.emit_log('This is a log message')

        # You can also emit a dictionary where you include fields
        # you can search and filter in logmet kibana.
        lm.emit_log({
          'app_name':'myApp',
          'type':'myType',
          'message':'This is a log message'
        })

    """

    default_timeout = 20.0  # seconds

    def __init__(self, logmet_host, logmet_port, space_id, token):
        self.space_id = space_id
        self._token = token
        self.logmet_host = logmet_host
        self.logmet_port = logmet_port

        self._connect()

    def _connect(self):
        try:
            ssl_context = ssl.create_default_context()
            self.socket = ssl_context.wrap_socket(
                socket.socket(socket.AF_INET),
                server_hostname=self.logmet_host)
        except AttributeError:
            # build our own then; probably not secure, but logmet
            # doesn't seem to check/verify certs?
            self.socket = ssl.wrap_socket(
                socket.socket(socket.AF_INET))

        self.socket.settimeout(self.default_timeout)
        self.socket.connect((self.logmet_host, int(self.logmet_port)))

        self._auth_handshake()

        self._conn_sequence = None

    def _conn_is_dropped(self):
        # logmet appears to shutdown its side after 2 minutes
        # of inactivity on the TCP connection, so...
        # check to see if we got a close message
        list_tup = select.select([self.socket], [], [], 0)
        rlist = list_tup[0]
        return bool(rlist)

    def _assert_conn(self):
        if self._conn_is_dropped():
            LOG.info('Detected closed connection. Reconnecting.')
            self.socket.close()
            self.socket = None
            self._connect()

    def _send_data(self, package, data_type):
        self._assert_conn()

        try:
            self._build_and_send(package, data_type)
        except (socket.error, SendError):
            LOG.exception('Error while attempting to send data!')
            # try a quick connection rebuild and try again
            if self.socket is not None:
                self.socket.close()
            self.socket = None
            self._connect()
            self._build_and_send(package, data_type)

    def _build_and_send(self, package, data_type):
        if self._conn_sequence is None:
            self._conn_sequence = 1

        package = self._wrap_for_send(
            [package], data_type=data_type)

        LOG.debug(
            "Sending wrapped messages: [{}]".format(
                package.encode(
                    'string_escape',
                    errors='backslashreplace'
                )
            )
        )

        self.socket.sendall(package)

        resp = ''
        while _has_readable(self.socket):
            data = self.socket.recv(1024)
            resp += data
            if resp >= 6:
                break

        LOG.debug('ACK buffer: [{}]'.format(repr(resp)))
        if not resp.startswith('1A'):
            raise SendError(
                'Invalid or no ACK from logmet: [{}]'.format(repr(resp)))
        else:
            LOG.debug('ACK-success found')

    def _wrap_for_send(self, messages, data_type):
        msg_wrapper = '1W' + pack_int(len(messages))
        for mesg in messages:
            msg_wrapper += ('1' + data_type +
                            pack_int(self._conn_sequence) +
                            mesg)
            self._conn_sequence += 1
        return msg_wrapper

    def emit_metric(self, name, value, timestamp=None):

        if timestamp is None:
            timestamp = time.time()

        metric_fmt = '{0}.{1} {2} {3}\r\n'
        metric_msg = metric_fmt.format(
            self.space_id, name, value, timestamp)

        encoded = to_bytes(metric_msg)
        packed_metric = pack_int(len(encoded)) + encoded

        self._send_data(packed_metric, data_type='M')

        LOG.debug('Metrics sent to logmet successfully')

    def emit_log(self, message):
        """
        :param message: string or dict to send to logmet
        """

        if isinstance(message, str):
            entry = {'message': message}
        else:
            entry = dict(message)

        # The tenant ID must be included for the message to be accepted
        entry['ALCH_TENANT_ID'] = self.space_id

        encoded = pack_dict(entry)
        encoded = to_bytes(encoded)

        self._send_data(encoded, data_type='D')

        LOG.debug('Log message sent to logmet successfully')

    def _auth_handshake(self):
        # local connection IP addr
        ident = str(self.socket.getsockname()[0])

        ident_fmt = '1I{0}{1}'
        ident_msg = ident_fmt.format(chr(len(ident)), ident)

        self.socket.sendall(ident_msg)

        auth_fmt = '2T{0}{1}{2}{3}'
        auth_msg = auth_fmt.format(
                chr(len(self.space_id)),
                self.space_id,
                chr(len(self._token)),
                self._token)

        self.socket.sendall(auth_msg)

        resp = self.socket.recv(1024)
        if not resp.startswith('1A'):
            raise Exception('Auth failure!')
        LOG.info('Auth to logmet successful')

    def close(self):
        # nicely close
        self.socket.shutdown(1)
        time.sleep(0.1)
        self.socket.close()


def pack_dict(msg):
    """
    :param msg: the dict to pack
    :return: string in the format
       '<num_keypars><len_key1><key1><len_val1><val1>...etc'
    """
    parts = []
    total_keys = len(msg)
    for key, value in msg.iteritems():
        key = to_bytes(key)
        value = to_bytes(value)
        if not value:
            # Keys without corresponding value can cause problems.
            total_keys -= 1
            continue
        parts.extend([
            pack_int(len(key)),
            key,
            pack_int(len(value)),
            value,
        ])

    return pack_int(total_keys) + ''.join(parts)


def pack_int(num):
    return struct.pack('!I', num)


def to_bytes(obj):
    if isinstance(obj, unicode):
        # turn unicode into bytearray/str
        msg = obj.encode('utf-8', 'replace')
    else:
        # cool, already encoded
        msg = str(obj)
    return msg


def _has_readable(sock):
    read_ready = select.select([sock], [], [], 10)[0]
    return bool(read_ready)

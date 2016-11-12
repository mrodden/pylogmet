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

class Logmet(object):
    """
    Simple client for sending metrics to Logmet.

    To use::

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
                server_hostname=logmet_host)
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

    def emit_metric(self, name, value, timestamp=None):
        self._assert_conn()

        if timestamp is None:
            timestamp = time.time()

        metric_fmt = '{0}.{1} {2} {3}\r\n'
        metric_msg = metric_fmt.format(
            self.space_id, name, value, timestamp)

        self._send_metric(metric_msg)

    def _send_metric(self, message):
        if isinstance(message, unicode):
            # turn unicode into bytearray/str
            encoded = message.encode('utf-8', 'replace')
        else:
            # cool, already encoded
            encoded = str(message)

        packed_metric = struct.pack('!I', len(message)) + encoded

        if self._conn_sequence is None:
            self._conn_sequence = 1

        def wrap_for_send(messages):
            msg_wrapper = '1W' + struct.pack('!I', len(messages))
            for idx, mesg in enumerate(messages, start=1):
                msg_wrapper += '1M' + struct.pack('!I', self._conn_sequence) + mesg
                self._conn_sequence += 1
            return msg_wrapper

        metrics_package = wrap_for_send([packed_metric])
        LOG.debug("Sending wrapped messages: [{}]".format(metrics_package))

        acked = False
        while not acked:
            self.socket.sendall(metrics_package)

            try:
                resp = self.socket.recv(16)
                LOG.debug('Ack buffer: [{}]'.format(resp))
                if not resp.startswith('1A'):
                    LOG.warning('Unexpected ACK response from recv: [{}]'.format(resp))
                    time.sleep(0.1)
                else:
                    acked = True
            except Exception:
                LOG.warning('No ACK received from server!')

        LOG.debug('Metrics sent to logmet successfully')

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

        resp = self.socket.recv(16)
        if not resp.startswith('1A'):
            raise Exception('Auth failure!')
        LOG.info('Auth to logmet successful')

    def close(self):
        # nicely close
        self.socket.shutdown(1)
        time.sleep(0.1)
        self.socket.close()

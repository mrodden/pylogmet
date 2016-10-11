
"""
This module can serve as a dummy Logmet endpoint for sending metrics to.

It can be used to check how the collectd plugin and other clients deal
with the metric server endpoint. It was used during the creation of
logmet.py to test the behavior against the original collectd plugin.

You can run it with a simple `python test_server.py` command, but
you will first need to generate a test cert and key for the SSL
socket.

Generate a self signed cert with the following command::

    openssl req -new -x509 -days 365 -nodes -out cert.pem -keyout cert.pem

You can just use all the defaults that the tool gives you.
This should leave a `cert.pem` in the directory where you ran it, which
the server can be pointed at. (It's a keyfile and certfile in one.)
"""

import binascii

import ssl
import socket
import struct

import threading


def main():
    s = ssl.wrap_socket(
        socket.socket(socket.AF_INET),
        server_side=True,
        keyfile='cert.pem',
        certfile='cert.pem')

    s.bind(('', 9095))
    s.listen(1)

    client_threads = []

    try:
        while True:
            client_conn, client_addr = s.accept()
            print 'Got connection from', client_addr

            client_thread = threading.Thread(target=handle_client, args=(client_conn,))
            client_thread.daemon = True
            client_thread.start()
            client_threads.append(client_threads)
    finally:
        s.close()


def handle_client(client_conn):
    try:
        while True:
            data = client_conn.recv(2)

            if data == '1I':
                data = client_conn.recv(1)
                data_len = long(binascii.hexlify(data), 16)
                data = client_conn.recv(data_len)
                print 'Identity: [%s]' % data

            elif data == '2T':
                data = client_conn.recv(1)
                data_len = long(binascii.hexlify(data), 16)
                space_id = ''
                while len(space_id) < data_len:
                    space_id += client_conn.recv(2)

                data = client_conn.recv(1)
                data_len = long(binascii.hexlify(data), 16)
                token = ''
                while len(token) < data_len:
                    token += client_conn.recv(2)

                print 'Auth: space_id=%s' % space_id

                client_conn.sendall('1A')

            elif data == '1W':
                data = client_conn.recv(4)
                data_len = struct.unpack('!I', data)[0]

                metric_count = data_len
                print 'Total metrics in this package:', metric_count

                for metric in xrange(0, metric_count):
                    # read 2 bytes
                    data = client_conn.recv(2)
                    assert data == '1M'

                    data = client_conn.recv(4)
                    data_len = struct.unpack('!I', data)[0]

                    seq_no = data_len

                    data = client_conn.recv(4)
                    data_len = struct.unpack('!I', data)[0]

                    data_item = ''
                    while len(data_item) < data_len:
                        data_item += client_conn.recv(1)

                    #print 'Found data_item: [%s]' % data_item

                print 'seq_no:', seq_no
                client_conn.sendall('1A')
            else:
                if len(data) == 0:
                    print 'Closing client connection'
                    client_conn.close()
                    break

                print 'Received data: [%r]' % data
    finally:
        client_conn.close()


if __name__ == '__main__':
    main()

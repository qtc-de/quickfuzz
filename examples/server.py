import sys
import time
import socket
import argparse
import threading
import json as j
import xml.etree.ElementTree as ET


def client_thread(sock, helo, json, subscribe, xml):
    '''
    Takes a socket object and tries to receive some input from it. If the input
    matches the desired format, something is printed back.

    Parameters:
        sock                    (socket)                Connected TCP socket

    Returns:
        None
    '''
    while True:
        data = sock.recv(2048)

        if helo:
            # If the data is in JSON format, we send something back
            try:
                string = data.decode('utf-8')
                if string == 'helo\n':
                    sock.sendall(b'helo 127.0.0.1\n')
                    sock.close()
                    return 0
            except:
                pass


        if subscribe:
            # If the data is in JSON format, we send something back
            try:
                string = data.decode('utf-8')
                if string == 'subscribe\n':
                    sock.sendall(b'Subscription accepted\n')
                    sock.close()
                    return 0
            except:
                pass


        if xml:
            # If the data is in XML format, we print something back
            try:
                ET.fromstring(data.decode('utf-8'))
                sock.sendall(b'Error: Function tag is missing.\n')
                sock.close()
                return 0
            except:
                pass


        if json:
            # If the data is in JSON format, we send something back
            try:
                j.loads(data.decode('utf-8'))
                sock.sendall(b'Error: Function node is missing.\n')
                sock.close()
                return 0
            except:
                pass

        time.sleep(1)



parser = argparse.ArgumentParser(description='''A simple threading socket server to test the core functionality of 
                                                quickfuzz. Simly select between different payloads that should trigger
                                                a response and run quickfuzz against the server, to check if you get
                                                the desired results.''')

parser.add_argument('port', nargs='?', metavar='port', default=8000, type=int, help='port to listen on')
parser.add_argument('ip', nargs='?', metavar='ip', default='127.0.0.1', help='ip address to listen on')
parser.add_argument('connections', nargs='?', metavar='connections', default=10, type=int, help='allowed number of connections')
parser.add_argument('--helo', action='store_true', help='respond to a payload containing helo')
parser.add_argument('--json', action='store_true', help='respond to any json formatted payload')
parser.add_argument('--subscribe', action='store_true', help='respond to a payload containing subscribe')
parser.add_argument('--xml', action='store_true', help='respond to any xml formatted payload')
args = parser.parse_args()


def main():
    '''
    Opens a listening socket server that accepts connections and starts an individual thread for each connection.
    Inside the thread, the incoming input is checked for specific keywords and depending on the appearance, a response
    is send back or the connection stays idle.

    Paramaters:
        None

    Returns:
        None
    '''
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind((args.ip, args.port))
        sock.listen(args.connections)
        print(f"[+] Socket server listening on {args.ip}:{str(args.port)}")
    except socket.error as msg:
        print("[-] Error during bind operation")
        sys.exit()

    print("[+] Waiting for connections")
    while True:
        conn, addr = sock.accept()
        print(f"[+] Connection from: {addr[0]}:{addr[1]}")
        x = threading.Thread(target=client_thread, args=(conn, args.helo, args.json, args.subscribe, args.xml))
        x.start()


main()

import os
import re
import sys
import ssl
import time
import json
import socket
import select
import termcolor
from io import StringIO
import concurrent.futures


def bytes_to_hex(byte_string):
    '''
    Helper function that converts a bytestring into a formatted hexstring:

    Paramaters:
        byte_string                 (bytes)             bytes object to transform

    Returns:
        hex_string                  (string)            Formatted hex string
    '''
    plain_hex = bytearray(byte_string).hex()
    hex_string = re.sub('(..)', r'\\x\1', plain_hex)
    return hex_string


def apply_format(string, indent=0):
    '''
    Helper function that formats a string with the marker [+] in front of each new line.

    Paramaters:
        string                      (string)            String to print
        indent                      (int)               Indent after each [+]

    Returns:
        formatted                   (string)            Formatted string
    '''
    indent = '    ' * indent
    lines = string.split('\n')
    lines = list(map(lambda x: f'[+] {indent}{x}', lines))
    return '\n'.join(lines)



class Fuzzer:
    '''
    The Fuzzer class is responsible for establishing the connection to the targeted host/port and for
    sending Payload objects and evaluating their success. It is capable of threading and has various
    other settings like the usage of ssl or the amount of time between requetss.
    '''

    def __init__(self, ip, port, connect_timeout=2, max_retries=2, no_color=False, no_failed=False, payloads=[], ssl=False, server_timeout=2, threads=5, verbose=False):
        '''
        Creates a new Fuzzer object.

        Paramaters:
            ip                          (string)                IP address of the target
            port                        (int)                   Port of the target
            connection_timeout          (int)                   Seconds before trying to reconnect
            max_retries                 (int)                   Number of reconnects per payload
            no_fauled                   (bool)                  Do not show unsuccessfull fuzz attempts
            no_olor                     (bool)                  Do not colorize outputs
            payloads                    (list[Payload])         Payloads to use for fuzzing
            ssl                         (bool)                  Using ssl connections
            server_timeout              (int)                   Seconds to wait for a server response
            threads                     (int)                   Number of thrads to use
            verbose                     (bool)                  Print live data for each payload
        '''
        self.ip = ip
        self.port = port
        self.connect_timeout = connect_timeout
        self.max_retries = max_retries
        self.ssl = ssl
        self.server_timeout = server_timeout
        self.threads = threads
        self.verbose = verbose
        self.payloads = payloads
        self.no_failed = no_failed
        self.parameter_dict = {}

        # Each Fuzzer can define its own color scheme, or no colors at all
        self.info_color = None if no_color else "white"
        self.error_color = None if no_color else "red" 
        self.success_color = None if no_color else "green"
        self.payload_color = None if no_color else "yellow"
        self.warning_color = None if no_color else "yellow"


    def connect(self, terminate=False):
        '''
        Establishes a new connection to the targeted host and port. if the target refuses the connection
        a reconnect is attempted until the number of maximum retries is reached.

        Parmaters:
            terminate                   (bool)                  Return None if connection is refused

        Returns:
            sock                        (Socket)                TCP Socket for the targeted port
        '''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if self.ssl:
            context = ssl.SSLContext()
            context.verify_mode = ssl.CERT_NONE
            context.check_hostname = False
            sock = context.wrap_socket(sock)

        target = (self.ip, self.port)

        # If the request is blocked for some reason, we wait some seconds
        # and try again, until the connect works or the maximum number of retires is rached
        retry_count = 0
        connected = False
        while not connected:

            try:
                sock.connect(target)
                connected = True

            # In case our connection request was refused, we should inform the user about this
            except ConnectionRefusedError:
                termcolor.cprint("[/] Connection refused.", self.warning_color, file=sys.stderr)
                if terminate:
                    return None
                # If the maximum number of retries is reached, we end execution from here
                if retry_count == self.max_retries:
                    termcolor.cprint("[-] Maximum number of retries reached. Stopping current thread...", self.error_color, file=sys.stderr)
                    sys.exit(1)
                retry_count += 1
                time.sleep(self.connect_timeout)

        return sock


    def is_blocking(self, sock_num=5):
        '''
        This method checks whether a single connection blocks the targeted port. It is recommended to 
        check if this is the case, before running multi-threaded connections against this port.

        Parameters:
            sock_num                    (int)                   Number of connections to try

        Returns:
            accept_num                  (int)                   Number of accepted connections
        '''
        sockets = []
        for ctr in range(sock_num):
            sock = self.connect(terminate=True)
            sockets.append(sock)
            time.sleep(0.1)

        sockets = list(filter(lambda x: x, sockets))
        accept_num = len(sockets)
        map(lambda x: x.close(), sockets)
        return accept_num


    def add_payload(self, payload):
        '''
        Adds a payload to the Fuzzer object.

        Paramaters:
            payload                     (Payload)               Payload to add

        Returns:
            len                         (int)                   Number of payloads in Fuzzer object
        '''
        self.payloads.add(payload)
        return len(self.payloads)


    def load_payloads(self, payload_dir):
        '''
        Tries to load each payload inside of {payload_dir}. The payloads are read in as binary data stream. 
        A file with name 'oneliners.txt' has a special meaning and contains multiple payloads, each with 
        a length of one line.

        Paramaters:
            payload_dir                 (string)                Path to the payloads folder

        Returns:
            len                         (int)                   Number of payloads in Fuzzer object
        '''
        try:
            payload_files = os.listdir(payload_dir)
        except FileNotFoundError:
            termcolor.cprint(f"[-] Payload folder '{payload_dir}' not found!", self.error_color, file=sys.stderr)
            return len(self.payloads)

        for payload_file in payload_files:

            # If the source file is the one-liners.txt file, simply launch each line as a separate payload
            if payload_file == "oneliners.txt":

                with open(f'{payload_dir}/{payload_file}', 'rb') as f:

                    payload = f.readlines()
                    for line in payload:

                        new_payload = Payload(line)
                        self.payloads.append(new_payload)

            else:
                
                with open(f'{payload_dir}/{payload_file}', 'rb') as f:
                    payload = f.read()
                    new_payload = Payload(payload)
                    self.payloads.append(new_payload)

        return len(self.payloads)


    def add_parameter(self, key, value):
        '''
        Just a helper function that adds a key-value pair to the parameter dicitonary.

        Parameters:
            key                     (bytes)                 Parameter key
            value                   (bytes)                 Parameter value

        Returns:
            len                     (int)                   Number of entries in parameter dict
        '''
        self.parameter_dict[key] = value
        return len(self.parameter_dict)

            
    def fuzz(self, payload):
        '''
        Takes a payload and sends it to the targeted host.
        
        Parameters:
            payload                 (Payload)                   Payload to send

        Returns:
            payload                 (Payload)                   Send payload    
        '''
        sock = self.connect()
        payload.prepare(self.parameter_dict)
        payload.send(sock, self.server_timeout)
        if self.verbose:
            self.print_summary(payload)
        if sock:
            sock.close()
        return payload


    def start_fuzzing(self):
        '''
        This function is just a wrapper around the fuzz() method. It uses ThreadPoolExecutor to spawn
        several threads, fuzzing different payloads.

        Paramaters:
            None

        Returns:
            None
        '''
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as executor:
            executor.map(self.fuzz, self.payloads)


    def get_results(self):
        '''
        This function can be used to obtain the results from the fuzzed payloads. It iterates over each
        payload object in {self.payloads} and prints the summary on it into a variable. This variable is 
        then returned. If the return value ist just printed, one gets the same output as using verbose=True.

        Paramaters:
            None

        Returns:
            output                  (string)                    Summary of all payload objects
        '''
        sys.stdout = output = StringIO()
        payload_list = self.payloads

        # If no_failed is on, we need to filter unsuccessful payloads
        if self.no_failed:
            payload_list = list(filter(lambda x: x.success, payload_list))

        for payload in payload_list:
            self.print_summary(payload)
        sys.stdout = sys.__stdout__
        return output.getvalue()


    def get_results_json(self):
        '''
        Returns the summary of all payloads as json. The corresponding keys can be looked up in the to_dict
        method of the Payload class.

        Parameters:
            None

        Returns:
            json                    (string)                    Json formatted payload summary
        '''
        result_list = []
        payload_list = self.payloads

        # If no_failed is on, we need to filter unsuccessful payloads
        if self.no_failed:
            payload_list = list(filter(lambda x: x.success, payload_list))

        for payload in payload_list:
            payload_dict = payload.to_dict()
            try:
                payload_dict['data'] = payload_dict['data'].decode('utf-8')
            except:
                payload_dict['data'] = bytes_to_hex(payload_dict['data'])
            result_list.append(payload_dict)
        return json.dumps(result_list)


    def print_summary(self, payload):
        '''
        Prints a summary of the current payload. The summary contains the payload data that was sent as well
        as the corresponding server response, if one was captured. If not, the error reason is displayed.
        This was actually part of the payload class, but was moved to the Fuzzer class to allow easy passing
        color schemes.

        Paramaters:
            payload                (bool)                      payload to print

        Returns:
            None
        '''
        # The payload data is still a bytes object. We try to convert it to utf-8 or display it as hex...
        try:
            data = payload.data.decode('utf-8')
            data = data.strip()
        except:
            data = bytes_to_hex(payload.data)

        # To avoid problems with threading and concurrent printing, we print everything to a variable and
        # print the final result with flush=True. This should keep everything in order
        sys.stdout = output = StringIO()

        if payload.success:
            termcolor.cprint('[+] Payload:', self.info_color)
            termcolor.cprint(apply_format(data, indent=1), self.payload_color)
            termcolor.cprint('[+] Response:', self.info_color)
            termcolor.cprint(apply_format(payload.result, indent=1), self.success_color)

        elif not self.no_failed:
            termcolor.cprint('[+] Payload:', self.info_color)
            termcolor.cprint(apply_format(data, indent=1), self.payload_color)
            termcolor.cprint(f'[-] Failed: {payload.reason}', self.error_color)

        sys.stdout = sys.__stdout__
        print(output.getvalue(), flush=True, end='')


class Payload:
    '''
    The payload class is a simple wrapper about a bytes object, representing a single payload. It is used
    to store payload related information, like success or the resulting response by the server.
    '''


    def __init__(self, data):
        '''
        Creates a new payload object. The {self.success} is always set to False and {self.reason} and
        {self.result} are always initialized empty.

        Paramaters:
            data                    (bytes)                     Actual payload data

        Returns:
            Payload                 (Payload)                   New generated payload object
        '''
        self.success = False
        self.data = data
        self.reason = ''
        self.result = ''


    def to_dict(self):
        '''
        Converts the payload object into a dictionary and returns it.

        Paramaters:
            None

        Returns:
            None
        '''
        return {
                 'success' : self.success,
                 'reason' : self.reason,
                 'data' : self.data,
                 'result' : self.result,
               }


    def prepare(self, parameter_dict):
        '''
        This method is used to replace certain keys inside of a payload. E.g. a HTTP request payload
        does require the IP address of the target inside the HTTP Host header.

        Parameters:
            parameter_dict              (dict)                  Key-Value pairs for replacement

        Returns:
            len                         (int)                   Length of the paramater dictionary
        '''
        for key,value in parameter_dict.items():
            self.data = self.data.replace(key, value)
        return len(parameter_dict)


    def send(self, sock, timeout=2):
        '''
        This method takes a socket object and sends the payload data over this socket. It also sets the
        value of {self.result} or {self.reason}, depending on the servers response.

        Paramaters:
            sock                        (socket)                Socket used for sending the payload
            timeout                     (int)                   Number of seconds to wait fot a response

        Returns:
            None
        '''
        sock.sendall(self.data)
        ready = select.select([sock], [], [], timeout)

        if ready[0]:

            # If data was received, we store it in the result variable of the payload
            try: 
                data = sock.recv(1024)
                try:
                    self.result = data.decode('utf-8')
                except:
                    self.result = bytes_to_hex(data)
                self.result = self.result.strip()
                self.success = True

            # Some servers will reset the connection after receiving wrong input.
            # We store this information in the reason variable of the payload.
            except ConnectionResetError:
                self.reason = "Connection reset by server."

        else:

            # If we reach this point, no response was received and we simply set
            # the reason variable to timeout
            self.reason = "Server Timeout."

__author__ = "Pete Allinson, PGA Embedded Systems Ltd.  pete@pgaembeddedsystems.co.uk"
__copyright__ = "Copyright 2016 Kibron Inc., All Rights Reserved"

"""
Remote Server Client.
Classes and constants for communicating with the trough
"""

import socket
import threading


# Indices to fields in the measurement data returned by 'GetData'
uTStatus = 0
uTVoltage = 1
uTPressure = 2
uTTension = 3
uTArea = 4
uTAreaPerChains = 5
uTTemperature1 = 6
uTTemperature2 = 7
uTPotential = 8
uTRadioactivity = 9
uTAux1 = 10
uTAux2 = 11
uTAux3 = 12
uTPosition = 13
uTSpeed = 14
uTCompressionRate = 15
uTTime = 16
uTDipPosition = 17
uTDipSpeed = 18
uTSteppingStatus = 19
uTDeviceStatus = 20
uTLastError = 21

# Device status codes
# How to interpret the value at index 20 in the GetData result
DstIdle = 0
DstTensiometer = 1
DstCompressionIsotherm = 2
DstConstantArea = 3
DstConstantPressure = 4
DstManual = 5
DstTargetReached = 6
DstBarrierInit = 7
DstBarrierInitDone = 8


def connect(host, port):
    sock = socket.create_connection((host, port))
    prologue = sock.recv(1024).decode()
    # TODO check that the prologue makes sense
    print(prologue)
    return sock


def dst_to_str(i):
    """Convert device status value to string"""
    dst_strs = [
        "Idle",
        "Tensiometer",
        "CompressionIsotherm",
        "ConstantArea",
        "ConstantPressure",
        "Manual",
        "TargetReached",
        "BarrierInit",
        "BarrierInitDone",
    ]
    try:
        return dst_strs[i]
    except IndexError:
        return "Invalid device status value: %s" % str(i)


# Barrier direction codes
# How to interpret the value at index 19 in the GetData result
StpCompress = 1
StpRelax = -1
StpStop = 0

# Trough Error codes
# How to interpret the value at index 21 in the GetData result
# and the value at index 0 in any command result
NoError = 0  # No error
EBusy = -1  # Device is busy, executing a command *)
ECommandNotImplemented = -2  # Command not implemented
ECommunicationFailure = -3  # Device did not send reply in time
EConnectFailure = -4  # Can't connect to device
EConnected = -5  # Communication port is active
EComPortNotSet = -6  # Com port number is not set
ENotConnected = -7  # Not connected to communication port
EComPortCfgSaveFailure = -8  # Could not save communication port information
ENoServerConnection = -9  # COM server not connected.

# Trough measurement modes
# The parameter to the NewMeasureMode command
MeIdle = 0
MeTensiometer = 1
MeCompressionIsotherm = 2
MeConstantArea = 3
MeConstantPressure = 4
MeManual = 5
MeRadioAct = 6
MeHysteresis = 7


###############################################################################
class TroughError(Exception):
    """Exception raised when a trough command (call, get, set, ctrl)
    results in an error"""

    pass


###############################################################################
class Trough(object):
    """Communications with trough across network"""

    # --------------------------------------------------------------------------
    def __init__(self, sock):
        self.sock = sock
        # Lock to serialize access from multiple threads
        self.lock = threading.Lock()
        self.line_end = b"\n"

    # --------------------------------------------------------------------------
    def _readline(self):
        """Read a line of text from the socket"""
        s = b""
        while True:
            rdata = self.sock.recv(1024)
            if len(rdata) == 0:
                # Connection closed
                return
            s += rdata
            # Check for complete line
            if s.endswith(self.line_end):
                break
        return s.decode()

    # --------------------------------------------------------------------------
    def _parse_response(self, response):
        """Parse response to trough command.  It's expected to have the form
        'OK: [ <status-code> [ <result-1> <result-2> ... ] ]'
        Check the response begins with 'OK:'.
        Return a list containing the status-code and ant result fields.
        Raise TroughError exception if the response indicates an error.
        """
        try:
            (ok, body) = response.split(":", 1)
        except ValueError:
            # missing ':'
            raise TroughError(response)
        if not ok.startswith("OK"):
            raise TroughError(response)
        result = body.split(None)  # split on whitespace, discarding empty strings

        return result

    # --------------------------------------------------------------------------
    def _map_str_to_number(self, str_vals):
        def str_to_number(s):
            try:
                # See if 's' can be converted to a number
                if "." in s:
                    return float(s)
                else:
                    return int(s)
            except ValueError:
                # Now try a boolean
                bools = {"false": False, "true": True}
                try:
                    b = bools[s.lower()]
                    return b
                except KeyError:
                    # Give up, return the original string
                    return s

        return tuple(map(str_to_number, str_vals))

    # --------------------------------------------------------------------------
    def call(self, *args):
        """Call a trough method, with parameters"""
        method = args[0]
        args = args[1:]
        cmd = " ".join([method] + [str(arg) for arg in args])
        with self.lock:
            self.sock.send(("call : " + cmd + "\n").encode())
            response = self._readline()

        # Split the response into fields
        result = self._parse_response(response)

        # Convert strings to numbers/bools where possible
        result = self._map_str_to_number(result)

        if method == "GetData":
            # Keep the <status-code>.  It is the count of pending messages
            return result
        elif method == "DeviceIdentification":
            # Keep the <status-code>.  It is actually part of the device identification
            return result
        elif len(result) == 0:
            # Empty result
            return None
        elif len(result) == 1:
            # Single return value, return that
            return result[0]
        elif len(result) == 2:
            # Drop the <status-code>, return single result
            return result[1]
        else:
            # Drop the <status-code>, return the remaining list
            return result[1:]

    # --------------------------------------------------------------------------
    def get(self, prop):
        """Get a trough property"""
        with self.lock:
            self.sock.send(("get : " + prop + "\n").encode())
            response = self._readline()

        # Split the response into fields
        result = self._parse_response(response)

        # Convert strings to numbers/bools where possible
        result = self._map_str_to_number(result)

        # There should be only one item in the result list
        if len(result) != 1:
            raise TroughError(
                "Property '%s' returned unexpected results:\n%s" % (prop, result)
            )

        return result[0]

    # --------------------------------------------------------------------------
    def set(self, prop, value):
        """Set a trough property"""
        cmd = "set : %s %s\n" % (prop, str(value))
        with self.lock:
            self.sock.send(cmd.encode())
            response = self._readline()

        # Split the response into fields
        result = self._parse_response(response)

        # Convert strings to numbers/bools where possible
        result = self._map_str_to_number(result)

        # The result list should be empty
        if len(result) != 0:
            raise TroughError(
                "Property '%s' returned unexpected results:\n%s" % (prop, result)
            )

        return result

    # --------------------------------------------------------------------------
    def ctrl(self, ctrl, value):
        """Update a 'control' value in the server"""
        cmd = "ctrl : %s %s\n" % (ctrl, str(value))
        with self.lock:
            self.sock.send(cmd.encode())
            response = self._readline()

        # Split the response into fields
        result = self._parse_response(response)

        # Convert strings to numbers/bools where possible
        result = self._map_str_to_number(result)

        return result


###############################################################################
class PollDataError(Exception):
    """Error occurred while polling GetData."""

    def __init__(self, msg, data=[]):
        """
        msg - the message from GetData
        data - measurement samples read in this polling cycle (if any)
        """
        Exception.__init__(msg)
        self.data = data


###############################################################################
class PollData(threading.Thread):
    """Periodically poll the trough for measurement data
    by naking GetData method calls on the trough.
    The response to the GetData call has the form:
        <n> <list of measurement data items> '\n'
    where <n> may be
        0 - measurement not in progress, or no new measurement data.
            In either case the measurement data items are the values most
            recently read from the trough.
        >0 - measurement in progress, and this is new measurement data.
            GetData will be called until <n> is 0, indicating all the
            measurement data has been read.
        <0 - negative value indicates error.  The thread sets an error flag
            and stops polling until the error flag is cleared.
    After calling GetData to retrieve measurement data, datacb is called
    with the measurement data passed in as a list of lists.
    """

    # --------------------------------------------------------------------------
    def __init__(self, trough, interval=0.25, datacb=None, errcb=None):
        """
        trough - instance of Trough, for communicating with trough
        interval - polling interval (seconds).  A value of None will
            suspend polling
        datacb - function called at the end of each poll cycle
        errcb - function to call if GetData reports an error
        datacb - function to call with measurement data
        """
        threading.Thread.__init__(self)

        self.trough = trough
        self._interval = interval
        self.datacb = datacb
        self.errcb = errcb

        self._event = threading.Event()
        self._error = False
        self._quit = False

    # --------------------------------------------------------------------------
    def run(self):
        while True:
            if not self._error:
                try:
                    data = self.get_data()
                    if self.datacb:
                        self.datacb(data)
                except PollDataError as err:
                    self._error = True
                    if self.errcb:
                        self.errorcb(str(err), err.data)

            self._event.wait(self.interval)
            if self._quit:
                break

    # --------------------------------------------------------------------------
    @property
    def interval(self):
        """return the current poll interval"""
        return self._interval

    # --------------------------------------------------------------------------
    @interval.setter
    def interval(self, interval):
        """Set the poll interval.  Wake the thread if the new interval is
        shorter than the current poll interval.  This ensures a timely
        response if the interval is changed from a long time to a
        short time."""
        if interval < self._interval:
            self._event.set()

    # --------------------------------------------------------------------------
    @property
    def error(self):
        return self._error

    # --------------------------------------------------------------------------
    @error.setter
    def error(self, value):
        self._error = value
        self._event.set()

    # --------------------------------------------------------------------------
    def quit(self):
        """Terminate the PollData task."""
        self._quit = True
        self._event.set()
        self.join()

    # --------------------------------------------------------------------------
    def get_data(self):
        data = []
        while True:
            try:
                vals = self.trough.call("GetData")
                # Expecting the result to be of the form
                #   '<status-code> <value-1> <value-2> ... <value-n>
                # vals is list comprising staus code followed by list of values
                data.append(vals)
                count = vals[0]
                if count == 0:
                    return data
            except TroughError as err:
                raise PollDataError(str(err), data)

from __future__ import print_function

__author__ = 'Pete Allinson, PGA Embedded Systems Ltd.  pete@pgaembeddedsystems.co.uk'
__copyright__ = 'Copyright 2016 Kibron Inc., All Rights Reserved'

"""
Simple client to exercise the MicroTrough remote server
Tested with Python 2.7 on Windows 8.1
"""

import sys
import socket
import threading
import argparse
import time
import csv
import os

# Communications with the trough
import mtx_client as mtx

# Default server address/port
HOST, PORT = "localhost", 9898

def get_options():
    def int_ge_0(s):
        try:
            i = int(s)
            if i < 0:
                raise ValueError("Port number must be greater than zero")
            return i
        except ValueError as err:
            raise argparse.ArgumentTypeError("Must be a non-negative integer")
    parser = argparse.ArgumentParser(description='MicroTrough Remote Access Client')
    parser.add_argument("host", nargs="?", action="store",
                        default=HOST,
                        type=str,
                        help="server host address")
    parser.add_argument("port", nargs="?", action="store",
                        default=PORT,
                        type=int_ge_0,
                        help="server host port")
    args = parser.parse_args()

    return args

args = get_options()

# Update server address/port
HOST, PORT = args.host, args.port


# Connect to server, read prologue
try:
    sock = socket.create_connection( (HOST, PORT) )
except socket.error as err:
    print("Failed to connect to server:\n", str(err) )
    sys.exit(1)
prologue = sock.recv(1024)
print(prologue)


#
# Connect to the trough interface
#
trough = mtx.Trough(sock)


class TroughDataHelper(object):
    """Utility class for handling trough data:

    Save measurement data to file.

    Timestamps in the measurement are in terms of elapsed time since the
    start of the measurement, so we support a time_offset property which will be
    added to all timestamps.

    Allow file annotation.

    Keep latest data available for anything wanting it"""
    def __init__(self, fname):
        self.fh = open(fname, "w")
        self.writer = csv.writer(self.fh, lineterminator='\n')
        self.curr_data = None

        self.annotation_prefix = '# '
        self.annotation_suffix = '\n'

        self._time_offset = 0           # Added to all uTTime values
        self._flock = threading.RLock() # Protect access to the file
                                        # Reentrant Lock so it can be acquired recursively
                                        # in the same thread

    def new_data(self, data):
        """Callback from the PollData thread
        data - list of measurements.  Each measurement is a list of data points
                sampled by the trough at the same time"""
        with self._flock:
            for measurement in data:
                measurement[mtx.uTTime] += self._time_offset
                count = measurement[0]
                if count > 0:
                    self.writer.writerow( measurement )

        self.curr_data = data[-1]

    def flush(self):
        """Flush measurement data filehandle"""
        self.fh.flush()

    def close(self):
        """Close measurement data filehandle"""
        self.fh.close()

    @property
    def time_offset(self):
        """Value added to all timestamps"""
        return self._time_offset

    @time_offset.setter
    def time_offset(self, secs):
        """Value added to all timestamps"""
        with self._flock:
            self._time_offset = secs
            self.annotate("Time Offset set to {}", secs)

    def annotate(self, format_string, *args, **kwargs):
        """Annotate the measurement file"""
        s = format_string.format(*args, **kwargs)
        with self._flock:
            self.fh.write(self.annotation_prefix + s + self.annotation_suffix)


def error_callback(errstr, data):
    """Will be called from PollData thread if there is an error.
    errstr - error message
    data - data read from the trough immediately preceeding the error"""
    print(errstr)


#
#
# Create a measurement file in the user home directory
home = os.path.expanduser("~")
measurement_file = os.path.join(home, 'kibron', 'measurements', 'data_file.csv')
try:
    os.makedirs( os.path.dirname(measurement_file) )
except os.error:
    # Assume error due to path already existing
    pass

trough_data = TroughDataHelper( measurement_file )


# Create and start PollData thread
# This will run in the background, collecting measurement data from the trough.
poll_data = mtx.PollData(trough, interval=1.0, datacb=trough_data.new_data, errcb=error_callback)
poll_data.start()


# Verbose output
try:
    #trough.ctrl('verbosity', 3)
    trough.ctrl('verbosity', 1)
except mtx.TroughError as err:
    print( err )
    poll_data.quit()
    sys.exit(1)


# Raise this exception to bypass a test case
class Skip(Exception): pass

skip = False
#skip = True

# Do a few simple commands
#
try:

    # This should return (quickly) provided the trough is connected and powered
    result = trough.call('DeviceIdentification')
    print(result)

    trough.call('NewMeasureMode', mtx.MeIdle)
except mtx.TroughError as err:
    print( str(err) )
    poll_data.quit()
    sys.exit(1)

###############################################################################
# Open barriers to full extent.
#

# Make sure data is being received from the trough
time.sleep(2)
if trough_data.curr_data is None:
    print("We don't seem to be receiving data from the trough.")
    poll_data.quit()
    sys.exit(1)

try:
    if skip:
        raise Skip()

    print ("Opening barriers ...")

    # Start barriers separating, quick as we can
    max_speed = trough.call('GetMaxBarrierSpeed')
    trough.call('SetBarrierSpeed', max_speed)

    trough.call('StepRelax')
    while True:
        # Polling at 1 second intervals, so allow a couple of seconds for
        # cached barrier status to be updated
        time.sleep(2)
        data = trough_data.curr_data
        if data[mtx.uTSteppingStatus] == mtx.StpStop:
            # Barriers stop automatically when they reach maximum extent
            break

    max_area = trough_data.curr_data[mtx.uTArea]
    print("Barriers at maximum extent, area is", str(max_area))


    print("... Done")

except mtx.TroughError as err:
    print( str(err) )
    poll_data.quit()
    sys.exit(1)

except Skip:
    pass


###############################################################################
# Example of Manual measurement mode,
# Compress barriers while accumulating data,
# Barriers moving at quarter max speed

trough_data.annotate("Starting Manual measurement.")

skip = True

try:
    if skip:
        raise Skip()

    print("Compressing barriers, gathering measurement data ...")

    # Tell the trough to produce measurement samples at 1 second intervals
    trough.call('SetStoreInterval', 1.0)

    trough.call('SetBarrierSpeed', max_speed / 4)

    trough.call('NewMeasureMode', mtx.MeManual)

    # Set time_offset in the measurement file when starting measurement
    now = time.time()               # seconds since the epoch
    trough_data.time_offset = now   # Will be added to all timestamps
    trough.call('StartMeasure')

    trough.call('StepCompress')

    # Wait until area is three-quarters maximum
    while True:
        data = trough_data.curr_data
        area = data[mtx.uTArea]
        print( "Area is:", area )
        if area < max_area * 0.75:
            break
        time.sleep(1)

    trough.call('StepStop')

    trough.call('StopMeasure')

    trough_data.annotate("Done.")
    print("... Done")

except mtx.TroughError as err:
    print( str(err) )
    poll_data.quit()
    sys.exit(1)

except Skip:
    pass


###############################################################################
# Example of Constant Area measurement mode for a series of areas.
#

skip = False

try:
    if skip:
        raise Skip()

    msg = "Test Constant Area measurement mode ..."
    print(msg)
    trough_data.annotate(msg)

    # Tell the trough to produce measurement samples at 1 second intervals
    trough.call('SetStoreInterval', 1.0)

    trough.call('SetBarrierSpeed', max_speed)

    trough.call('NewMeasureMode', mtx.MeConstantArea)

    # Loop over these areas, spending 1 minute at each
    areas_to_test = [
            12000, 10000, 8000, 6000, 4000      # mm^2
            ]

    # Setting target area in mm^2 is awkward because the trough API call
    # wants a parameter in Ang.^2-per-chain.
    # So we need to calculate a scaling factor:
    max_area_per_chains = trough.call('MaxAreaPerChains')
    scale = max_area_per_chains / max_area

    for area in areas_to_test:

        area_per_chains = area * scale
        trough.call('SetTargetAreaPerChains', area_per_chains)

        msg = "Moving to target area ..."
        print(msg)
        trough_data.annotate(msg)

        # Set time_offset in the measurement file when starting measurement
        now = time.time()               # seconds since the epoch
        trough_data.time_offset = now   # Will be added to all timestamps
        trough.call('StartMeasure')

        # Wait until target area is reached
        while True:
            time.sleep(2)

            data = trough_data.curr_data
            area = data[mtx.uTArea]
            dst = data[mtx.uTDeviceStatus]
            dststr = mtx.dst_to_str( dst )

            print( "Area is: {}, Dst is: {}".format(area, dststr) )
            if dst == mtx.DstTargetReached:
                break

        msg = "Waiting ..."
        print(msg)
        trough_data.annotate(msg)

        # Issue another StartMeasure (timestamps stopped advancing when the 
        # target area area was reached) 
        now = time.time()               # seconds since the epoch
        trough_data.time_offset = now   # Will be added to all timestamps
        trough.call('StartMeasure')

        # Wait for 1 minute, gathering measurement data
        time.sleep(60)

        trough.call('StopMeasure')

    msg = "Done"
    print(msg)
    trough_data.annotate(msg)


except mtx.TroughError as err:
    print( str(err) )
    poll_data.quit()
    sys.exit(1)

except Skip:
    pass



###############################################################################
# Exercise a few trough commands

# Properties:
try:
    # Note - these are unlikely to fail because they return data cached in the
    # trough interface software.  They don't go to the trough interface hardware
    current_speed = trough.get('CurrentSpeed')
    current_position = trough.get('CurrentPosition')
    compression_rate = trough.get('CompressionRate')
    command_status = trough.get('CommandStatus')
    com_port = trough.get('ComPort')

    print("A few properties:")
    print("Current Speed:   ", current_speed)
    print("Current Position:", current_position)
    print("Compression Rate:", compression_rate)
    print("Command Status:  ", mtx.dst_to_str( command_status) )
    print("Com Port:        ", com_port)

except mtx.TroughError as err:
    print( str(err) )
    poll_data.quit()
    sys.exit(1)

# Methods
try:
    pass

except mtx.TroughError as err:
    print( str(err) )
    poll_data.quit()
    sys.exit(1)


# 
# Quit the PollData thread, close the data file
poll_data.quit()
trough_data.close()


# All done
sock.close()
sys.exit(0)

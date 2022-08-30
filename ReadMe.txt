README
======

This package is part of the Kibron FilmWareX software range and contains a
Remote Access Server for the Kibron Microtrough.  The Server runs alongside the
FilmWareX software, sharing access to the trough, and can be used by client
software to control measurements made with the trough.

Copyright 2016 Kibron Inc., All Rights Reserved

Client software uses BSD Sockets to communicate with the Server.  Communication
is in the form of string-based commands and responses.  The client formats a
string containing a command, plus any parameters, and sends it to the Server.
The Server sends the command to the trough interface software and thence to the
trough.  The Server formats the response from the trough, along with any result
data, into a string which is returned to the client software.

This package includes a simple client script illustraing control of the trough
and collection of measurement data.  The script is written in Python 2.7 but it
keeps the use of Python features to a minimum so it should be straightforward to
understand and translate to other programming languages.

This package also includes a description of the string format for commands and
responses, plus a description of the available commands.

The Remote Access Server runs alongside FilmWareX but is not integrated with it.
The intention is that FilmWareX be used for:
    System Control - establishing communications with the trough hardware
    Trough Configuration - downloading dimensional and calibration data to the
        trough
and then client software can take over to carry out
    Measurement Configuration
    Measurement Control
For this reason the documentation does not describe commands associated with
System Control and Trough Configuration.  Future releases of FilmWareX may
integrate the Server software, at which time the client software may be able to
perform System Control and Trough Configuration functions.


Installation
============
Remote Access Server
--------------------
Copy the installation file, KbnMtxRas_inst.exe, to the target PC (where
FilmWareX is installed.)

Run the installation file and follow the on-screen instructions.

By default the Server software will be installed to
C:\Program Files (x86)\Kibron\MicroTrough Remote Access Server

During installation you will have the option of copying the sample client
software and documentation to the same directory.

Sample Client and Documentation
-------------------------------
Copy the 'scripts' and the 'docs' folders to the client machine


Starting the Remote Access Server
=================================
Make sure FilmWareX has been started.  This will start the trough interface
software and initialise the trough hardware.

Using Windows Task Manager, verify that one instance of
    "Kibron communication component for UTrough"
is running as a background process.  (The .exe is "KbnMTIO30.exe")
(Depending on Windows OS you may need to select "More details" for Task Manager
to display background processes.)

Start the Remote Access Server.  This can be done by double-clicking on the
program name in a Windows Explorer:
  "C:\Program Files (x86)\Kibron\MicroTrough Remote Access Server\KbnMtxRas.exe"
or from a command line prompt:
  "C:\Program Files (x86)\Kibron\MicroTrough Remote Access Server>.\KbnMtxRas.exe"

If the Server starts successfully it will be running in its own command window
with the output:
    "Server listening on port 9898"

The Server defaults to listening for connections on port 9898.  A command-line
switch starts the server listening on a different port:
    .\KbnMtxRas.exe -p 9897

When the Server is started, check Task Manager and confirm there is still one
instance of
    "Kibron communication component for UTrough"
running as a background process.  If there are two instances then the Server
is not running with the correct permissions.  For technical reasons FilmWareX
3.62 must be run in Windows XP SP3 compatibility mode, and the Remote Access
Server must have "Run As Administrator" compatibility.  Future releases of the
software will address these limitations.

If the selected port is not available then the Remote Access Server will exit
immediately with an error message.

Each instance of the Server allows only one client at a time.  Further client
connections will be rejected.  It is not anticipated that this will be a
problem, but if it is then multiple instances of the Server can be run (on
different ports.)  Future releases of the software will address this limitation.


Testing the Remote Access Server
================================
The simplest test is to use telnet to make a connection to the server, and then
to issue some commands to the trough.  This should be done first from the same
PC as the Server and then from a remote computer where the client software will
run.

Depending on the version of Windows the telnet client software may need to be
installed.  This can be done from Control Panel -> Programs and Features
-> Turn Windows features on or off.  Scroll down to Telnet Client, click in the
adjacent box and then click OK.

Start the telnet client program and open a connection to the Server:
    Microsoft Telnet> o 127.0.0.1 9898
    Connecting To 127.0.0.1...

The client should display a connect message from the Server:

    MicroTrough Remote Server
                             Version: 0.1

The default line-ending is LF, which is looks funny on Windows Telnet Client.
Fix the line endings by typing the following command:

                                         ctrl : line_ending crlf
    OK:

'ctrl' commands control the operation of the server.  The 'line_ending' command
takes a single parameter and determine what the Server uses to terminate
responses.  The options are 'lf' (default), 'cr', 'lfcr', 'crlf'.

Now send a trough command:

    call : GetData
    OK: 0 -4596.47753906 597895.75 -597822.9375 5861.60449219 6.55939149857 999.0 99
    9.0 -2499.61108398 0.0 0.388920336962 0.0 0.0 22813.0 70.125 4.62990283966 0.0 1
    0.0 5.0 0 0 0

'call' commands make an API function call on the trough interface software.  The
'GetData' command returns the most recent measurement sample received from the
trough.

The 'OK:' prefix indicates the command was successfully processed.  The rest of
the data (which is actually all one line) is the result of the GetData command.

The RAS_INTERFACE.txt document describes the GetData command.

If a command is not successfully processed then the response string will
comprise an 'ERROR:' prefix followed by a description of the error.  For example

    call : NotACommand
    ERROR: CallError(-100, 'Unrecognised command name', 'KBNuTAXCtrl.KBNuTAX.NotACom
    mand')


Halting the Server
==================
Type a Ctrl-C character into the server's command window.  The server will exit
when all clients have disconnected.


Running the Sample Script
=========================
The sample script was written for Python 2.7 and has been tested on a
Windows 8.1 platform.

Linux platforms often come with Python already installed.
For Windows, Python can be downloaded from the Python.org website:
    https://www.python.org/downloads/

The sample script comprises two modules:
    mtx_client.py
        This is a collection of classes to format command strings, send them to
        the Server, and parse the response string.
        It also defines a background thread that will regularly poll the Server
        with a GetData command to retrieve measurement data
    sample_script.py
        Contains helper classes to handle measurement data.
        Sends sequences of commands to the Server to put the trough through
        a few exercises.

To run the script, open a command line window, cd to the
directory containing the two modules and type the command
    python sample_script.py

If the Server is on a different host, or is not listening on the default port:
    python sample_script.py host=<ip_address> port=<port>
Defaults are:
    host=127.0.0.1
    port=9898

The script does use Python 'exceptions' (for error handling) and 'contexts' (for
locking access to files and sockets) but has otherwise been written with a
minimum of Python features, so it should be straightforward to translate to
other programming languages.

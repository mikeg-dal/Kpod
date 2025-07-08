This allows the Elecraft Kpod to be plugged directly into the MAC OS USB port.  Once that is done you can control K4 Control Software by setting up the KPOD as a MIDI Controller and mapping the VFO and buttons whatever you like inside K4Control.
Pre-Requisites.

On Mac OS Open your Midi Application

Applications->Utilities-Audio MIDI Setup.App

At the Top look for Window -> Show MIDI Studio and select it.

In the window that opens Select IAC Driver and open it.

Make sure the checkbox for Device is Online is selected.

Close out of the windows.

Python Pre-requisites

Create your Python Environment

 python3 -m venv ~/kpodenv

Activate your python environment

source ~/kpodenv/bin/activate

Install pip requirements(one time only)
------------- ------------
hid           1.0.8
hidapi        0.14.0.post4
pip           24.2
python-rtmidi 1.5.8
setuptools    80.9.0




Still in progress getting the pre-req.  Home brew also used to install HIDAPI.


Video showing setup.

https://youtu.be/CvL_pqLJApE

This allows the Elecraft Kpod to be plugged directly into the MAC OS USB port.  Once that is done you can control K4 Control Software by setting up the KPOD as a MIDI Controller and mapping the VFO and buttons whatever you like inside K4Control.
Pre-Requisites.

On Mac OS Open your Midi Application

Applications->Utilities-Audio MIDI Setup.App

At the Top look for Window -> Show MIDI Studio and select it.

In the window that opens Select IAC Driver and open it.

Make sure the checkbox for Device is Online is selected.

Close out of the windows.


Unzip the application, and place it in your apps folder.  run it and it should ask for permissions since I didnt sign it with my dev account.  

You close it by force quit for now since I dont have a menu system.  The KPOD has to be plugged in before running it.  To verify its running you can run ps -ax | grep KPOD.  you should see a process ID with the location of the KPOD-Bridge.

I provided the pre-made app file in a zip folder, this was built using pyinstaller to create the app.  The source is listed here as well.

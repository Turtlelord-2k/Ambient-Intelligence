import serial 
import time
import datetime
import os
import math
import json
import sys

# Logger
import logging
log = logging.getLogger(__name__)

#Local Imports
from parseFrame import parseStandardFrame

UART_MAGIC_WORD = bytearray(b'\x02\x01\x04\x03\x06\x05\x08\x07')

class UARTParser():
    def __init__(self,type):
        # Set this option to 1 to save UART output from the radar device
        self.saveBinary = 0
        self.replay = 0
        self.binData = bytearray(0)
        self.uartCounter = 0
        self.framesPerFile = 100
        self.first_file = True
        self.filepath = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
        self.parserType = type
        self.dataCom = None
        self.isLowPowerDevice = False
        self.cfg = ""
        self.demo = ""
        self.device = "xWR6843"
        self.frames = [] # TODO this needs to be reset if connection is reset
        
        # Data storage
        self.now_time = datetime.datetime.now().strftime('%Y%m%d-%H%M')


    def connectComPorts(self, cliCom, dataCom):
        self.cliCom = serial.Serial(cliCom, 115200, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.6)
        self.dataCom = serial.Serial(dataCom, 921600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=0.6)
        self.dataCom.reset_output_buffer()
        log.info('Connected')


    def setSaveBinary(self, saveBinary = 1):
        self.saveBinary = saveBinary

    # This function is always called - first read the UART, then call a function to parse the specific demo output
    # This will return 1 frame of data. This must be called for each frame of data that is expected. It will return a dict containing all output info
    # Point Cloud and Target structure are liable to change based on the lab. Output is always cartesian.
    # DoubleCOMPort means this function refers to the xWRx843 family of devices.
    def readAndParseUartDoubleCOMPort(self):
        
        self.fail = 0
        if (self.replay):
            return self.replayHist()

        data = {'cfg': self.cfg, 'demo': self.demo, 'device': self.device}
    
        # Find magic word, and therefore the start of the frame
        index = 0
        magicByte = self.dataCom.read(1)
        frameData = bytearray(b'')
        while (1):
            # If the device doesn't transmit any data, the COMPort read function will eventually timeout
            # Which means magicByte will hold no data, and the call to magicByte[0] will produce an error
            # This check ensures we can give a meaningful error
            if (len(magicByte) < 1):
                log.error("ERROR: No data detected on COM Port, read timed out")
                log.error("\tBe sure that the device is in the proper mode, and that the cfg you are sending is valid")
                magicByte = self.dataCom.read(1)
                
            # Found matching byte
            elif (magicByte[0] == UART_MAGIC_WORD[index]):
                index += 1
                frameData.append(magicByte[0])
                if (index == 8): # Found the full magic word
                    break
                magicByte = self.dataCom.read(1)
                
            else:
                # When you fail, you need to compare your byte against that byte (ie the 4th) AS WELL AS compare it to the first byte of sequence
                # Therefore, we should only read a new byte if we are sure the current byte does not match the 1st byte of the magic word sequence
                if (index == 0): 
                    magicByte = self.dataCom.read(1)
                index = 0 # Reset index
                frameData = bytearray(b'') # Reset current frame data
        
        # Read in version from the header
        versionBytes = self.dataCom.read(4)
        
        frameData += bytearray(versionBytes)

        # Read in length from header
        lengthBytes = self.dataCom.read(4)
        frameData += bytearray(lengthBytes)
        frameLength = int.from_bytes(lengthBytes, byteorder='little')
        
        # Subtract bytes that have already been read, IE magic word, version, and length
        # This ensures that we only read the part of the frame in that we are lacking
        frameLength -= 16 

        # Read in rest of the frame
        frameData += bytearray(self.dataCom.read(frameLength))

        # frameData now contains an entire frame, send it to parser
        if (self.parserType == "DoubleCOMPort"):
            outputDict = parseStandardFrame(frameData)
        else:
            log.error('FAILURE: Bad parserType')

        # If save binary is enabled
        if(self.saveBinary == 1):
            # Save data every framesPerFile frames
            self.uartCounter += 1

            # uncomment below to save bin data in Matlab-friendly format
            # self.binData += frameData
            # if (self.uartCounter % self.framesPerFile == 0):
            #     # First file requires the path to be set up
            #     if(self.first_file is True): 
            #         if(os.path.exists('binData/') == False):
            #             # Note that this will create the folder in the caller's path, not necessarily in the Industrial Viz Folder                        
            #             os.mkdir('binData/')
            #         os.mkdir('binData/'+self.filepath)
            #         self.first_file = False
            #     toSave = bytes(self.binData)
            #     fileName = 'binData/' + self.filepath + '/pHistBytes_' + str(math.floor(self.uartCounter/self.framesPerFile)) + '.bin'
            #     bfile = open(fileName, 'wb')
            #     bfile.write(toSave)
            #     bfile.close()
            #     # Reset binData and missed frames
            #     self.binData = []
 
            # Saving data here for replay
            # frameJSON = {}
            # frameJSON['frameData'] = outputDict
            # frameJSON['timestamp'] = time.time()
            # # frameJSON['CurrTime'] = time.ctime(frameJSON['timestamp']) # Add human-readable timestamp

            # self.frames.append(frameJSON)
            # data['data'] = self.frames

            # if (self.uartCounter % self.framesPerFile == 0):
            #     if(self.first_file is True): 
            #         if(os.path.exists('binData/') == False):
            #             # Note that this will create the folder in the caller's path, not necessarily in the viz folder            
            #             os.mkdir('binData/')
            #         os.mkdir('binData/'+self.filepath)
            #         self.first_file = False
            #     with open('./binData/'+self.filepath+'/replay_' + str(math.floor(self.uartCounter/self.framesPerFile)) + '.json', 'w') as fp:
            #         json_object = json.dumps(data, indent=4)
            #         fp.write(json_object)
            #         # self.frames = [] uncomment to put data into one file at a time in 100 frame chunks
        
        return outputDict

    # This function is identical to the readAndParseUartDoubleCOMPort function, but it's modified to work for SingleCOMPort devices in the xWRLx432 family
    def readAndParseUartSingleCOMPort(self):
        # Reopen CLI port
        if(self.cliCom.isOpen() == False):
            log.info("Reopening Port")
            self.cliCom.open()

        self.fail = 0
        if (self.replay):
            return self.replayHist()

        data = {'cfg': self.cfg, 'demo': self.demo, 'device': self.device}
    
        # Find magic word, and therefore the start of the frame
        index = 0
        magicByte = self.cliCom.read(1)
        frameData = bytearray(b'')
        while (1):
            # If the device doesn't transmit any data, the COMPort read function will eventually timeout
            # Which means magicByte will hold no data, and the call to magicByte[0] will produce an error
            # This check ensures we can give a meaningful error
            if (len(magicByte) < 1):
                log.error("ERROR: No data detected on COM Port, read timed out")
                log.error("\tBe sure that the device is in the proper mode, and that the cfg you are sending is valid")
                magicByte = self.cliCom.read(1)

            # Found matching byte
            elif (magicByte[0] == UART_MAGIC_WORD[index]):
                index += 1
                frameData.append(magicByte[0])
                if (index == 8): # Found the full magic word
                    break
                magicByte = self.cliCom.read(1)
                
            else:
                # When you fail, you need to compare your byte against that byte (ie the 4th) AS WELL AS compare it to the first byte of sequence
                # Therefore, we should only read a new byte if we are sure the current byte does not match the 1st byte of the magic word sequence
                if (index == 0):
                    magicByte = self.cliCom.read(1)
                index = 0 # Reset index
                frameData = bytearray(b'') # Reset current frame data
        
        # Read in version from the header
        versionBytes = self.cliCom.read(4)
        
        frameData += bytearray(versionBytes)

        # Read in length from header
        lengthBytes = self.cliCom.read(4)
        frameData += bytearray(lengthBytes)
        frameLength = int.from_bytes(lengthBytes, byteorder='little')
        
        # Subtract bytes that have already been read, IE magic word, version, and length
        # This ensures that we only read the part of the frame in that we are lacking
        frameLength -= 16 

        # Read in rest of the frame
        frameData += bytearray(self.cliCom.read(frameLength))

        # frameData now contains an entire frame, send it to parser
        if (self.parserType == "SingleCOMPort"):
            outputDict = parseStandardFrame(frameData)
        else:
            log.error('FAILURE: Bad parserType')

        # If save binary is enabled
        if(self.saveBinary == 1):
            self.binData += frameData
            # Save data every framesPerFile frames
            self.uartCounter += 1

            # uncomment below to save bin data in Matlab-friendly format
            # self.binData += frameData
            # if (self.uartCounter % self.framesPerFile == 0):
            #     # First file requires the path to be set up
            #     if(self.first_file is True): 
            #         if(os.path.exists('binData/') == False):
            #             # Note that this will create the folder in the caller's path, not necessarily in the Industrial Viz Folder                        
            #             os.mkdir('binData/')
            #         os.mkdir('binData/'+self.filepath)
            #         self.first_file = False
            #     toSave = bytes(self.binData)
                
            #     fileName = 'binData/'+self.filepath+'/pHistBytes_'+str(math.floor(self.uartCounter/self.framesPerFile))+'.bin'
            #     bfile = open(fileName, 'wb')
            #     bfile.write(toSave)
            #     bfile.close()
            #     # Reset binData and missed frames
            #     self.binData = []

            # Saving data here for replay
            frameJSON = {}
            frameJSON['frameData'] = outputDict
            frameJSON['timestamp'] = time.time()
            frameJSON['CurrTime'] = time.ctime(frameJSON['timestamp']) # Add human-readable timestamp

            self.frames.append(frameJSON)
            data['data'] = self.frames

            if (self.uartCounter % self.framesPerFile == 0):
                if(self.first_file is True): 
                    if(os.path.exists('binData/') == False):
                        # Note that this will create the folder in the caller's path, not necessarily in the viz folder            
                        os.mkdir('binData/')
                    os.mkdir('binData/'+self.filepath)
                    self.first_file = False
                with open('./binData/'+self.filepath+'/replay_' + str(math.floor(self.uartCounter/self.framesPerFile)) + '.json', 'w') as fp:
                    json_object = json.dumps(data, indent=4)
                    fp.write(json_object)
                    self.frames = [] #uncomment to put data into one file at a time in 100 frame chunks
        
        return outputDict

# while True:
#     bytecount = ser.inWaiting()
#     s = ser.read(bytecount)
#     print(s)

# ser.close()

    def sendCfg(self, cfg):
        # Remove empty lines from the cfg
        cfg = [line for line in cfg if line != '\n']
        # Ensure \n at end of each line
        cfg = [line + '\n' if not line.endswith('\n') else line for line in cfg]
        # Remove commented lines
        cfg = [line for line in cfg if line[0] != '%']

        for line in cfg:
            time.sleep(.03) # Line delay

            if(self.cliCom.baudrate == 1250000):
                for char in [*line]:
                    time.sleep(.001) # Character delay. Required for demos which are 1250000 baud by default else characters are skipped
                    self.cliCom.write(char.encode())
            else:
                self.cliCom.write(line.encode())
                
            # ack = self.cliCom.readline()
            # print(ack, flush=True)
            # ack = self.cliCom.readline()
            # print(ack, flush=True)
            # if (self.isLowPowerDevice):
            #     ack = self.cliCom.readline()
            #     print(ack, flush=True)
            #     ack = self.cliCom.readline()
            #     print(ack, flush=True)

            # splitLine = line.split()
            # if(splitLine[0] == "baudRate"): # The baudrate CLI line changes the CLI baud rate on the next cfg line to enable greater data streaming off the xWRL device.
            #     try:
            #         self.cliCom.baudrate = int(splitLine[1])
            #     except:
            #         log.error("Error - Invalid baud rate")
            #         sys.exit(1)
        # Give a short amount of time for the buffer to clear
        time.sleep(0.03)
        self.cliCom.reset_input_buffer()
        # NOTE - Do NOT close the CLI port because 6432 will use it after configuration  
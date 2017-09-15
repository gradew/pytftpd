#!/usr/bin/python

import logging
import struct
import sys
from StringIO import StringIO
import socket as socketlib
from os import path

DEFAULT_PORT = 69
RECVFROM_BUFSIZE = 65536
TRANSMISSION_TIMEOUT = 2.0 # seconds

OPCODE_RRQ = 1
OPCODE_DATA = 3
OPCODE_ACK = 4

log = logging.getLogger("tptftpserver")

class Transmitter:
    def __init__(self, aFile, client, socket):
        self.__file = aFile
        self.__client = client
        self.__socket = socket
        self.__blockNumber = 1
        self.__data = self.__file.read(512)

    def transmit(self):
        log.debug("Transmitting block number %d" % self.__blockNumber)
        self.__socket.sendto(struct.pack("!HH%ds" % len(self.__data),
                                         OPCODE_DATA, self.__blockNumber,
                                         self.__data),
                             self.__client)

    def ack(self, blockNumber):
        if blockNumber == self.__blockNumber:
            if len(self.__data) < 512:
                # EOF, transmission complete
                return True
            else:
                self.__data = self.__file.read(512)
                self.__blockNumber += 1
        else:
            log.warning("Unknown ack block number %d" % blockNumber)

    def isSameClient(self, client):
        return client == self.__client

WAIT_FOR_RRQ = 1
WAIT_FOR_ACK = 2

def main(port=DEFAULT_PORT):
    socket = __makeServerSocket(port)
    while True:
        client, requestedFile = __waitForRRQ(socket)
        log.info("Transmitting %s to %r" % (requestedFile, client))
        try:
                theFile=open("/var/lib/tftpboot/"+requestedFile)
                __rewindFile(theFile)
                __transmitFile(theFile, client, socket)
                log.info("Transmission complete")
        except:
                log.info("Failed to serve %s" % requestedFile)

def __waitForRRQ(socket):
    socket.settimeout(None)
    while True:
        packet, client = socket.recvfrom(RECVFROM_BUFSIZE)
        log.debug("Received packet=%r" % packet)
        opcode = __getOpcode(packet)
        if opcode == OPCODE_RRQ:
            mode = __getRRQMode(packet)
            # mode = octet/netsascii
            args=packet.split("\x00") # ['', '\x01file.ext', 'netascii', '']
            requestedFile=args[1].replace("\x01", "")
            break
    return client, requestedFile

def __transmitFile(theFile, client, socket):
    transmitter = Transmitter(theFile, client, socket)
    socket.settimeout(TRANSMISSION_TIMEOUT)
    while True:
        try:
            packet, client = socket.recvfrom(RECVFROM_BUFSIZE)
        except socketlib.timeout:
            log.debug("ACK timeout")
            transmitter.transmit()
            continue
        if not transmitter.isSameClient(client):
            log.warning("Packet from %r received while transmitting elsewhere"
                        % client)
            continue
        log.debug("Received possible ack %r" % (packet,))
        opcode = __getOpcode(packet)
        if opcode == OPCODE_ACK:
            if transmitter.ack(struct.unpack("!H", packet[2:4])[0]):
                break
            transmitter.transmit()
        else:
            log.warning("Unknown opcode %#x, expected ACK" % opcode)

def __rewindFile(theFile):
    theFile.seek(0, 0)

def __getRRQMode(packet):
    return packet[packet[2:].index("\0") + 3:-1].lower()

def __getOpcode(packet):
    return struct.unpack("!H", packet[0:2])[0]

def __makeServerSocket(port):
    socket = socketlib.socket(socketlib.AF_INET, socketlib.SOCK_DGRAM)
    socket.bind(('', port))
    return socket


if __name__ == "__main__":
    logging.basicConfig()
    #logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.INFO)
    main()

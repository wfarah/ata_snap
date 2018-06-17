#! /usr/bin/env python

import argparse
import adc5g
import casperfpga
import time
import numpy as np

parser = argparse.ArgumentParser(description='Program and initialize a SNAP ADC5G spectrometer',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('host', type=str,
                    help = 'Hostname / IP of SNAP')
parser.add_argument('fpgfile', type=str,
                    help = '.fpgfile to program')
parser.add_argument('-s', dest='sync', action='store_true', default=False,
                    help ='Use this flag to re-arm the designs sync logic')
parser.add_argument('-m', dest='mansync', action='store_true', default=False,
                    help ='Use this flag to manually sync the design with an asynchronous software trigger')
parser.add_argument('-t', dest='tvg', action='store_true', default=False,
                    help ='Use this flag to switch to post-fft test vector outputs')
parser.add_argument('-e', dest='eth', action='store_true', default=False,
                    help ='Use this flag to switch on Ethernet transmission')
parser.add_argument('-a', dest='acclen', type=int, default=2**18,
                    help ='Number of 2048-channel spectra to accumulate per dump')
parser.add_argument('-f', dest='fftshift', type=int, default=0xffff,
                    help ='FFT shift schedule')

args = parser.parse_args()

print "Connecting to %s" % args.host
snap = casperfpga.CasperFpga(args.host)
print "Programming %s with %s" % (args.host, args.fpgfile)
snap.upload_to_ram_and_program(args.fpgfile)

print "Configuring ADC->FPGA interface"
chosen_phase, glitches = adc5g.calibrate_mmcm_phase(snap, 0, ['ss_adc'])

print "Configuring ADCs for dual-input mode"
adc5g.spi.set_spi_control(snap, 0, adcmode=0b0100, stdby=0, dmux=1, bg=1, bdw=0b11, fs=0, test=0)

print "Setting accumulation length to %d spectra" % args.acclen
snap.write_int('timebase_sync_period', args.acclen * 4096 / 4) # convert to FPGA clocks (4096-point FFT, adc is operating as demux 4)

print "Setting FFT shift schedule to %s" % bin(args.fftshift)
snap.write_int("fft_shift", args.fftshift)

if args.sync:
    print "Re-syncing the design"
    if not args.mansync:
        print "  Waiting for a PPS to pass"
        # Wait for a PPS to pass before re-syncing
        current_sync = snap.read_int("sync_count")
        time.sleep(0.05)
        while(snap.read_int("sync_count") == current_sync):
            time.sleep(0.05)
        sync_time = int(np.ceil(time.time())) + 2 # Number of seconds for sync is determined by design
        print "  PPS passed! New sync time will be %d" % sync_time
        snap.write_int("sync_arm", 1)
        snap.write_int("sync_arm", 0)
        print "  Writing new sync time to snap memory"
        snap.write_int("sync_sync_time", sync_time)

if args.mansync:
   print "  Issuing software sync (you probably only want to do this if you don't have a PPS connected"
   for i in range(2):
       snap.write_int("sync_arm", 1<<4)
       snap.write_int("sync_arm", 0)
       time.sleep(1)

print "Initialization complete!"

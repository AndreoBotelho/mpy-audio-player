# Copyright 2024 Andre Botelho - andrebotelhomail@gmail.com
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

# Audio Player for micropython STM32 MCU, plays on DAC or PWM output
# works on background using DMA loop (need to copy all audio file on RAM)
# or a working thread (need thread suport and GIL disable)
# depends on wave and chunk mpy library.
# this library supports 8bit unsigned and 16bit signed WAVE files

import wave
from pyb import DAC,delay,udelay,Timer,freq
import array
import _thread

_TIMER =     2      #timer 2
_CHANNEL =   4      #timer 2 ch 4
_PIN     =   'A3'   #timer 2 ch 4 pin PA3
_DAC     =   1      #first DAC on Pin PA4
_FREQ    =   120000 #PWM freq

def custom_delay(t): #delay uS
     udelay(t) #using pyb.udelay
    
class AUDIO_PLAYER(object):
    
    def __init__(self, filename, pwm = True, loop = False, thread = False):
        self.filename = filename
        self.pwm_mode = pwm
        self.loop = loop
        self.dac = None
        self.pwm_out = None
        self.timer = None
        self.audiofile = None
        self.adatawidth = 8
        self.framedata = None
        self.buffersize = 2048 # set read ahead buffer size
        self.ready = False
        self.threading = thread
        self.pthread = None
        self.volumes = [49,31,21,15,11,9,7,6,5,4,3,2,1] # 12 levels volume
        self.volume = 10
        self.fstop = True
        
        
    def begin(self):
        ################### open file and output #######################
        self.audiofile = wave.open(self.filename, 'r')
        self.adatawidth = 12 if self.audiofile.getsampwidth() > 1 else 8
        if self.pwm_mode:
            #if self.adatawidth == 8:
            pr = (freq()[2] * 2) // 255 // _FREQ
            self.timer = pyb.Timer(_TIMER, prescaler=pr, period=255) 
            #else:
            #    pr = (freq()[2] * 2) // 2047 // _FREQ
            #    self.timer = pyb.Timer(_TIMER, prescaler=pr, period=2047) 
            self.pwm_out = self.timer.channel(_CHANNEL, pyb.Timer.PWM, pin=machine.Pin(_PIN, machine.Pin.OUT), pulse_width_percent=50)
        else:
            self.dac = DAC(_DAC,bits=self.adatawidth, buffering= True)
        
        ################### get audio info ##############################
        self.total_frames = self.audiofile.getnframes()
        self.framerate = self.audiofile.getframerate()
        
        self.ready = True

        
    def play(self):
        if not(self.ready): return
        self.fstop = False
        ########### load audio file to ram and play in a loop ###########
        if self.loop: 
            self.framedata = self.audiofile.readframes(self.total_frames)
            self.dac.write_timed(self.framedata, self.framerate, mode=DAC.CIRCULAR)
        ################ play audio file frame by frame ##################
        else:
            if self.adatawidth == 8:
                if self.threading:
                    self.pthread = _thread.start_new_thread(self._play8,())
                else:
                    self._play8()
            else:
                if self.threading:
                    self.pthread = _thread.start_new_thread(self._play16,())
                else:
                    self._play16()
        
    def volume_up(self):
        if self.volume < 12:
            self.volume += 1
            
    def volume_down(self):
        if self.volume > 0:
            self.volume -= 1
            
    def set_volume(self, v):
        if 0 <= v <= 12:
            self.volume = v
            
    def stop(self):
        if not(self.ready): return
        self.fstop = True
        if self.loop: 
            self.dac.write(0)
        
    ################ play audio file frame by frame ##################
    @micropython.native
    def _play16(self): #play mono signed 16 bit data
        ################# calc data feed delay #######################
        self.period = int((1 / self.framerate * 1000000) * 0.95)
        for position in range(self.buffersize, self.total_frames, self.buffersize):
            if self.fstop:
                return
            self.framedata = self.audiofile.readframes(self.buffersize) #read frames
            buf = array.array('h', self.framedata) # temp buffer to conversion
            self.audiofile.setpos(position) #update file pointer
            volume = self.volumes[self.volume]
            volume *= 128 if self.pwm_out else 16 #convert to 11 or 12 bits
            for i in range(self.buffersize):
                if self.pwm_out:
                    sample = 128 + buf[i] // volume
                    self.pwm_out.pulse_width(sample)
                else:
                    sample = 2048 + buf[i] // volume
                    self.dac.write(sample)
                custom_delay(self.period)
     
    @micropython.native
    def _play8(self): # play mono unsigned 8 bit data
        ################# calc data feed delay #######################
        self.period = int((1 / self.framerate * 1000000) * 0.90)
        for position in range(self.buffersize, self.total_frames, self.buffersize):
            if self.fstop:
                return
            self.framedata = self.audiofile.readframes(self.buffersize) #read frames
            buf = array.array('B', self.framedata) # temp buffer to conversion
            self.audiofile.setpos(position)
            volume = self.volumes[self.volume]
            for i in range(self.buffersize):
                sample = buf[i] // volume
                if self.pwm_out:
                    self.pwm_out.pulse_width(sample)
                else:
                    self.dac.write(sample)
                custom_delay(self.period)
            



# USAGE EXAMPLES

#audio = AUDIO_PLAYER('/flash/SND/arpeggio.wav')
#audio = AUDIO_PLAYER('/flash/SND/short-alarm2.wav',loop = True)
#audio = AUDIO_PLAYER('/flash/SND/idiota.wav')
#audio = AUDIO_PLAYER('/flash/SND/idiota8.wav')
#audio = AUDIO_PLAYER('/flash/SND/idiotafull.wav')

audio = AUDIO_PLAYER('/flash/SND/idiota8.wav', pwm = True, thread = True)
audio.begin()
audio.play()
# delay(2000)
# audio.stop()

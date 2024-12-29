import pyvisa
import time
import pandas as pd
import matplotlib.pyplot as plt
import os,sys
import numpy as np
from labdrivers.quantumdesign import qdinstrument
from matplotlib.animation import FuncAnimation
#from MultiPyVu import MultiVuClient as mvc

os.chdir(sys.path[0])

class AHE():
    def __init__(self,path_name,file_name,frequency,temperature0,field0,scan_rate,harm,set_temp,waiting_time,ppms):
        self.path_name = path_name
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        self.file_name = file_name+'temperature_{}K_field_{}Oe_{}GHz_SP'.format(temperature0,field0,frequency)
        self.frequency = frequency
        # Initialize the VISA resource manager
        rm = pyvisa.ResourceManager()
        # Open connections
        #self.k2901 = rm.open_resource('GPIB0::17::INSTR') #B2901A
        self.sr830 = rm.open_resource('GPIB1::8::INSTR')  #sr830
        self.e8257d = rm.open_resource('GPIB0::19::INSTR')
        #self.k2901 = rm.open_resource('GPIB1::17::INSTR') #B2901A
        #self.volt = volt
        self.harm = harm
        self.set_config()

        print('start to connect DynaCool')
        self.ppms=ppms
        print('connection established')

        if set_temp:
            self.set_temp(temperature0)
            for i in range(waiting_time):
                print("waiting temperature {} second left".format(waiting_time-i))
                time.sleep(1)
        self.set_field(field0)

        self.fields = []
        self.voltages = []
        self.voltages_y = []

        # Prepare for plotting
        self.animating = True
        self.fig = plt.figure(figsize=(10,4))
        self.ax1 = self.fig.add_axes([0.15,0.2,0.3,0.7])
        self.ax2 = self.fig.add_axes([0.65,0.2,0.3,0.7])
        plt.subplots_adjust(left=0.2,right=0.9,top=0.9,bottom=0.2)
        self.ax1.set_xlabel("Field (Oe)")
        self.ax1.set_ylabel("Voltage_x (V)")
        self.ax2.set_xlabel("Field (Oe)")
        self.ax2.set_ylabel("Voltage_y (V)")

        #self.k2901.write(":OUTP ON")  # Turn on the output
        self.e8257d.write('OUTP ON')
        self.sr830.write("SLVL 1")
        time.sleep(0.5)
        self.scan_field(-field0,scan_rate)
        time.sleep(0.5)
        #self.k2901.write(":OUTP OFF")  # Turn on the output
        self.sr830.write("SLVL 0.01")
        self.e8257d.write('OUTP OFF')

        print('measurement compeleted')
        self.animating = False 
        plt.ioff()
        plt.close()
        plt.clf()

        # Close the connections
        self.sr830.close()

    def set_config(self):
        # Configure Keysight B2901A for pulsed current output
        # Configure Keithley 2182A to measure voltage
        self.sr830.write('*RST')
        self.sr830.write("FREQ 1713")
        self.sr830.write("SLVL 0.01")
        if self.harm == 2:
            self.sr830.write("PHAS 90")
        elif self.harm ==1:
            self.sr830.write("PHAS 0")
        self.sr830.write("HARM {}".format(self.harm))
        self.sr830.write("ISRC 1")
        if self.harm == 2:
            self.sr830.write("SENS 11")
        elif self.harm == 1:
            #self.sr830.write("SENS 16") #500uV
            self.sr830.write("SENS 17") #11-10uV  10-5uV
            #self.sr830.write("SENS 24") #200mV
        # self.sr830.write("OFIT 8")  # unknown probably mistyped
        self.sr830.write("OFLT 8")  # time constant
        self.sr830.write("OFSL 8")  # slope
        self.sr830.write('FMOD 1')  # internal
        self.sr830.write('RSLP 0')  # sine
        self.sr830.write("RMOD 2")  # low noise
        self.sr830.write("OEXP 1,0,2") # x,offset,expand
        self.sr830.write("OEXP 2,0,2") # x,offset,expand

        # Set frequency to 4 GHz
        self.e8257d.write('FREQ {} GHz'.format(self.frequency))
        # Set power to 20 dBm
        self.e8257d.write('POW 20 dBm')
        # Enable AM modulation
        self.e8257d.write('AM:STATE ON')
        # Select the AM modulation source as External1
        self.e8257d.write('AM:SOUR EXT1')
        # Set AM type to Linear
        self.e8257d.write('AM:TYPE LIN')
        # Set AM depth to 100%
        self.e8257d.write('AM:DEPT 100')

    def set_temp(self,temperature0,t_rate=12):
        print('start to set temperature to {}'.format(temperature0))
        self.ppms.setTemperature(temperature0,t_rate)
        time.sleep(0.5)
        _, temperature, status = self.ppms.getTemperature()
        while status != 1: #1 stable 6 Tracking
            _, temperature, status = self.ppms.getTemperature()
            print(temperature,status)
            time.sleep(1)
            pass
        print('temperature set successfully')

    def set_field(self,field0,h_rate=200):
        print('start to set field to {}'.format(field0))
        self.ppms.setField(field0,h_rate)
        time.sleep(0.5)
        _,field, status = self.ppms.getField()
        while status != 4 or np.abs(field-field0)>1: 
            _,field, status = self.ppms.getField()
            print(field,status)
            time.sleep(1)
            pass
        print('field set successfully')


    def scan_field(self,end_field,scan_rate):
        print('start to scan field')
        time.sleep(0.1)
        def animate(i):
            if not self.animating:
                ani.event_source.stop()  # Stop the animation
                return
            self.ax1.clear()
            self.ax1.plot(self.fields, self.voltages, '-o', color='#1f77b4')
            self.ax2.clear()
            self.ax2.plot(self.fields, self.voltages_y, '-o', color='#1f77b4')
        # Start the animation
        ani = FuncAnimation(self.fig, animate, interval=3000, cache_frame_data=False)  # Update every 2000 ms

        self.ppms.setField(end_field, scan_rate)
        time.sleep(0.01)
        _,field,status = self.ppms.getField()
        while np.abs(field - end_field) > 1 or status != 4:
            try:
                # Query for both the real part (X) and the imaginary part (Y)
                response = self.sr830.query('SNAP?1,2')
                # The response will typically be a comma-separated string, e.g., "X,Y"
                real_part, imaginary_part = response.split(',')
                voltage,voltage_y =map(float,[real_part,imaginary_part])
                _,field,status = self.ppms.getField()
                self.fields.append(field)
                self.voltages.append(voltage)
                self.voltages_y.append(voltage_y)
                time.sleep(0.0005)
                plt.pause(0.0005)
            except Exception as e:
                print(f"Error during data collection: {e}")
                break

        df = pd.DataFrame({'field (Oe)':self.fields,'voltage_x (V)':self.voltages,'voltage_y (V)':self.voltages_y})        
        df.to_csv(self.path_name + self.file_name + '.csv')
        plt.savefig(self.path_name + self.file_name + '.png', dpi=300)


def end_mearsument():
    ppms=qdinstrument.QdInstrument('DynaCool','192.168.0.4')
    ppms.setTemperature(300,12)
    ppms.setField(0)
    rm = pyvisa.ResourceManager()
    sr830 = rm.open_resource('GPIB1::8::INSTR')  #sr830
    e8257d = rm.open_resource('GPIB0::19::INSTR')
    sr830.write("SLVL 0.01")
    e8257d.write('OUTP OFF')
    sr830.close()
    e8257d.close()
    # ppms.setPosition(0,1)

if __name__ == "__main__":
    ppms0 = qdinstrument.QdInstrument('DynaCool','192.168.0.4')
    for i in range(300,295,-10):  
        AHE(path_name='./SP/varing_vicinal/',
                        # SP\LFO-oxygen\2Pa_new_24Oct23
                file_name= 'round2_miscut1_90deg',
                frequency = 4,
                temperature0 = i, #K
                field0 = 800, #Oe
                scan_rate = 20, #Oe/s
                harm = 1,
                set_temp = False,
                waiting_time=10,
                ppms =ppms0
                ) #mA
    # for i in range(290,70,-10):
    #     AHE(path_name='./SP/LFO/3nm_24Jul30/',
    #             file_name= '60deg_',
    #             frequency = 4,
    #             temperature0 = i, #K
    #             field0 = 800, #Oe
    #             scan_rate = 20, #Oe/s
    #             harm = 1,
    #             set_temp = True,
    #             waiting_time=60,
    #             ppms =ppms0
    #             ) #mA
    # for i in range(160,95,-10):
    # # for i in [150]:
    #     AHE(path_name='./SP/LFO/LSMO_Dec30_90deg/',
    #             file_name= '90deg',
    #             frequency = 4,
    #             temperature0 = i, #K
    #             field0 = 800, #Oe
    #             scan_rate = 20, #Oe/s
    #             harm = 1,
    #             set_temp = True,
    #             waiting_time=10,
    #             ppms =ppms0
    #             ) #mA
    # for i in [180]:
    #     AHE(path_name='./SP/LFO/3nm_24Jul30/',
    #             file_name= '45deg_',
    #             frequency = 4,
    #             temperature0 = i, #K
    #             field0 = 800, #Oe
    #             scan_rate = 20, #Oe/s
    #             harm = 1,
    #             set_temp = True,
    #             waiting_time=60,
    #             ppms =ppms0
    #             ) #mA
    end_mearsument()

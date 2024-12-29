import pyvisa
import time
import pandas as pd
import matplotlib.pyplot as plt
import os,sys
import numpy as np
#from MultiPyVu import MultiVuClient as mvc
from matplotlib.animation import FuncAnimation
from labdrivers.quantumdesign import qdinstrument

os.chdir(sys.path[0])

class AHE():
    def __init__(self,path_name,file_name,temperature0,field0,scan_rate,harm,set_temp,waiting_time,pos1,pos2):
        self.path_name = path_name
        # ---------------------------------------------------------
        # ---------------------------------------------------------
        self.file_name = file_name+'temperature_{}K_field_{}Oe_{}harm.csv'.format(temperature0,field0,harm)
        # Initialize the VISA resource manager
        rm = pyvisa.ResourceManager()
        
        # Open connections
        #self.k2901 = rm.open_resource('GPIB0::17::INSTR') #B2901A
        self.k6221 = rm.open_resource('GPIB1::12::INSTR') #k6221
        self.sr830 = rm.open_resource('GPIB0::8::INSTR')  #sr830
        self.harm = harm
        self.set_config()
        self.field0 = field0

        print('start to connect DynaCool')
        self.ppms=qdinstrument.QdInstrument('DynaCool','192.168.0.4')
        print('connection established')

        if set_temp:
            self.set_temp(temperature0)
            for i in range(waiting_time):
                time.sleep(1)
                print('waiting, remaining time {}'.format(waiting_time-i))
        

        self.positions = []
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

        self.k6221.write("SOUR:WAVE:ARM")
        self.k6221.write("SOUR:WAVE:INIT")
        time.sleep(1)
        self.scan_position(pos1,pos2,scan_rate,self.field0)
        time.sleep(1)
        self.scan_position(pos2,pos1,scan_rate,self.field0)
        time.sleep(1)
        self.k6221.write(":OUTP OFF")  # Turn on the output
        #self.k2901.write(":OUTP OFF")  # Turn on the output

        print('measurement compeleted')
        self.animating = False  # Stop the animation after data collection is complete
        plt.ioff()
        plt.close()
        plt.clf()

        # Close the connections
        self.sr830.close()

    def set_config(self):
        # Configure Keysight B2901A for pulsed current output
        # Configure Keithley 2182A to measure voltage
        self.sr830.write("FREQ 1713")
        self.sr830.write("SLVL 0.01")
        if self.harm == 2:
            self.sr830.write("PHAS 90")
        elif self.harm ==1:
            self.sr830.write("PHAS 0")
        self.sr830.write("HARM {}".format(self.harm))
        self.sr830.write("ISRC 1")
        if self.harm == 2:
            # self.sr830.write("SENS 10")
            self.sr830.write("SENS 13")
            # self.sr830.write("SENS 15")
        elif self.harm == 1:
            self.sr830.write("SENS 26") #1mV
        self.sr830.write("OFIT 8")
        self.sr830.write("OFSL 8")
        self.sr830.write("RSLP 1")
        self.sr830.write("FMOD 0")
        #self.k2901.write(":SOUR:FUNC:MODE VOLT")
        #self.k2901.write(f":SOUR:VOLT {self.volt* 1e-3}")
        #self.k2901.write(":SENS:CURR:PROT 0.002")

        self.k6221.write('*RST')
        self.k6221.write('SOUR:WAVE:AMPL 5e-3')
        self.k6221.write('SOUR:WAVE:FREQ 1713')
        self.k6221.write('SOUR:WAVE:PMAR:STAT 1')
        self.k6221.write('SOUR:WAVE:PMAR:LEV 0')
        self.k6221.write('SOUR:WAVE:PMAR:OLINE 3')

    def set_temp(self,temperature0,t_rate=10):
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
    
    def set_position(self,pos0,p_rate=5):
        print('start to set position to {}'.format(pos0))
        self.ppms.setPosition(pos0,p_rate)
        time.sleep(0.5)
        _,pos, status = self.ppms.getPosition()
        while status != 1 or np.abs(pos-pos0)>0.1: 
            _,pos, status = self.ppms.getPosition()
            print(pos,status)
            time.sleep(1)
            pass
        print('position set successfully')


    def scan_position(self,ini_pos, end_pos, scan_rate,field):
        print('Start to scan position')
        time.sleep(0.1)
        def animate(i):
            if not self.animating:
                ani.event_source.stop()  # Stop the animation
                return
            self.ax1.clear()
            self.ax1.plot(self.positions, self.voltages, '-o', color='#1f77b4')
            self.ax2.clear()
            self.ax2.plot(self.positions, self.voltages_y, '-o', color='#1f77b4')
        # Start the animation
        ani = FuncAnimation(self.fig, animate, interval=2000, cache_frame_data=False)  # Update every 2000 ms
        
        self.set_position(ini_pos)
        time.sleep(1)
        self.set_field(field)
        time.sleep(1)
        self.ppms.setPosition(end_pos, scan_rate)
        time.sleep(0.1)
        _,pos,status = self.ppms.getPosition()
        while np.abs(pos - end_pos) > 0.1 or status != 1:
            try:
                response = self.sr830.query('SNAP?1,2')
                # The response will typically be a comma-separated string, e.g., "X,Y"
                real_part, imaginary_part = response.split(',')
                voltage,voltage_y =map(float,[real_part,imaginary_part])
                _,pos,status = self.ppms.getPosition()
                self.positions.append(pos)
                self.voltages.append(voltage)
                self.voltages_y.append(voltage_y)
                time.sleep(0.001)
                plt.pause(0.001)
            except Exception as e:
                print(f"Error during data collection: {e}")
                break


        df = pd.DataFrame({'position (degree)': self.positions, 'voltage_x (V)': self.voltages, 'voltage_y (V)': self.voltages_y})
        df.to_csv(self.path_name + self.file_name + '.csv')
        plt.savefig(self.path_name + self.file_name + '.png', dpi=300)

def end_mearsument():
    ppms=qdinstrument.QdInstrument('DynaCool','192.168.0.4')
    ppms.setTemperature(300)
    ppms.setField(0)
    ppms.setPosition(0,1)

if __name__ == "__main__":
    for i in [550,-550]:
        AHE(path_name='./Feb19_15-3-4_LSAT/device12_angle/',
                file_name ='Jul13_rotate',
                temperature0 = 180, #K
                field0 = i, #Oe
                scan_rate = 2, #degree/s
                harm = 2,
                set_temp = True,
                waiting_time = 60,
                pos1 = 0,
                pos2 = 360
                ) #mA
    for i in [550,-550]:
        AHE(path_name='./Feb19_15-3-4_LSAT/device12_angle/',
                file_name ='Jul13_rotate_1',
                temperature0 = 180, #K
                field0 = i, #Oe
                scan_rate = 2, #degree/s
                harm = 1,
                set_temp = True,
                waiting_time = 60,
                pos1 = 0,
                pos2 = 360
                ) #mA
        # AHE(path_name='./Feb19_15-3-4_LSAT/device13_angle/',
        #         file_name ='Jun23',
        #         temperature0 = 180, #K
        #         field0 = i, #Oe
        #         scan_rate = 0.5, #degree/s
        #         harm = 1,
        #         set_temp = False,
        #         waiting_time = 0,
        #         pos1 = 70,
        #         pos2 = 105
        #         ) #mA
    end_mearsument()

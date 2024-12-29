import pyvisa
import time
import pandas as pd
import matplotlib.pyplot as plt
import os,sys
import numpy as np
from labdrivers.quantumdesign import qdinstrument
from matplotlib.animation import FuncAnimation

os.chdir(sys.path[0])

# ---------------------------------------------------------
# ---------------------------------------------------------

class Current_swtiching():
    def __init__(self,path_name,temperature0,sat_field,field0,current_list,width,mear_curr,set_temp,wating_time,ppms):
    ## required input：
        self.path_name = path_name
        self.maxcurrent = current_list[-1]
        self.mear_curr = mear_curr #mA
        self.temperature0 = temperature0
        self.field0 = field0

        # Initialize the VISA resource manager
        rm = pyvisa.ResourceManager()

        # Open connections
        print('start to connect 2901 and 2182')
        self.k2901 = rm.open_resource('GPIB1::17::INSTR') #B2901A
        self.k2182 = rm.open_resource('GPIB0::7::INSTR')  #2182A
        # Configure
        self.set_config(mear_curr,width)
        print('2901 and 2182 connected')

        #Connect to PPMS
        print('start to connect DynaCool')
        self.ppms=ppms
        print('connection established')

        if set_temp:
            self.set_temp(temperature0)
            for i in range(wating_time):
                print('waiting temperature stable, remaining time {} s'.format(wating_time-i))
                time.sleep(1)

        self.set_field(sat_field)
        time.sleep(2)
        self.set_field(field0)

        self.k2901.write(":OUTP ON")  # Turn on the output
        time.sleep(1)

        # Prepare for plotting
        plt.ion()  # Turn on interactive mode

        self.animating = True
        self.fig = plt.figure(figsize=(5,4))
        self.ax1 = self.fig.add_axes([0.2,0.2,0.6,0.6])
        self.ax1.set_xlabel("Current (mA)")
        self.ax1.set_ylabel("Resistance (ohm)")
        self.currents = []
        self.voltages = []
        self.resistances = []

        self.test_current()
        self.scan_current(current_list)

        # Finish plotting
        print('measurement compeleted')
        self.animating = False 
        plt.ioff()
        plt.close()
        plt.clf()
        self.k2901.write(":OUTP OFF")

        # Close the connections
        self.k2901.close()
        self.k2182.close()

    def set_config(self,mear_curr,width):
        self.k2182.write('*RST')
        self.k2901.write('*RST')
        self.k2901.write(":SOUR:FUNC:MODE CURR")
        self.k2901.write(":SOUR:FUNC PULS")
        self.k2901.write(f":SOUR:CURR {mear_curr * 1e-3}")
        self.k2901.write(f":SOURCE:PULS:WIDTH {width * 1e-3}")  # Set triggered level
        self.k2901.write(":SENS:VOLT:PROT 42")

        self.k2182.write(":SENS:FUNC 'VOLT:DC'")
        self.k2182.write(":SENS:VOLT:DC:RANGE 10") # 10 mV minimal range

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

    def extract_voltage(self,response):
        # You can customize this function if the output format changes.
        #print(response)
        response = response.replace('=','-')
        response = response.replace(';','+')
        response = response.replace('U','E')
        response = response.replace('>','.')
        response = response.replace('\x1a','')
        #print(response)
        return(float(response))

    def test_current(self):
        print('test current')
        for i in range(3):
            self.k2901.write(f":SOUR:CURR:TRIG {0}")  # Set triggered level
            self.k2901.write(":INIT")
            time.sleep(1)  # Wait for stabilization
            self.k2182.query(":READ?")
            time.sleep(0.1)  # Wait for stabilization

    def scan_current(self,current_list):
        print('start to scan current')
        time.sleep(0.1)
        def animate(i):
            if not self.animating:
                ani.event_source.stop()  # Stop the animation
                return
            self.ax1.clear()
            self.ax1.plot(self.currents, self.resistances, '-o', color='#1f77b4')
        # Start the animation
        ani = FuncAnimation(self.fig, animate, interval=3000, cache_frame_data=False)  # Update every 2000 ms

        for current in current_list:  # In mA
            print('appiled pulsed current {} mA'.format(current))
            # Set the pulse current level
            self.k2901.write(f":SOUR:CURR:TRIG {current * 1e-3}")  # Set triggered level
            self.k2901.write(":INIT")

            time.sleep(1)  # Wait for stabilization
            
            voltage = 0
            num = 10
            for i in range(num):
                response = self.k2182.query(":READ?")
                voltage += self.extract_voltage(response)
                time.sleep(0.01) 
            voltage = voltage/num
            time.sleep(0.1)  # Wait for stabilization

            # Append data to lists
            self.currents.append(current)
            self.voltages.append(voltage)
            self.resistances.append(voltage/(self.mear_curr*1e-3))

            plt.pause(0.1)  # Short pause to update plot
            time.sleep(0.1)  # Wait for stabilization

        df = pd.DataFrame({'I':self.currents,'V':self.voltages,'R':self.resistances})
        file_name = 'temperature_{}K_field_{}Oe_max_current_{}mA'.format(self.temperature0,self.field0,self.maxcurrent)
        df.to_csv(self.path_name+file_name+'.csv')
        plt.savefig(self.path_name+file_name+'.png',dpi=300)

def end_mearsument():
    ppms=qdinstrument.QdInstrument('DynaCool','192.168.0.4')
    ppms.setTemperature(300,12)
    ppms.setField(0)


if __name__ == "__main__":
    #current_list = [0,20,25,29,33,37,40]+[37,33,29,25,20,0]+[-20,-25,-29,-33,-37,-40]+[-37,-33,-29,-25,-20]+[0,20,25,29,33,37,40]
    path_name = './SRO_LFO_SIO/22nm/0deg_20x60/'
    ppms0 = qdinstrument.QdInstrument('DynaCool','192.168.0.4')
    c_max = 9
    current_list = list(np.linspace(0,c_max,15)) + list(np.linspace(c_max,-c_max,15))+list(np.linspace(-c_max,c_max,15))
    # current_list = [0,15,20,25,30,33,36,38]+[36,33,30,27,25,15,0]+[-15,-20,-25,-30,-33,-36,-38]+[-36,-33,-30,-25,-20,-15]+[0,15,20,25,30,33,36,38]
    # current_list = [0,20,25,29,33,37,40]+[37,33,29,25,20,0]+[-20,-25,-29,-33,-37,-40]+[-37,-33,-29,-25,-20]+[0,20,25,29,33,37,40]
    #current_list = [0,15,25,30,35,40,43,45]+[43,40,35,30,25,15,0]+[-15,-25,-30,-35,-40,-43,-45]+[-43,-40,-35,-30,-25,-15]+[0,15,25,30,35,40,43,45]
    # current_list = [0,25,35,39,43,46,49]+[46,43,39,35,25]+[0,-25,-35,-39,-43,-46,-49]+[-46,-43,-39,-35,-25]+[0,25,35,39,43,46,49]
    # current_list = [0,40,60,70,80,85,90]+[85,80,70,60,40]+[-0,-40,-60,-70,-80,-85,-90]+[-85,-80,-70,-60,-40]+[0,40,60,70,80,85,90]
    # current_list = [0,5]
    # current_list = [0,0.02,0.03,0.04,0.05,0.06,0.07]+[0.06,0.05,0.04,0.03,0.02,0]+[-0.02,-0.03,-0.04,-0.05,-0.06]+[-0.07,-0.06,-0.05,-0.04,-0.03,-0.02,0]+[0.02,0.03,0.04,0.05,0.06,0.07]
    # current_list = 0.8*np.array(current_list)
    # for i in range(290,49,-30):
    #     Current_swtiching(path_name = path_name,
    #                     temperature0 = i,
    #                     field0 = 0,
    #                     current_list=np.array(current_list),
    #                     mear_curr= 1,
    #                     width = 0.5,
    #                     set_temp = True,
    #                     wating_time=0,
    #                     ppms=ppms0)
    
    Current_swtiching(path_name = path_name,
                      temperature0 = 70,
                      sat_field = -500,
                      field0 = -500,
                      current_list=current_list,
                      mear_curr= 0.1,
                      width = 1,
                      set_temp = True,
                      wating_time=180,
                      ppms=ppms0)
    # Current_swtiching(path_name = path_name,
    #                   temperature0 = 100,
    #                   field0 = 0,
    #                   current_list=current_list,
    #                   mear_curr= 5,
    #                   width = 0.5,
    #                   set_temp = False,
    #                   wating_time=300,
    #                   ppms=ppms0)
    # Current_swtiching(path_name = path_name,
    #                   temperature0 = 100,
    #                   field0 = 500,
    #                   current_list=current_list,
    #                   mear_curr= 5,
    #                   width = 0.5,
    #                   set_temp = False,
    #                   wating_time=300,
    #                   ppms=ppms0)
    # Current_swtiching(path_name = path_name,
    #                   temperature0 = 100,
    #                   field0 = 1000,
    #                   current_list=current_list,
    #                   mear_curr= 5,
    #                   width = 0.5,
    #                   set_temp = False,
    #                   wating_time=300,
    #                   ppms=ppms0)
    # end_mearsument()
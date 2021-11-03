#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Mar  5 14:29:20 2020

@author: hegedues
"""

# %load_ext autoreload
# %autoreload 2
# sys.path.append('/home/p212user/sardanaMacros/sg') # <-- path to directory containing the import modules



DEBUG = True

import PyTango as PT
import HasyUtils as HU
import sys, os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.patches import Rectangle
import time

import weakref # to keep track of the grain or candidate objects

from PIL import Image

import _func


SE = '\033[41m'
SI = '\033[44m'
EE = '\033[0m'


DEFEXPTIME = 0.5




def lsenvironment():
    ip = get_ipython() # this only works from Ipython, where get_ipython is in the global namespace
    ip.magic('lsenv')



def _prepare_config_file(path):
    with open(os.path.join(path, 'config.dat', 'w')) as f:
        f.write('# This is an automatically generated measurement configuration file for single grain diffraction measurements\n')
        f.write('# This file contains the name of the necessary devices. The device instance has to be filled.\n# The user may define new devices following the syntax:\n# dev_name: instance(with full path)\n')
        f.write('# Alternatively local spock names may also be used\n')
        f.write('# Comment lines begin with hashtag and empty lines are discarded.\n\n')
        f.write('# horizontal motor\n')
        f.write('mot_hor: \n')
        f.write('# vertical motor\n')
        f.write('mot_ver: \n')
        f.write('# omega rotation motor\n')
        f.write('mot_rot: \n\n')
        f.write('# near field detector:\n')
        f.write('det_near: \n')
        f.write('nearDetAbtgChannel: \n')
        f.write('mot_nearDetY: \n')
        f.write('nearDetYIn: \n')
        f.write('nearDetYOut: \n\n')
        f.write('# far field detector:')
        f.write('det_far: \n')
        f.write('farDetAbtgChannel: \n')
        f.write('mot_farDetY: \n')


        



class Measurement:
    '''
    Class to define the measurement parameters:
        
        movable devices for y, z, and omega
            -> this would be a nested dict with the names in this module as keys 
            and a subdir containing the device_name and the device instance itself
        detectors
            -> near and far field detectors

        it can not handle counters yet
        
        database
        directory
        log
    '''
    def __init__(self, config_file, path=None):
        devices = self.read_config_file(config_file)
        if DEBUG: print(devices)
        self.devs = {}
        self.measurement_path = path
        self.create_directory()
        self.temp_setup_detector_folders()
        # make nested dict out of the device dict
        for k in devices['movables'].keys():
            self.devs[k] = {'name': devices['movables'][k], 'dev': self.import_device(devices['movables'][k])}
        
    
    def read_config_file(self, config_file):
        '''
        reads in the given configuration file
        it returns a nested dictionary with 'movables', 'counters'...
        '''
        devices = {'movables': {}, 'counters': {}, 'detectors': {}}
        aux = {}  # motor positions and detector channels
        try:
            with open(config_file, 'r') as f:
                data = f.read()
        except:
            print('Error!\n%s could not be opened.' % (config_file))
        for l in data.strip().split('\n'):
            if '#' in l or not l: # skipping comment and empty lines
                pass
            else:
                key = l.partition(':')[0]
                value = l.partition(':')[2].strip()
                if key.partition('_')[0] == 'mot': # movable device
                    devices['movables'][key] = value
                elif key.partition('_')[0] == 'cou': # counter device
                    devices['counters'][key] = value
                elif key.partition('_')[0] == 'det': # counter device
                    devices['detectors'][key] = value
                else:
                    aux[key] = value
        print('Config file read successfully')
        return devices


    def import_device(self, dev_name):
        '''
        import a single device
        dev_name is the instance name with full path or alternatively a local (same host!) spock name
        '''
        if '/' not in dev_name:
            sn = _func._getMoveableSpockNames()
            dev_name = HU.getHostname()+':10000/'+sn[dev_name]
        try:
            dev = PT.DeviceProxy(dev_name)
        except:
            print('Could not import %s' % dev_name)
            sys.exit(1)
        try:
            dev.state()
        except Exception as e:
            print('%s\nWarning! %s imported successfully, but does not respond.' % (e, dev_name))
        if DEBUG: print('%s device imported' % dev_name)
        return dev

    
    def create_directory(self):
        if self.measurement_path is not None:
            if not os.path.isabs(self.measurement_path):
                self.measurement_path = os.path.join('/gpfs/current/raw', self.measurement_path)
            if os.path.exists(self.measurement_path):
                raise ValueError(SE+'Directory exists'+EE)
        else:
            raise ValueError(SE+'Directory not given'+EE)
        try:
            os.makedirs(self.measurement_path)
            print(SI+'Measurement dir: %s'%(self.measurement_path)+EE)
        except:
            raise ValueError(SE+'Cannot create directory'+EE)
        self.neardir = os.path.join(self.measurement_path, 'near')
        os.makedirs(self.neardir)

        self.fardir = os.path.join(self.measurement_path, 'far')
        os.makedirs(self.fardir)

    
    def temp_setup_detector_folders(self):
        self.varex = PT.DeviceProxy('hasep21eh3:10000/p21/MultiXRDTango/hasep21perk02')
        self.Lambda = PT.DeviceProxy('hasmlmbd02:10000/petra3/lambda/01')
        self.varex.AllStopAcq()
        self.Lambda.StopAcq()
        time.sleep(0.2)
        
        self.varex.FileDir1 = self.varexdir.replace('/gpfs/', 't:/')
        self.Lambda.SaveFilePath = self.lambdadir
    
    
    def create_database(self):
        pass



'''
general class for grain Candidates
the actual grain class could be an inheritance from the candidates class
'''



class Grain(object):
    '''
    Class to hold grain properties
    M - is the instance of the measurement class, definig the devices needed
    '''
    instances = []
    
    def __init__(self, M):
        #self.__class__.instances.append(self)
        self.M = M
        self._ypos = [M.devs['mot_hor']['dev'].position]
        self._zpos = [M.devs['mot_ver']['dev'].position]
        self._rotpos = [M.devs['mot_rot']['dev'].position]
        
        self.roi = None
        self.Lroi =None
        
        # some magic to get the spock names of the moveable devices so that later they can be used by spock macros like mv
        self.moveable_spock_names = _func._getMoveableSpockNames()
        self.inv_moveable_spock_names = {v: k for k, v in self.moveable_spock_names.items()}
        self.mot_hor = self.inv_moveable_spock_names[M.devs['mot_hor']['dev'].dev_name()]
        self.mot_ver = self.inv_moveable_spock_names[M.devs['mot_ver']['dev'].dev_name()]
        self.mot_rot = self.inv_moveable_spock_names[M.devs['mot_rot']['dev'].dev_name()]
        if DEBUG: print(self.mot_hor, self.mot_ver, self.mot_rot)
        self.spock = get_ipython()

    #@classmethod
    #def printInstances(cls):
    #    for instance in cls.instances:
    #        print(instance)


        
    def new_pos(self, ypos= None, zpos=None, Opos=None):
        self._ypos.append(self.M.devs['mot_hor']['dev'].position)
        self._zpos.append(self.M.devs['mot_ver']['dev'].position)
        self._rotpos.append(self.M.devs['mot_rot']['dev'].position)

    def current_pos(self):
        return [self._ypos[-1], self._zpos[-1], self._rotpos[-1]]

    def all_pos(self):
        return [self._ypos, self._zpos, self._rotpos]
        
    def goto_grain_center(self):
        #cp = self.current_pos()
        #command = 'umv %s %f %s %f %s %f' % \
        #                 (self.mot_hor, self.current_pos()[0],
        #                  self.mot_ver, self.current_pos()[1],
        #                  self.mot_rot, self.current_pos()[2])
        #if DEBUG: print(command)
        self.spock.magic('umv %s %f %s %f %s %f' %
                         (self.mot_hor, self.current_pos()[0],
                          self.mot_ver, self.current_pos()[1],
                          self.mot_rot, self.current_pos()[2]))


    def centerH(self, start, end, NoSteps, rotstart, rotend, exposure=DEFEXPTIME, channel=1):
        # move slits:
        
        if channel == 3:
            self.M.Lambda.StopAcq()
        elif channel == 1:
            self.M.varex.AllStopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True
        time.sleep(0.1)
        if channel == 1:
            if not self.roi:
                positions, self.roi = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure, channel=channel, roi=self.roi)
            else:
                positions, _ = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.roi)
        if channel == 3:
            if not self.Lroi:
                positions, self.Lroi = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.Lroi)
            if self.Lroi:
                positions, _ = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                    channel=channel, roi=self.Lroi)

        #self.new_pos()


    def centerV(self, start, end, NoSteps, rotstart, rotend, exposure=DEFEXPTIME, channel=1):
        # move slits:
            
        if channel == 3:
            self.M.Lambda.StopAcq()
        elif channel == 1:
            self.M.varex.AllStopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True
        time.sleep(0.1)
        if channel == 1:
            if not self.roi:
                positions, self.roi = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure, channel=channel, roi=self.roi)
            else:
                positions, _ = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.roi)
        if channel == 3:
            if not self.Lroi:
                positions, self.Lroi = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.Lroi)
            else:
                positions, _ = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                    channel=channel, roi=self.Lroi)
        #self.new_pos()

    def centerO(self, start, end, NoSteps, exposure=DEFEXPTIME, channel=1):
        self.spock.magic('wm idrz1')
        # move slits:
            
            
        if channel == 3:
            self.M.Lambda.StopAcq()
        elif channel == 1:
            self.M.varex.AllStopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True
        time.sleep(0.1)

        if channel == 1:
            if not self.roi:
                cen, self.roi = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.roi)
            else:
                cen,_ = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.roi)
        if channel == 3:
            if not self.Lroi:
                cen, self.Lroi = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.Lroi)
            else:
                cen, _ = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.Lroi)
        
        #self.new_pos()


    def redef_ROI(self, imsource, channel=1):
        if channel == 1:
            self.roi, _ = _func.explorer(imsource)
        if channel == 3:
            self.Lroi, _ = _func.explorer(imsource)
        

    def showMap(self, fiofile):
        _func.showMap(fiofile, 3, self.Lroi)

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        

        
        
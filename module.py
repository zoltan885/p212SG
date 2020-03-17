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
from matplotlib.backends.backend_pdf import PdfPages


SE = '\033[41m'
SI = '\033[44m'
EE = '\033[0m'


DEFEXPTIME = 0.5

HORIZONTALBEAM = {'eh3st': 0.01, 'eh3sb': 0.01, 'eh3so': 0.1, 'eh3si': 0.1}
VERTICALBEAM   = {'eh3st': 0.1, 'eh3sb': 0.1, 'eh3so': 0.01, 'eh3si': 0.01}
LARGEBEAM      = {'eh3st': 0.1, 'eh3sb': 0.1, 'eh3so': 0.1, 'eh3si': 0.1}


def lsenvironment():
    ip = get_ipython() # this only works from Ipython, where get_ipython is in the global namespace
    ip.magic('lsenv')



def _prepare_config_file(path):
    with open(path+'/config.dat', 'w') as f:
        f.write('# This is an automatically generated measurement configuration file for single grain diffraction measurements\n')
        f.write('# This file contains the name of the necessary devices. The device instance has to be filled.\n# The user may define new devices following the syntax:\n# dev_name: instance(with full path)\n')
        f.write('# Alternatively local spock names may also be used\n')
        f.write('# Comment lines begin with hashtag and empty lines are discarded.\n\n')
        f.write('# horizontal motor\n')
        f.write('mot_hor: \n')
        f.write('# vertical motor\n')
        f.write('mot_ver: \n')
        f.write('# omega rotation motor\n')
        f.write('mot_rot: \n')
        f.write('# far field detector y motor\n')
        f.write('ff_det_mot_hor: \n')
        f.write('# far field detector z motor\n')
        f.write('ff_det_mot_ver: \n')
        f.write('# auxiliary devices (e.g. slits) for logging (spock names separated by spaces):\n')
        f.write('aux: ')


        



class Measurement:
    '''
    Class to define the measurement parameters:
        
        moveable devices for y, z, and omega
            -> this would be a nested dict with the names in this module as keys 
            and a subdir containing the device_name and the device instance itself
        it can not handle counters yet
        
        detectors
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
        self.create_logfile()
        # make nested dict out of the device dict
        for k in devices['movables'].keys():
            self.devs[k] = {'name': devices['movables'][k], 'dev': self.import_device(devices['movables'][k])}



    
    def read_config_file(self, config_file):
        '''
        reads in the given configuration file
        it returns a nested dictionary with 'moveables', 'counters'...
        '''
        devices = {'movables': {}, 'counters': {}, 'auxiliary': {}}
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
                if key.partition('_')[0] == 'cou': # counter device
                    devices['counters'][key] = value
                if all(elem in key.split('_') for elem in ['det', 'mot']): # detector motor device
                    devices['movables'][key] = value
                if 'aux' in key:
                    for v in value.split():
                        devices['auxiliary'][v] = v


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
            self.write_log('%s\nWarning! %s imported successfully, but does not respond.' % (e, dev_name))
        if DEBUG: print('%s device imported' % dev_name)
        if DEBUG: self.write_log('%s device imported' % dev_name)
        return dev

    
    def create_directory(self):
        if self.measurement_path is not None:
            if self.measurement_path[-1] == '/': self.measurement_path = self.measurement_path[:-1]
            if self.measurement_path[0] != '/':
                self.measurement_path = '/gpfs/current/raw' + os.sep + self.measurement_path
            if os.path.exists(self.measurement_path):
                raise ValueError(SE+'Directory exists'+EE)
        else: raise ValueError(SE+'Directory not given'+EE)
        try:
            os.mkdir(self.measurement_path)
            print(SI+'Measurement dir: %s'%(self.measurement_path)+EE)
        except:
            raise ValueError(SE+'Cannot create directory'+EE)
        self.varexdir = self.measurement_path+os.sep+'PE'
        os.mkdir(self.varexdir)
        self.lambdadir = self.measurement_path+os.sep+'lambda'
        os.mkdir(self.lambdadir)

    
    def temp_setup_detector_folders(self):
        self.varex = PT.DeviceProxy('hasep21eh3:10000/p21/MultiXRDTango/hasep21perk02')
        self.Lambda = PT.DeviceProxy('hasmlmbd02:10000/petra3/lambda/01')
        self.varex.AllStopAcq()
        self.Lambda.StopAcq()
        time.sleep(0.2)
        
        self.varex.FileDir1 = self.varexdir.replace('/gpfs/', 't:/')
        self.Lambda.SaveFilePath = self.lambdadir

    def create_logfile(self):
        self.logfile = self.measurement_path + 'log.log'
        with open(self.logfile, 'w') as log:
            log.write('Logfile for single grain diffraction created: %f, %s\n' % (time.time(), time.asctime()))


    def write_log(self, mess, time=True):
        with open(self.logfile, 'a') as log:
            if time:
                log.write('%f, %s: ' %(time.time(), time.asctime()))
            log.write(mess+'\n')


    def log_positions(self):
        with open(self.logfile, 'a') as log:
            log.write('%f, %s: ' %(time.time(), time.asctime()))
            for k,v in self.devs['movables'].item():
                log.write('%s: %.3f' % (k, v.position))
            log.write(' ')
            for k,v in self.devs['auxiliary'].item():
                log.write('%s: %.3f' % (k, v.position))
            log.write('\n')


    def _cleanup(self, really=False):
        import shutil
        if really:
            try:
                shutil.rmtree(self.measurement_path)
            except OSError as e:
                print("Error: %s : %s" % (self.measurement_path, e.strerror))
            if DEBUG: print('Measurement directory deleted')


    def create_database(self):
        pass



'''
general class for grain Candidates
the actual grain class could be an inheritance from the candidates class
'''



class Grain(object):
    '''
    Class to hold grain properties
    M - is the instance of the measurement class, defining the devices needed
    '''

    instances = []
    
    def __init__(self, M, name=None):
        self.name=name
        self.__class__.instances.append(self.name)
        self.M = M
        self._ypos = [self.M.devs['mot_hor']['dev'].position]
        self._zpos = [self.M.devs['mot_ver']['dev'].position]
        self._rotpos = [self.M.devs['mot_rot']['dev'].position]
        self._dethpos = [self.M.devs['ff_det_mot_hor']['dev'].position]
        self._detvpos = [self.M.devs['ff_det_mot_ver']['dev'].position]
        
        self.roi = None
        self.Lroi =None
        
        # some magic to get the spock names of the moveable devices so that later they can be used by spock macros like mv
        self.moveable_spock_names = _func._getMoveableSpockNames()
        self.inv_moveable_spock_names = {v: k for k, v in self.moveable_spock_names.items()}
        self.mot_hor = self.inv_moveable_spock_names[self.M.devs['mot_hor']['dev'].dev_name()]
        self.mot_ver = self.inv_moveable_spock_names[self.M.devs['mot_ver']['dev'].dev_name()]
        self.mot_rot = self.inv_moveable_spock_names[self.M.devs['mot_rot']['dev'].dev_name()]
        self.detmot_hor = self.inv_moveable_spock_names[self.M.devs['ff_det_mot_hor']['dev'].dev_name()]
        self.detmot_ver = self.inv_moveable_spock_names[self.M.devs['ff_det_mot_ver']['dev'].dev_name()]

        if DEBUG: print(self.mot_hor, self.mot_ver, self.mot_rot, self.detmot_hor, self.detmot_ver)
        self.spock = get_ipython()


    def new_pos(self, ypos=None, zpos=None, Opos=None):
        self._ypos.append(self.M.devs['mot_hor']['dev'].position)
        self._zpos.append(self.M.devs['mot_ver']['dev'].position)
        self._rotpos.append(self.M.devs['mot_rot']['dev'].position)
        self._dethpos.append(self.M.devs['ff_det_mot_hor']['dev'].position)
        self._detvpos.append(self.M.devs['ff_det_mot_ver']['dev'].position)
        self.M.write_log('New position defined for grain: %s' % self.name)
        self.M.log_positions()


    def current_pos(self):
        return [self._ypos[-1], self._zpos[-1], self._rotpos[-1], self._dethpos[-1], self._detvpos[-1]]


    def all_pos(self):
        return [self._ypos, self._zpos, self._rotpos, self._dethpos, self._detvpos]
        

    def goto_grain_center(self):
        #cp = self.current_pos()
        #command = 'umv %s %f %s %f %s %f' % \
        #                 (self.mot_hor, self.current_pos()[0],
        #                  self.mot_ver, self.current_pos()[1],
        #                  self.mot_rot, self.current_pos()[2])
        #if DEBUG: print(command)
        self.spock.magic('umv %s %f %s %f %s %f %s %f %s %f' %
                         (self.mot_hor, self.current_pos()[0],
                          self.mot_ver, self.current_pos()[1],
                          self.mot_rot, self.current_pos()[2],
                          self.detmot_hor, self.current_pos()[3],
                          self.detmot_ver, self.current_pos()[4]))

    def set_slit_size(self, posdict):
        c = 'umv '
        for m,p in posdict.item():
            c.append('%s %.3f ' %(m,p))
        self.spock.magic(c)
        self.M.write_log('Slits set to: %s' % posdict)

    def centerH(self, start, end, NoSteps, rotstart, rotend, exposure=DEFEXPTIME, channel=1, auto=False):
        if channel == 1:
            self.M.write_log('Horizontal centering with Varex on grain: %s' % self.name)
        if channel == 3:
            self.M.write_log('Horizontal centering with Lambda on grain: %s' % self.name)
        # move slits:
        self.set_slit_size(VERTICALBEAM)
        
        if channel == 3:
            self.M.Lambda.StopAcq()
        elif channel == 1:
            self.M.varex.AllStopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True
        time.sleep(0.1)
        if channel == 1:
            if not self.roi:
                positions, res, self.roi = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure, channel=channel, roi=self.roi)
            else:
                positions, res, _ = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.roi)
        if channel == 3:
            if not self.Lroi:
                positions, res, self.Lroi = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.Lroi)
            if self.Lroi:
                positions, res, _ = _func.center('h', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                    channel=channel, roi=self.Lroi)

        self.M.write_log('Selected roi %s' % self.roi, time=False)
        self.M.write_log('Results: center %f fwhm %f' % (res['cen'], res['fwhm']))
        if auto:
            self.spock.magic('umv %s %f'%(self.mot_hor, res['cen']))
            self.M.write_log('Automatically moved to the center.')

        #self.new_pos()


    def centerV(self, start, end, NoSteps, rotstart, rotend, exposure=DEFEXPTIME, channel=1, auto=False):
        if channel == 1:
            self.M.write_log('Vertical centering with Varex on grain: %s' % self.name)
        if channel == 3:
            self.M.write_log('Vertical centering with Lambda on grain: %s' % self.name)
        # move slits:
        self.set_slit_size(HORIZONTALBEAM)

        if channel == 3:
            self.M.Lambda.StopAcq()
        elif channel == 1:
            self.M.varex.AllStopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True
        time.sleep(0.1)
        if channel == 1:
            if not self.roi:
                positions, res, self.roi, fio = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure, channel=channel, roi=self.roi)
            else:
                positions, res, _, fio = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.roi)
        if channel == 3:
            if not self.Lroi:
                positions, res, self.Lroi, fio = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                   channel=channel, roi=self.Lroi)
            else:
                positions, res, _, fio = _func.center('v', start, end, NoSteps, rotstart, rotend, exposure=exposure,
                                                    channel=channel, roi=self.Lroi)

        self.M.write_log('Logfile: %s' % fio)
        self.M.write_log('Selected roi %s' % self.roi, time=False)
        self.M.write_log('Results: center %f fwhm %f' % (res['cen'], res['fwhm']))
        if auto:
            self.spock.magic('umv %s %f'%(self.mot_ver, res['cen']))
            self.M.write_log('Automatically moved to the center.')
        #self.new_pos()

    def centerO(self, start, end, NoSteps, exposure=DEFEXPTIME, channel=1, auto=False):
        if channel == 1:
            self.M.write_log('Angular centering with Varex on grain: %s' % self.name)
        if channel == 3:
            self.M.write_log('Angular centering with Lambda on grain: %s' % self.name)
        # move slits:
        self.set_slit_size(LARGEBEAM)
            
        if channel == 3:
            self.M.Lambda.StopAcq()
        elif channel == 1:
            self.M.varex.AllStopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True
        time.sleep(0.1)

        if channel == 1:
            if not self.roi:
                positions, res, self.roi, fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.roi)
            else:
                positions, res, _, fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.roi)
        if channel == 3:
            if not self.Lroi:
                positions, res, self.Lroi, fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.Lroi)
            else:
                positions, res, _, fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.Lroi)

        self.M.write_log('Logfile: %s' % fio)
        self.M.write_log('Selected roi %s' % self.roi, time=False)
        self.M.write_log('Results: center %f fwhm %f' % (res['cen'], res['fwhm']))
        if auto:
            self.spock.magic('umv %s %f'%(self.mot_rot, res['cen']))
            self.M.write_log('Automatically moved to the center.')
        #self.new_pos()


    def recordMap(self, start, end, NoSteps, exposure=DEFEXPTIME, channel=1):
        pass


    def redef_ROI(self, imsource, channel=1):
        if channel == 1:
            self.roi, _ = _func.explorer(imsource)
            self.M.write_log('Varex ROI redefined: %s for grain %s' % (self.roi, self.name))
        if channel == 3:
            self.Lroi, _ = _func.explorer(imsource)
            self.M.write_log('Lambda ROI redefined: %s for grain %s' % (self.Lroi, self.name))

    def showMap(self, fiofile):
        _func.showMap(fiofile, 3, self.Lroi)

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        

        
        
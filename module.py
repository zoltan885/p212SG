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

try:
    import PyTango as PT
    import HasyUtils as HU
except ImportError:
    print('Could not import PyTango & HasyUtils')
import sys, os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.patches import Rectangle
import time

from PIL import Image

import _func
from matplotlib.backends.backend_pdf import PdfPages

from collections import OrderedDict
import json
import yaml
import shutil


SE = '\033[41m'
SI = '\033[44m'
EE = '\033[0m'


DEFEXPTIME = 0.5

HORIZONTALBEAM = {'eh3st': 0.025, 'eh3sb': 0.025, 'eh3so': 0.15, 'eh3si': 0.15}
VERTICALBEAM   = {'eh3st': 0.15, 'eh3sb': 0.15, 'eh3so': 0.025, 'eh3si': 0.025}
LARGEBEAM      = {'eh3st': 0.15, 'eh3sb': 0.15, 'eh3so': 0.15, 'eh3si': 0.15}



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
        f.write('mot_hor: idty2\n')
        f.write('# vertical motor\n')
        f.write('mot_ver: idtz2\n')
        f.write('# omega rotation motor\n')
        f.write('mot_rot: idrz1\n')
        f.write('# far field detector y motor\n')
        f.write('mot_ff_det_hor: p2ty\n')
        f.write('# far field detector z motor\n')
        f.write('mot_ff_det_ver: p2tz\n')
        f.write('# top slit\n')
        f.write('mot_st: eh3st\n')
        f.write('# bottom slit\n')
        f.write('mot_sb: eh3sb\n')
        f.write('# inboard slit\n')
        f.write('mot_si: eh3si\n')
        f.write('# outboard slit\n')
        f.write('mot_so: eh3so\n')
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
    def __init__(self, config_file, path, load=False):
        devices = self.read_config_file(config_file)
        if DEBUG:
            print(devices)
        self.devs_mov = {}
        self.devs_aux = {}
        self.measurement_path = path
        self.logF = path+'/log'
        self.logger = logger(self.logF)
        if load:
            self.load_directory()
        else:
            self.create_directory()
        #self.temp_setup_detector_folders()
        self.create_logfile()

        self.detChannels = {'1': 'Perkin', '2': 'Eiger', '3': 'Lambda'}

        # make nested dict out of the device dict
        for k in devices['movables'].keys():
            self.devs_mov[k] = {'name': devices['movables'][k], 'dev': self.import_device(devices['movables'][k])}
        for k in devices['auxiliary'].keys():
            self.devs_aux[k] = {'name': devices['auxiliary'][k], 'dev': self.import_device(devices['auxiliary'][k])}
        self.spock = get_ipython()
        print('Init finished')



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


        print('Config file successfully loaded')
        return devices


    def import_device(self, dev_name):
        '''
        import a single device
        dev_name is the instance name with full path or alternatively a local (same host!) spock name
        '''
        if '/' not in dev_name:
            sn = _func._getMovableSpockNames()
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
        if not os.path.isabs(self.measurement_path):
            self.measurement_path = os.path.join('/gpfs/current/raw', self.measurement_path)
#        if self.measurement_path is not None:
#            if self.measurement_path[-1] == '/': self.measurement_path = self.measurement_path[:-1]
#            if self.measurement_path[0] != '/':
#                self.measurement_path = '/gpfs/current/raw' + os.sep + self.measurement_path
        if os.path.exists(self.measurement_path):
            print(SE+'Directory exists! Please use load=True option when initializing the measurement.'+EE)
            print('Object not instantiated')
            raise ValueError
        try:
            os.makedirs(self.measurement_path)
            print(SI+'Measurement dir: %s'%(self.measurement_path)+EE)
        except:
            print(SE+'Cannot create directory'+EE)
            raise
        self.varexdir = os.path.join(self.measurement_path, 'Varex')
        os.makedirs(self.varexdir)
        # TEMPORARY: put paths to folders in the environment
        #HU.setEnv('PE_c_folder', '%s'%self.varexdir.replace('/gpfs/', 't:/'))
        #self.lambdadir = self.measurement_path+os.sep+'lambda'
        #os.mkdir(self.lambdadir)
        #HU.setEnv('Lambda_hr_folder', self.lambdadir)
        self.eigerdir = os.path.join(self.measurement_path, 'Eiger')
        os.makedirs(self.eigerdir)

        #os.mkdir(self.measurement_path+os.sep+'DIC')
        #os.mkdir(self.measurement_path+os.sep+'LPA')
        #HU.setEnv('LPA_folder', self.measurement_path.replace('/gpfs/', 't:/')+os.sep+'LPA')
        #HU.setEnv('DIC_folder', self.measurement_path+os.sep+'DIC')

    def load_directory(self):
        if not os.path.isabs(self.measurement_path):
            self.measurement_path = os.path.join('/gpfs/current/raw', self.measurement_path)
        if not os.path.exists(self.measurement_path):
            print(SE+'Directory does not exist'+EE)
            raise Exception

        with open(self.logF+'.json', 'r') as l:
            grains = json.load(l)
        for g in grains.keys():
            globals()[g] = Grain(g, self.logger)


    def temp_setup_detector_folders(self):
        self.varex = PT.DeviceProxy('hasep21eh3:10000/p21/Varex/3')
        self.Lambda = PT.DeviceProxy('hasmlmbd02:10000/petra3/lambda/01')

        self.varex.StopAcq()
        self.Lambda.StopAcq()
        time.sleep(0.2)
        self.varex.FileDir = self.varexdir.replace('/gpfs/', 't:/')
        self.varex.FileName = 'PE1_%I.tif'
        self.Lambda.SaveFilePath = self.lambdadir




    def create_logfile(self):
        self.logfile = os.path.join(self.measurement_path, 'log.log')
        with open(self.logfile, 'w') as log:
            log.write('%f, %s: logfile for single grain diffraction created\n' % (time.time(), time.asctime()))


    def write_log(self, mess, addtime=True, nonl=False):
        with open(self.logfile, 'a') as log:
            if addtime:
                log.write('%f, %s: ' %(time.time(), time.asctime()))
            if nonl:
                log.write(mess+' ')
            else:
                log.write(mess+'\n')


    def log_positions(self, addtime=True):
        with open(self.logfile, 'a') as log:
            if addtime:
                log.write('%f, %s: ' %(time.time(), time.asctime()))
            for k,v in self.devs_mov.items():
                log.write('%s: %.3f ' % (k, v['dev'].position))
            for k,v in self.devs_aux.items():
                log.write('%s: %.3f ' % (k, v['dev'].position))
            log.write('\n')


    def comment(self, comm):
        self.write_log('USER: ' + comm)


    def create_database(self):
        pass


    def set_slit_size(self, posdict):
        c = 'umv '
        for m,p in posdict.items():
            c = c + ('%s %.3f ' %(m,p))
        self.spock.magic(c)
        self.write_log('Slits set to: %s' % posdict)

'''
general class for grain Candidates
the actual grain class could be an inheritance from the candidates class
'''

class logger(object):
    '''
    logger class for grain attributes
    log the results into a json file
    '''
    def __init__(self, fname):
        self.j = fname+'.json'
        self.y = fname+'.yml'
        #self.attrs = ['timestamp', 'direction', 'detector', 'slit', 'scanID', 'ROIs', 'intensity', 'fitpars', 'positions']
        self.objList = {}  # dict holding the registered classes

    def register(self, obj):
        self.objList[obj.name] = obj

    def _backup(self):
        if os.path.exists(self.j):
            shutil.copy2(self.j, self.j+'_bak')
        if os.path.exists(self.y):
            shutil.copy2(self.y, self.y+'_bak')

    def logNow(self):
        self._backup()
        dumpDict = {}
        for g,inst in self.objList.items():
            dumpDict[g] = {}
            if hasattr(inst, 'logAttrs'):
                for a in inst.logAttrs:
                    try:
                        dumpDict[g][a] = eval('inst.%s' % a)
                    except:
                        dumpDict[g][a] = ['?',]
            else:  # nothing to log
                if DEBUG:
                    print(SI+'%s is registered for logging, but there is nothing to log' % inst.__repr__()+EE)

        with open(self.j, 'w') as jf:
            json.dump(dumpDict, jf)
        with open(self.y, 'w') as yf:
            yaml.dump(dumpDict, yf)
        return dumpDict


class TestGrain(object):
    def __init__(self, name, logger):
        self.name = name
        logger.register(self)
        self.logAttrs = ['timestamp', 'action', 'direction', 'detector', 'slit', 'scanID', 'ROIs', 'integRes', 'fitpars', 'positions']
        self.timestamp = [time.asctime()]
        self.action = ['centering']
        self.direction = ['V',]
        self.detector = ['eiger',]
        self.slit = [{'top': 11, 'bottom': 22, 'inboard': 33, 'outboard': 44},]
        self.scanID = [153,]
        self.ROIs = [{'eiger': (2341, 4232, 231, 2134)}, ]
        self.integRes = [([-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6],[1,2,3,4,5,6,7,6,5,4,23,2,1]),]
        self.fitpars = [{'s': 12, 'b': 423.2},]
        self.positions = [{'y': 0.12, 'z': -1.2, 'o': 213.84},]


#l = logger('/home/hegedues/Documents/snippets/crap')
#print(vars(l))
#g1 = TestGrain('grain1', l)
#g3 = TestGrain('grain22', l)
#print(vars(l))
#l.logNow()



class Grain(object):
    '''
    Class to hold grain properties
    M - is the instance of the measurement class, defining the devices needed
    '''

    def __init__(self, M, name=None, grdct=None):
        self.name=name
        self.M = M
        self.M.logger.register(self)
        self._ypos = [self.M.devs_mov['mot_hor']['dev'].position]
        self._zpos = [self.M.devs_mov['mot_ver']['dev'].position]
        self._rotpos = [self.M.devs_mov['mot_rot']['dev'].position]
        self._dethpos = [self.M.devs_mov['mot_ff_det_hor']['dev'].position]
        self._detvpos = [self.M.devs_mov['mot_ff_det_ver']['dev'].position]



        if grdct is not None:
            self._loadGrainFromFile(grdct)
        else:
            # setup logging attributes
            self.positions = []
            self._appendPos()
            self.timestamp = [time.asctime()]
            self.action = ['initGrain']
            self.direction = ['?']
            self.detector = ['?']
            self.slit = []
            self._appendSlitPos()
            self.scanID = []
            self.ROIs = [('?',)]
            self.integRes = [['?'],]
            self.fitpars = [{'?': '?'}]
            self.logAttrs = ['timestamp', 'direction', 'detector', 'slit', 'scanID', 'ROIs', 'integRes', 'fitpars', 'positions']
            self.M.logger.logNow()


        # self.roi  = None
        # self.Lroi = None
        # current rois:
        self.cROIs = {}
        for ch,d in self.M.detChannels.items():
            self.cROIs[ch] = None


        # some magic to get the spock names of the moveable devices so that later they can be used by spock macros like mv
        self.moveable_spock_names = _func._getMovableSpockNames()
        self.inv_moveable_spock_names = {v: k for k, v in self.moveable_spock_names.items()}
        self.mot_hor = self.inv_moveable_spock_names[self.M.devs_mov['mot_hor']['dev'].dev_name()]
        self.mot_ver = self.inv_moveable_spock_names[self.M.devs_mov['mot_ver']['dev'].dev_name()]
        self.mot_rot = self.inv_moveable_spock_names[self.M.devs_mov['mot_rot']['dev'].dev_name()]
        self.detmot_hor = self.inv_moveable_spock_names[self.M.devs_mov['mot_ff_det_hor']['dev'].dev_name()]
        self.detmot_ver = self.inv_moveable_spock_names[self.M.devs_mov['mot_ff_det_ver']['dev'].dev_name()]

        self.M.write_log('"%s" grain object defined with positions:' % (self.name), nonl=True)
        self.M.log_positions(addtime=False)

        if DEBUG: print(self.mot_hor, self.mot_ver, self.mot_rot, self.detmot_hor, self.detmot_ver)
        self.spock = get_ipython()

    def _appendPos(self):
        '''
        Append the current motor positions to the self.positions list
        '''
        dct = {'y': self.M.devs_mov['mot_hor']['dev'].position,
              'z': self.M.devs_mov['mot_ver']['dev'].position,
              'o': self.M.devs_mov['mot_rot']['dev'].position,
              'det_y': self.M.devs_mov['mot_ff_det_hor']['dev'].position,
              'det_z': self.M.devs_mov['mot_ff_det_ver']['dev'].position}
        self.positions.append(dct)

    def _appendSlitPos(self):
        '''
        Append the current slit positions to the self.slit list
        '''
        dct = {'top': self.M.devs_mov['mot_st']['dev'].position,
               'bottom': self.M.devs_mov['mot_sb']['dev'].position,
               'inboard': self.M.devs_mov['mot_si']['dev'].position,
               'outboard': self.M.devs_mov['mot_so']['dev'].position}
        self.slit.append(dct)

    def _appendROI(self):
        '''
        Append the curent ROIs for all detectors defined in the measurement
        '''
        dct = {}
        for ch,d in self.M.detChannels.items():
            dct[d] = self.cROIs[str(ch)]
        self.ROIs.append(dct)

    def getScanID(self):
        '''
        Gets the scan ID of the !last! scan
        '''
        sid = int(HU.getEnv('ScanID')) - 1
        return sid

    def _loadGrainFromFile(self, grdct):
        self.logAttrs = ['timestamp', 'direction', 'detector', 'slit', 'scanID', 'ROIs', 'integRes', 'fitpars', 'positions']
        for attr in self.logAttrs:
            if attr not in grdct.keys():
                raise Exception('%s could not be found in the yaml/json file' % attr)
        for k,v in grdct.items():
            exec("self.%s = grdct['%s']" % (k, k))
#        self.positions = grdct['positions']
#        self.timestamp = grdct['timestamp']
#        self.action = grdct['action']
#        self.direction = grdct['direction']
#        self.detector = grdct['detector']
#        self.slit = grdct['slit']
#        self.scanID = grdct['scanID']
#        self.ROIs = grdct['ROIs']
#        self.integRes = grdct['integRes']
#        self.fitpars = grdct['fitpars']
#        self.logAttrs = ['timestamp', 'direction', 'detector', 'slit', 'scanID', 'ROIs', 'integRes', 'fitpars', 'positions']


    # def new_pos(self, ypos=None, zpos=None, Opos=None):
    #     self._ypos.append(self.M.devs_mov['mot_hor']['dev'].position)
    #     self._zpos.append(self.M.devs_mov['mot_ver']['dev'].position)
    #     self._rotpos.append(self.M.devs_mov['mot_rot']['dev'].position)
    #     self._dethpos.append(self.M.devs_mov['mot_ff_det_hor']['dev'].position)
    #     self._detvpos.append(self.M.devs_mov['mot_ff_det_ver']['dev'].position)
    #     self.M.write_log('New position defined for "%s"' % self.name)
    #     self.M.log_positions()


    # def current_pos(self):
    #     return [self._ypos[-1], self._zpos[-1], self._rotpos[-1], self._dethpos[-1], self._detvpos[-1]]
    def current_pos(self):
        return self.positions[-1]

    # def all_pos(self):
    #     return [self._ypos, self._zpos, self._rotpos, self._dethpos, self._detvpos]
    def all_pos(self):
        return self.positions


    # def goto_grain_center(self, Lambda=False):
    #     #cp = self.current_pos()
    #     #command = 'umv %s %f %s %f %s %f' % \
    #     #                 (self.mot_hor, self.current_pos()[0],
    #     #                  self.mot_ver, self.current_pos()[1],
    #     #                  self.mot_rot, self.current_pos()[2])
    #     #if DEBUG: print(command)
    #     if Lambda:
    #         self.spock.magic('umv %s %f %s %f %s %f %s %f %s %f' %
    #                      (self.mot_hor, self.current_pos()[0],
    #                       self.mot_ver, self.current_pos()[1],
    #                       self.mot_rot, self.current_pos()[2],
    #                       self.detmot_hor, self.current_pos()[3],
    #                       self.detmot_ver, self.current_pos()[4]))
    #     else:
    #         self.spock.magic('umv %s %f %s %f %s %f' %
    #                      (self.mot_hor, self.current_pos()[0],
    #                       self.mot_ver, self.current_pos()[1],
    #                       self.mot_rot, self.current_pos()[2]))
    def goto_grain_center(self, farDet=False, careful=True):
        cp = self.current_pos()
        command = 'umv %s %f %s %f %s %f' % (self.mot_hor, cp['y'], self.mot_ver, cp['z'], self.mot_rot, cp['o'])
        if farDet:
            command.append(' %s %f %s %f' % (self.detmot_hor, cp['det_y'], self.detmot_ver, cp['det_z']))
        if DEBUG:
            print(command)
        if careful:
            dct = {'y': self.M.devs_mov['mot_hor']['dev'].position,
              'z': self.M.devs_mov['mot_ver']['dev'].position,
              'o': self.M.devs_mov['mot_rot']['dev'].position,
              'det_y': self.M.devs_mov['mot_ff_det_hor']['dev'].position,
              'det_z': self.M.devs_mov['mot_ff_det_ver']['dev'].position}
            print('Moving from: %s' % dct)
        self.spock.magic(command)


    def centerH(self, start, end, NoSteps, rotstart, rotend, exposure=DEFEXPTIME, channel=2, auto=False, log=True):
        if channel == 1:
            self.M.write_log('Horizontal centering with Varex on grain: %s' % self.name)
        if channel == 2:
            self.M.write_log('Horizontal centering with Eiger on grain: %s' % self.name)
        if channel == 3:
            self.M.write_log('Horizontal centering with Lambda on grain: %s' % self.name)
        # move slits:
        self.M.set_slit_size(VERTICALBEAM)

        if channel == 3:
            self.M.Lambda.StopAcq()
            time.sleep(0.1)
            self.M.Lambda.SaveAllImages = True
        elif channel == 2:
            self.spock.magic('_eigerLive off')
        elif channel == 1:
            pass
        time.sleep(0.1)

        positions, res, self.cROIs[str(channel)], fio = _func.center('h', start, end, NoSteps+1, rotstart, rotend,
                                                                exposure=exposure, channel=channel, roi=self.cROIs[str(channel)])


        self.M.write_log('Logfile: %s' % fio)
        self.M.write_log('Selected roi %s' % self.cROIs[str(channel)], addtime=False)
        self.M.write_log('Results: center %f fwhm %f' % (res['cen'], res['fwhm']))
        if res['moveto']:
            self.spock.magic('umv idty2 %.3f' % res['cen'])

        if auto:
            self.spock.magic('umv %s %f'%(self.mot_hor, res['cen']))
            self.M.write_log('Automatically moved to the center.')

        if log:
            self._appendPos()
            self.timestamp.append(time.asctime())
            self.action.append('centerH')
            self.direction.append('H')
            self.detector.append(self.M.detChannels[str(channel)])
            self._appendSlitPos()
            self.scanID.append(self.getScanID())
            self._appendROI()
            self.integRes.append({'pos': list(positions), 'int': ['?']})  # TODO: expose the intensity?
            self.fitpars.append({'cen': res['cen'], 'fwhm': res['fwhm']})
            self.M.logger.logNow()

        #self.new_pos()


    def centerV(self, start, end, NoSteps, rotstart, rotend, exposure=DEFEXPTIME, channel=2, auto=False, log=True):
        if channel == 1:
            self.M.write_log('Vertical centering with Varex on grain: %s' % self.name)
        if channel == 2:
            self.M.write_log('Vertical centering with Eiger on grain: %s' % self.name)
        if channel == 3:
            self.M.write_log('Vertical centering with Lambda on grain: %s' % self.name)
        # move slits:
        self.M.set_slit_size(HORIZONTALBEAM)

        if channel == 3:
            self.M.Lambda.StopAcq()
            time.sleep(0.1)
            self.M.Lambda.SaveAllImages = True
        elif channel == 2:
            self.spock.magic('_eigerLive off')
        elif channel == 1:
            pass
        time.sleep(0.1)

        positions, res, self.cROIs[str(channel)], fio = _func.center('v', start, end, NoSteps+1, rotstart, rotend,
                                                                exposure=exposure, channel=channel, roi=self.cROIs[str(channel)])


        self.M.write_log('Logfile: %s' % fio)
        self.M.write_log('Selected roi %s' % self.cROIs[str(channel)], addtime=False)
        self.M.write_log('Results: center %f fwhm %f' % (res['cen'], res['fwhm']))
        if res['moveto']:
            self.spock.magic('umv idtz2 %.3f' % res['cen'])

        if auto:
            self.spock.magic('umv %s %f'%(self.mot_hor, res['cen']))
            self.M.write_log('Automatically moved to the center.')

        if log:
            self._appendPos()
            self.timestamp.append(time.asctime())
            self.action.append('centerH')
            self.direction.append('H')
            self.detector.append(self.M.detChannels[str(channel)])
            self._appendSlitPos()
            self.scanID.append(self.getScanID())
            self._appendROI()
            self.integRes.append({'pos': list(positions), 'int': ['?']})  # TODO: expose the intensity?
            self.fitpars.append({'cen': res['cen'], 'fwhm': res['fwhm']})
            self.M.logger.logNow()

        #self.new_pos()

    def centerO(self, start, end, NoSteps, exposure=DEFEXPTIME, channel=2, auto=False, mode=24, log=True):
        if channel == 1:
            self.M.write_log('Angular centering with Varex on grain: %s' % self.name)
        if channel == 2:
            self.M.write_log('Angular centering with Eiger on grain: %s' % self.name)
        if channel == 3:
            self.M.write_log('Angular centering with Lambda on grain: %s' % self.name)
        # move slits:
        self.M.set_slit_size(LARGEBEAM)

        if channel == 3:
            self.M.Lambda.StopAcq()
            time.sleep(0.1)
            self.M.Lambda.SaveAllImages = True
        elif channel == 2:
            self.spock.magic('_eigerLive off')
        elif channel == 1:
            pass
        time.sleep(0.1)

        positions, res, self.cROIs[str(channel)], fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.cROIs[str(channel)])


        self.M.write_log('Logfile: %s' % fio)
        self.M.write_log('Selected roi %s' % self.cROIs[str(channel)], addtime=False)
        self.M.write_log('Results: center %f fwhm %f' % (res['cen'], res['fwhm']))
        print(res['moveto'])
        if res['moveto']:
            self.spock.magic('umv idrz1 %.3f' % res['cen'])

        if auto:
            self.spock.magic('umv %s %f'%(self.mot_rot, res['cen']))
            self.M.write_log('Automatically moved to the center.')

        if logger is not None:
            self._appendPos()
            self.timestamp.append(time.asctime())
            self.action.append('centerO')
            self.direction.append('O')
            self.detector.append(self.M.detChannels[str(channel)])
            self._appendSlitPos()
            self.scanID.append(self.getScanID())
            self._appendROI()
            self.integRes.append({'pos': list(positions), 'int': ['?']})  # TODO: expose the intensity?
            self.fitpars.append({'cen': res['cen'], 'fwhm': res['fwhm']})
            self.M.logger.logNow()

        #self.new_pos()

    def recenter(self, imsource=None, channel=2):
        if imsource is not None:
            self.cROIs[str(channel)], _ = _func.explorer(imsource)
            self.M.write_log('%s roi redefined: %s for grain %s' % (self.M.detChannels[str(channel)], str(self.cROIs[str(channel)]), self.name))
        else:
            print(SE+'No image source defined!'+EE)

        # rewrite _fioparser such that it returns a dict or an object with the attribute command, parse the command and figure out the motor name from there!
        #res = _func.fitGauss(imsource, self.cROIs[str(channel)], motor=mot)




        if logger is not None:
            self._appendPos()
            self.timestamp.append(time.asctime())
            self.action.append('recenter')
            self.direction.append('?')
            self.detector.append(self.M.detChannels[str(channel)])
            self._appendSlitPos()
            self.scanID.append('?')
            self._appendROI()
            self.integRes.append((['?'], ['?']))
            self.fitpars.append({'cen': '?', 'fwhm': '?'})
            self.M.logger.logNow()


    def recordMap(self, start, end, NoSteps, exposure=None, channel=2):
        if exposure is None:
            raise ValueError('Exposure time not given')
        self.M.set_slit_size(LARGEBEAM)
        self.M.Lambda.StopAcq()
        time.sleep(0.1)
        self.M.Lambda.SaveAllImages = True

        positions, res, self.cROIs[str(channel)], fio = _func.centerOmega(start, end, NoSteps, exposure=exposure,
                                                                     channel=channel, roi=self.cROIs[str(channel)])
        # if not self.Lroi:
        #     positions, res, self.Lroi, fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.Lroi)
        # else:
        #     positions, res, _, fio = _func.centerOmega(start, end, NoSteps, exposure=exposure, channel=channel, roi=self.Lroi)

        if logger is not None:
            self._appendPos()
            self.timestamp.append(time.asctime())
            self.action.append('recordMap')
            self.direction.append('?')
            self.detector.append(self.M.detChannels[str(channel)])
            self._appendSlitPos()
            self.scanID.append(self.getScanID())
            self._appendROI()
            self.integRes.append((['?'], ['?']))
            self.fitpars.append({'cen': '?', 'fwhm': '?'})
            self.M.logger.logNow()



    def redef_ROI(self, imsource=None, channel=2):
        '''
        TODO: this should watch out if the right channel is given,
        currently it can not, because the explorer does not report which detector it used
        '''
        if imsource is not None:
            self.cROIs[str(channel)], _ = _func.explorer(imsource)
            self.M.write_log('%s roi redefined: %s for grain %s' % (self.M.detChannels[str(channel)], str(self.cROIs[str(channel)]), self.name))
            # if channel == 1:
            #     self.roi, _ = _func.explorer(imsource)
            #     self.M.write_log('Varex ROI redefined: %s for grain %s' % (self.roi, self.name))
            # if channel == 3:
            #     self.Lroi, _ = _func.explorer(imsource)
            #     self.M.write_log('Lambda ROI redefined: %s for grain %s' % (self.Lroi, self.name))
        else:
            print(SE+'No image source defined!'+EE)
            # if channel == 1:
            #     self.roi = None
            #     self.M.write_log('Varex ROI deleted')
            # if channel == 3:
            #     self.Lroi = None
            #     self.M.write_log('Lambda ROI deleted')

        if logger is not None:
            self._appendPos()
            self.timestamp.append(time.asctime())
            self.action.append('redefROI')
            self.direction.append('?')
            self.detector.append(self.M.detChannels[str(channel)])
            self._appendSlitPos()
            self.scanID.append('?')
            self._appendROI()
            self.integRes.append((['?'], ['?']))
            self.fitpars.append({'cen': '?', 'fwhm': '?'})
            self.M.logger.logNow()



    def showMap(self, fiofile, maxint, channel=2):
        _func.showMap(fiofile, roi=self.cROIs[str(channel)], maxint=maxint)



















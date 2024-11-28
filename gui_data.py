import numpy as np
import lmfit
import time
from functools import partial
import h5py
import fabio
from collections import namedtuple
import json
import yaml
import os
import tempfile
from copy import copy
#from jsondiff import diff
import numpy.ma as maskedarray
from pyFAI import detectors

import _fiosupport
import SGmath



# https://glinteco.com/en/post/tips-python-dotdict-class/
class DotDict(dict):
    """DotDict class allows accessing dictionary keys as attributes."""
    def __init__(self, *args, **kwargs):
        super(DotDict, self).__init__(*args, **kwargs)

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        try:
            del self[item]
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")

# such a tuple records its creation time and the time in asctime format
# WARNING: It can not correctly handle the original creation time of a roi reloaded from file, 
# because it is reloaded as string and the new namedtuple is created with the current time
ROI = namedtuple('ROI', ['x', 'y', 'width', 'height', 'channel', 'created_at', 'created_at_asc'], defaults=[None, time.time(), time.asctime()])

# this is a class version of the namedtuple, but it is not working as expected
# class ROItemplate(namedtuple):
#     def _aslist(self):
#         return list(self)[-2]
# ROI2 = ROItemplate('ROI2', ['x', 'y', 'width', 'height', 'created_at', 'created_at_asc'], defaults=[time.time(), time.asctime()])

# if the dataclass only contains 'pointers' and no objects and raw data, it could be pickled
# Data_empty is a template class for the dataclass, all pointers are set
# there should be a new one for each state of a grain
# how to track if object attributes are changed, reimplement __setitem__ and __setattr__?  https://github.com/saurabh0719/object-tracker

class _data(DotDict):
    def __init__(self):
        self.fiofile = None  # full path to the fio file
        self.fiodata = None  # fio object from _fiosupport
        self.scanID = None   # integer
        # from here on these are channel specific, but this is not handled yet
        self.h5file = None  # full path to the h5 file
        self.h5data = None  # fabio object
        self.usedroi = None  # ROI namedtuple

class _centeringData(_data):
    def __init__(self):
        super().__init__()
        self.fitresults = None  # fit result object from lmfit
        
class _mapData(_data):
    def __init__(self):
        super().__init__()
        self.map = None  # numpy array

SUPPORTED_DETECTORS = {'Eiger4M??': 'Eiger2_4M', 'eiger1mw01': 'Eiger2_1MW', 'eiger1mw02': 'Eiger2_1MW'}  # This is a mapping of the ABTGV2 detector names to the pyFAI detector names


class grainStateDataEmpty(DotDict):
    def __init__(self):
        self.data = DotDict({'centerYs': [_centeringData()],  # these are lists so that more elements can be added if new scans pop up for the same centering action
                            'centerZs': [_centeringData()],
                            'centerOmegas': [_centeringData()],
                            'map': [_mapData()],
                            })
        # ROI
        self.rois = []  # list of ROI namedtuples; if there are multiple ROIs, the last one is the active one




# LIMITATIONS: only single channel fio files are supported!!!
#              only a single ROI is supported, but multiple ROIs can be added to the list, the last one is the active one,
# this is important, because one may not use different detectors within one grain state object, since the ROI would need to be different
class grainStateData(grainStateDataEmpty):
    def __init__(self):
        super().__init__()
        self.empty = None# grainStateDataEmpty()  # pointer to the empty object
        self.logPath = None  # path to the database
        self.logFileName = None  # name of the database JSON file
    
    def read_fios(self):
        for k,v in self.data.items():
            for vv in v:
                if vv['fiofile'] is not None and vv['fiodata'] is None:  # this would not reload already loaded fio files, but seems to fail
                #if vv['fiofile'] is not None:
                    vv['fiodata'] = _fiosupport.fio(vv['fiofile'])
                    vv.scanID = int(vv.fiofile.split('_')[-1].split('.')[0])
                    assert len(vv['fiodata'].channels) == 1, 'Currently only single channel fio files are supported' 

    def _get_idx_and_action(self, fioname):
        idx, action = None, None
        for k,v in self.data.items():
            # check if the fiofile is in the list, if it is in the list get the index, otherwise continue
            if fioname in [vv['fiofile'] for vv in v]: 
                idx = [i for i, w in enumerate(v) if w['fiofile'] == fioname][0]
                action = k
            else:
                continue
        if any([idx is None, action is None]):
            raise FileNotFoundError(f'No such fio file {fioname}')
        return idx, action


    def load_h5(self, fioname, test=False):  # this defines the h5file and h5data attributes
        idx, action = self._get_idx_and_action(fioname)
        self.data[action][idx]['h5file'], channel = self.data[action][idx]['fiodata'].getDataFile()
        if test:
            print(self.data[action][idx]['h5file'])
            print('Overwrite h5file with a test h5 file')
            h5file = '/home/hegedues/prog/p212SG/test.h5'
            self.data[action][idx]['h5file'] = h5file
        try:
            self.data[action][idx]['h5data'] = fabio.open(self.data[action][idx]['h5file'])
        except AssertionError:
            raise AssertionError('Not supported fio type')
        except FileNotFoundError:
            raise FileNotFoundError(f'No such file {self.data[action][idx]["h5file"]}')


    def get_intensity(self, fioname, test=False, masked=True):
        # uses the last roi from self.rois
        idx, action = self._get_idx_and_action(fioname)
        x = self.data[action][idx]['fiodata'].data['sweep_mot_mid_pos']
        if self.data[action][idx]['h5file'] is None:
            self.load_h5(fioname, test=test)
        h5file = self.data[action][idx]['h5data']
        if masked:
                detname = list(self.data[action][idx]['fiodata'].detectors.keys())[0]
                pyfaidetname = SUPPORTED_DETECTORS[detname.lower()]
                mask = getattr(detectors, pyfaidetname)().calc_mask()
        if self.rois != []:
            roi = self.rois[-1]
            y = [np.sum(maskedarray.masked_array(h5file.get_frame(i).data, mask)[roi.x:roi.x+roi.width, roi.y:roi.y+roi.height]) for i in range(len(x))]
        else:
            roi = ROI(0, 0, h5file.get_frame(0).data.shape[0], h5file.get_frame(0).data.shape[1])
            y = [np.sum(maskedarray.masked_array(h5file.get_frame(i).data, mask)) for i in range(len(x))]
        y = [float(yy) for yy in y]
        return x, y, roi
    

    def fit_center(self, fioname, bg=None, test=False):
        idx, action = self._get_idx_and_action(fioname)
        if test:
            x, y = SGmath.gaussian(np.linspace(-10, 10, 100), 1, 2, 0.05)
            usedroi = ROI(0, 0, 100, 100)
        else:
            x, y, usedroi = self.get_intensity(action, fioname)
        result = SGmath.fit_gaussian(x, y, bg)
        self.data[action][idx]['fitresults'] = result
        self.data[action][idx]['usedroi'] = usedroi
        return result


    def create_map(self):
        for k,v in self.data.items():
            for vv in v:
                if vv['h5'] is not None:
                    frames = vv['h5']
                    # TODO: implement the map creation, fix non-existent self.map attribute
                    #self.map[k] = np.array([frames.get_frame(i).data for i in range(len(frames))])

                    # has to implement usedroi update as well

    def update_empty(self):
        self.empty = grainStateDataEmpty()
        #rois
        # remove created_at and created_at_asc and transfer it as a list to the empty object, because upon serialization the namedtuple becomes a list
        # if this is not done, the live empty object will have a namedtuple, but the serialized object will have a list
        self.empty.rois = [list(r) for r in self.rois]

        #data
        for k,v in self.data.items():
            for i,vv in enumerate(v):
                if i > 0:  # if there are more than one elements in the list, append a new one to the empty object, the first one is already there
                    if isinstance(vv, _centeringData):
                        self.empty.data[k].append(_centeringData())
                    elif isinstance(vv, _mapData):
                        self.empty.data[k].append(_mapData())
                self.empty.data[k][i]['fiofile'] = vv['fiofile']
                self.empty.data[k][i]['fiodata'] = None
                self.empty.data[k][i]['scanID'] = vv['scanID']
                if hasattr(vv, 'fitresults'):  # _mapData does not have fitresults
                    if not vv['fitresults'] is None:
                        self.empty.data[k][i]['fitresults'] = {'best_values': vv['fitresults'].best_values,  # this is a subset of the params.valuesdict(), but I don't know which one is easier to use in the future
                                                            'parameters': vv['fitresults'].params.valuesdict(),
                                                            'components': [comp.name for comp in vv['fitresults'].components],} # this is a list of the components names of the model, because the components themselves are not serializable
                    else:
                        self.empty.data[k][i]['fitresults'] = None
                if hasattr(vv, 'maps'):
                    self.empty.data[k][i]['map'] = None
                self.empty.data[k][i]['usedroi'] = vv['usedroi']
                self.empty.data[k][i]['h5data'] = None
                self.empty.data[k][i]['h5file'] = vv['h5file']

    def _set_save_path(self, path):  # could only be a path and the actual files could be hardcoded
        if isinstance(path, str):
            self.logPath = path
            if not os.path.exists(self.logPath):
                os.makedirs(self.logPath)
                # check if the path is writable, DOES NOT WORK!!!??? https://stackoverflow.com/questions/2113427/determining-whether-a-directory-is-writeable
                if not os.access(self.logPath, os.W_OK | os.X_OK):
                    raise PermissionError('Path is not writable')
                try:
                    testfile = tempfile.TemporaryFile(dir = self.logPath)
                    testfile.close()
                except Exception as e:
                    raise e
        print(f'Save path: {self.logPath}')

    def _save_to_file(self, name):  # json and yaml
        if name.endswith('.json'):
            name = name[:-5]
        if self.logFileName is None:
            self.logFileName = name
            print(f'Log file name set to {self.logFileName}')
        if self.logPath is None:
            raise AttributeError('Save path is not set')
        if self.empty is None:
            raise AttributeError('Empty object is not set')
        # save the object to the path
        extensions = ['json', 'yaml']
        for ext in extensions:
            if ext == 'json':
                with open(os.path.join(self.logPath, f'{name}.json'), 'w') as f:
                    json.dump(self.empty, f)
            elif ext == 'yaml':
                # use a tempfile to write the json and then read it back and save it as yaml
                # incredibly ugly, but it works, as opposed to json.dumps(), because that produces a non human readable output
                tmp = ''
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:  # delete_on_close=False only possible from 3.12, with delete=False the file will remain on disk even after the context manager exited.
                    json.dump(self.empty, f)
                    f.close()
                    with open(f.name, 'rb') as f:
                        tmp = json.load(f)
                with open(os.path.join(self.logPath, f'{name}.yaml'), 'w') as f:
                    yaml.dump(tmp, f)
                del tmp
            else:
                raise ValueError('Unknown file format')

    def _update_and_save(self):  # convenience function
        self.update_empty()
        self.save_to_file()


    def _check_JSON_modification(self):
        if self.logPath is None:
            raise AttributeError('Save path is not set')
        if self.empty is None:
            raise AttributeError('Empty object is not set')
        # load the object from the path
        loaded = None
        with open(os.path.join(self.logPath, self.logFileName + '.json'), 'r') as f:
            loaded = json.load(f)
        # compare loaded to self.empty
        jsondiff = diff(self.empty, loaded)
        if jsondiff != {}:
            print('File externally modified')
            return jsondiff
        return False
    

    def _check_JSON_corruption(self):
        if self.logPath is None:
            raise AttributeError('Save path is not set')
        if self.empty is None:
            raise AttributeError('Empty object is not set')
        # load the object from the path
        loaded = None
        for path in self.logPath:
            if path.endswith('.json'):
                with open(path, 'r') as f:
                    loaded = json.load(f)
        # parse the loaded object and set the attributes????
        # check if loaded object has no less attributes than the empty object, otherwise it is corrupted
        if loaded != self.empty:
            # check data keys
            currentset = set()
            loadedset = set()
            for k,v in self.data.items():
                currentset.add([vv['fiofile'] for vv in v])
            for k,v in loaded['data'].items():
                loadedset.add([vv['fiofile'] for vv in v])
            if not currentset.issubset(loadedset):  
                raise ValueError('Corrupted object')
            #fitresults  # this is either very complicated or we accept that the fitresults are not checked

            # check rois
            corrupt = False
            # checki if all self.empty.rois are in loaded['rois'], throw error if not
            for r in self.empty.rois:
                if r not in loaded['rois']:
                    raise ValueError('Corrupted object')            
        return False

    def update_data(self):  # this is meant to update both the data and the empty object after a new fio file is added from the database/JSON
                            # or after a new roi definition is added
        # load fiodata
        self.read_fios()
        for k,v in self.data.items():
            for vv in v:
                # load h5 data
                if vv['fiofile'] is not None and vv['h5file'] is None:
                    try:
                        vv['h5file'] = vv['fiodata'].getDataFile()
                    except AssertionError:
                        raise AssertionError('Not supported fio type')
                # fit the data, if it is a certering fio, create map if it is a map fio
                if hasattr(vv, 'fitresults'):
                    if vv['fiofile'] is not None and vv['fitresults'] is None:
                        self.fit_center(k, vv['fiofile'])  # this will update the fitresults and usedroi attributes
                if hasattr(vv, 'map'):
                    if vv['fiofile'] is not None and vv['map'] is None:
                        self.create_map()
        self.update_empty()


    def _load_JSON(self, loadCorrupted=False, test=False):
        if self.paths is None:
            raise AttributeError('Save path is not set')
        if self.empty is None:
            raise AttributeError('Empty object is not set')
        if not loadCorrupted:
            try:
                corrupt = self._check_JSON_corruption()
            except ValueError:
                raise ValueError('Corrupted object')
        # load object from JSON
        loaded = None
        for path in self.paths:
            if path.endswith('.json'):
                with open(path, 'r') as f:
                    loaded = json.load(f)

        # data, except for fitresults, beacuse they need to be converted back to lmfit.model.ModelResult
        self.data = loaded['data']
        self.update_empty()
        print(f'\n{self.data=}\n')

        print('Reloading fitresults!!!')
        print(f'{loaded["fitresults"]=}')
        for k,v in self.data.items():  # this already contains everything, but the fitresults
            for vv in v:
                if vv['fitresults'] is not None:
                    gmod = lmfit.models.GaussianModel(prefix='peak_')
                    if 'linear' in vv['fitresults']['components']:
                        bgmod = lmfit.models.LinearModel(prefix='line_')
                    elif 'constant' in vv['fitresults']['components']:
                        bgmod = lmfit.models.ConstantModel(prefix='const_')
                    pars = lmfit.Parameters()
                    for key, value in vv['fitresults']['parameters'].items():
                        pars.add(key, value)
                    if 'linear' in vv['fitresults']['components'] or 'constant' in vv['fitresults']['components']:
                        model = gmod + bgmod
                    if test:
                        x, y = SGmath.gaussian(np.linspace(-10, 10, 100), 1, 2, 0.05)
                    else:
                        x, y = self.Nget_intensity(k, vv['fiofile'])
                    print('Refitting!!!')
                    vv['fitresults'] = model.fit(y, x=x, params=pars)

        # rois
        self.rois = [ROI(*r) for r in loaded['rois']]
        self.update_data()

 

if __name__ == "__main__":
    print('Use the gui_data_test.py script for testing')


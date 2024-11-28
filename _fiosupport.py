import dateutil.parser
import json
import os
import re
import numpy as np
import copy


DET_NAMES = {'Varex_1': 'hasep21eh3:10000/p21/Varex/1',
             'Varex_2': 'hasep21eh3:10000/p21/Varex/2',
             'Varex_3': 'hasep21eh3:10000/p21/Varex/3',
             'Varex_4': 'hasep21eh3:10000/p21/Varex/4',
             'Varex_5': 'hasep21eh3:10000/p21/Varex/5',
             'Eiger':   'hasep21eh3:10000/p21/Eiger/e4m',
             'Eiger1mw01': 'hasep21eh2:10000/p21/Eiger/e1mw01',
             'Eiger1mw02': 'hasep21eh2:10000/p21/Eiger/e1mw02',
             'Pilatus': 'hasep21eh3:10000/p21/Pilatus/CdTe2M',
             'PCO':     'hasep21eh3:10000/p21/PCO/pool',}
DET_NAMES = {k.lower(): v.lower() for k,v in DET_NAMES.items()}


# there is no way to identify which channel is which detector!?
class fio:
    """
    The `fio` class provides methods to read and process data from a specified file format. 
    It extracts comments, parameters, and data from the file and stores them in the class attributes.
    """

    def __init__(self, fn: str):
        """
        Initializes the class with default values for its attributes.
        Attributes:
            parameters (None): Placeholder for parameters.
            data (None): Placeholder for data.
            columns (None): Placeholder for columns.
            command (None): Placeholder for command.
            fioType (None): Placeholder for fioType.
            user (None): Placeholder for user.
            date (None): Placeholder for date.
            detectors (dict): Dictionary to store detector information.
        """
        
        self.parameters = None
        self.data = {}
        self.channelData = {}
        self.columns = None
        self.command = None
        self.fioType = None
        self.user = None
        self.startdate = None
        self.enddate = None
        self.finished = None
        self.abtgv2config = None
        self.channels = {}
        self.detectors = {}

        self._read(fn)

    def _type (self, val: str):
        """
        Converts a string to an integer or float if possible.

        Args:
            val (str): The string to be converted.

        Returns:
            int or float or str: The converted value if possible, otherwise the original string.
        """
        try:
            return int(val)
        except ValueError:
            try:
                return float(val)
            except ValueError:
                return val
            

    def _read(self, fn):
        """
        Reads the content of the file specified by `fn` and processes it into comments, parameters, and data.

        Args:
            fn (str): The file path to read from.

        Raises:
            ValueError: If the file does not contain the required '%c', '%p', and '%d' markers.

        Side Effects:
            Sets the `self.parameters` and `self.data` attributes with the parsed parameters and data from the file.
        """
        lines = open(fn).read().splitlines()
        c = lines.index('%c')
        p = lines.index('%p')
        d = lines.index('%d')
        e = len(lines)-1

        self._getComments(lines=lines, start=c+1, end=p)
        self.parameters = self._getParameters(lines=lines, start=p+1, end=d)
        self._getData(lines=lines, start=d+1, end=e)
        self._getEnd(lines=lines)
        
        self._getChannels()
        for ch in self.channels.keys():
            try:
                self._getChannelData(ch)
            except KeyError:
                raise ValueError(f'Channel {ch} contains more than one detector. This is currenlty not supported.')
        
        try:
            self._convertToMidMotorPosition()
        except AssertionError:
            pass

    def _getEnd(self, lines: str):
        """
        Parses the last line of the given lines to determine the end date and status.

        Args:
            lines (str): A string containing multiple lines of text.

        Sets:
            self.enddate: The parsed end date from the last line if it starts with '!'.
            self.finished: The status of the process, set to 'Aborted' if the last line contains 'aborted',
                           or 'Finished' if the fioType is one of ['fastsweep2', 'supersweep2', 'timesweep2'].
        """
        last_line = lines[-1]
        if last_line.startswith('!'):
            self.enddate = dateutil.parser.parse(' '.join(last_line.split(' ')[4:9]))
            if 'aborted' in last_line:
                self.finished = 'Aborted'
            elif self.fioType in ['fastsweep2', 'supersweep2', 'timesweep2']:
                self.finished = 'Finished'

    def _getComments(self, lines: str, start: int, end: int):
        """
        Extracts comments from a specified range of lines and parses command, fioType, user, and date.

        Args:
            lines (str): The string containing multiple lines to be processed.
            start (int): The starting index of the range of lines to be processed.
            end (int): The ending index of the range of lines to be processed.

        Attributes:
            command (str): The first comment line that does not start with '!'.
            fioType (str): The first word of the command.
            user (str): The user extracted from the second comment line.
            date (datetime): The date parsed from the second comment line.
        """
        comment = []
        for l in lines[start:end]:
            if not l.startswith('!'):
                comment.append(l)
        self.command = comment[0]
        self.fioType = self.command.split()[0]
        self.user = comment[1].split(' ')[1]
        self.startdate = dateutil.parser.parse(' '.join(comment[1].split(' ')[5:]))

    def _getParameters(self, lines: str, start: int, end: int):
        """
        Extracts parameters from a given range of lines and processes them into a dictionary.
        Args:
            lines (str): The input string containing multiple lines.
            start (int): The starting line index (inclusive).
            end (int): The ending line index (exclusive).
        Returns:
            dict: A dictionary containing the extracted parameters. If a parameter value is a 
              comma-separated list of key-value pairs, it is further processed into a nested dictionary.
        """
        pars = {}
        for l in lines[start:end]:
            if not l.startswith('!'):
                key = l.split('=')[0].strip()
                val = l.split('=')[1].strip() # take all elements after the first
                pars[key] = self._type(val)
        
        for k,v in pars.items():
            k=k.lower()  # this is to create lower case keys for the detectors
            if isinstance(v, str):
                try:
                    self.detectors[k] = json.loads(v)  # this works for the detector parameters, but not for the ABTGV2_CONF dict
                    continue
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(e)
                
                if k == ('ABTGV2_CONF'.lower()):
                    tmpv = re.sub(r'\s(\d):', r' "\1":', v)  # add quotes around the single digits with a preceding space
                    tmpv = re.sub(r'{(\d):', r'{"\1":', tmpv)  # Add quotes around single digits that follow an opening curly brace
                    tmpv = tmpv.replace('\n', '').replace(' ', '').replace('\'', '\"').replace('(', '[').replace(')', ']')
                    try:
                        self.abtgv2config = json.loads(tmpv)
                        # change all detector device strings to lowercase
                        for k,v in self.abtgv2config.items():
                            if isinstance(v, dict):
                                for kk,vv in v.items():
                                    if isinstance(vv, list):
                                        for i,l in enumerate(vv):
                                            vv[i] = vv[i].lower()

                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        print(e)
                    
#        for k in self.detectors.keys():
#            #k = k.lower()  # the lower case keys can not be used here
#            pars.pop(k)
        return pars

    def _getChannels(self):
        """
        Extracts channel information from the parameters.
        """

        if self.fioType in ['fastsweep2', 'supersweep2', 'timesweep2'] and self.abtgv2config is not None:
            usedchannels = [c[0] for c in self.command.split() if ':' in c]
            for ch in usedchannels:
                dets = self.abtgv2config['detectors'][ch]
                self.channels[ch] = []
                #self.channels[ch] = {}
                for d in dets:
                    for k,v in DET_NAMES.items():
                        if d.lower() in v.lower():
                            self.channels[ch].append(k)
                            #self.channels[ch][k] = {}

    def _getChannelData(self, ch: str):
        """
        Retrieve and process data for a specific channel.

        This method checks if the specified channel exists in the `channels` attribute.
        If not, it attempts to refresh the channels list. If the channel still does not
        exist, it raises a ValueError. For each detector in the channel, it copies the
        data and removes columns that do not correspond to the detector. It also renames
        the detector's column to 'imageID' and removes rows that do not contain valid
        data for the specified detector. Finally, it adds directory and file pattern
        information to the data.

        Args:
            ch (str): The channel identifier.

        Raises:
            ValueError: If the specified channel is not found in the data.
        """

        if ch not in self.channels:
            self._getChannels()
        if ch not in self.channels:
            raise ValueError(f'Channel {ch} not found in the data.')
        self.channelData[ch] = {}
        for det in self.channels[ch]:
            self.channelData[ch][det] = self.data.copy()
            # remove other detectors image number columns
            # TODO: this is not working for mutiple detectors on the same channel, because it removes all of them
            for data_label in list(self.channelData[ch][det].keys()):
                if data_label.lower() in [k.lower() for k in list(self.detectors.keys())]:
                    if data_label.lower() == det.lower():
                        print(f'Renaming {data_label} to imageID')
                        self.channelData[ch][det]['imageID'] = self.channelData[ch][det].pop(data_label)
                    if data_label.lower() != det.lower():
                        print(f'Removing {data_label=} from {ch=} for {det=}')
                        _ = self.channelData[ch][det].pop(data_label)
        # remove data lines that do not contain valid data for the specified detector
        for det in self.channelData[ch].keys():
            nones = []
            for i,l in enumerate(self.channelData[ch][det]['imageID']):
                if l == '<no-data>':
                    nones.append(i)
            for k in self.channelData[ch][det].keys():
                self.channelData[ch][det][k] = [v for i,v in enumerate(self.channelData[ch][det][k]) if i not in nones]
        # add the directory and file pattern to the data
        for det in self.channelData[ch].keys():
            self.channelData[ch][det]['Filedir'] = self.detectors[det]['Filedir']
            self.channelData[ch][det]['Filepattern'] = self.detectors[det]['Filepattern']
            self.channelData[ch][det]['Files'] = self.getFileList(ch)

    def getFileList(self, ch: str):
        """
        Generates a dictionary of file paths for a given channel.
        Args:
            ch (str): The channel identifier.
        Returns:
            dict: A dictionary where keys are detector identifiers and values are lists of file paths.
        """
        
        files = {}
        for det in self.channelData[ch].keys():
            files[det] = []
            if '%' in self.channelData[ch][det]['Filepattern']:  # tif or cbf files
                for id in self.channelData[ch][det]['imageID']:
                    files[det].append(os.path.join(self.channelData[ch][det]['Filedir'], self.channelData[ch][det]['Filepattern']%id))
            else: # h5 files
                files[det].append(os.path.join(self.channelData[ch][det]['Filedir'], self.channelData[ch][det]['Filepattern']))
        return files    


    def _getData(self, lines: str, start: int, end: int):
        """
        Extracts and processes data from a given range of lines.

        Args:
            lines (str): The input lines containing data.
            start (int): The starting index of the range of lines to process.
            end (int): The ending index of the range of lines to process.

        Returns:
            None: The function updates the instance's `columns` and `data` attributes.
        """

        self.columns = []
        coldtype = []
        data = []
        for l in lines[start:end]:
            if l.startswith(' Col'):
                self.columns.append(l.split()[2])
                coldtype.append(l.split()[-1].lower())
            else:
                data.append([self._type(ll) for ll in l.split()])  # Convert to float
        data = list(map(list, zip(*data)))  # Transpose the data
        for c,d,dt in zip(self.columns, data, coldtype):
            self.data[c] = d

    def _convertToMidMotorPosition(self):
        '''
        Converts encoder start and end positions to middle (avg) positions.
        '''
        if self.fioType in ['fastsweep2', 'supersweep2']:
            assert len(([i for i in self.columns if i.endswith('(start)')])) == 1, 'More than one start position found.'
            assert len([i for i in self.columns if i.endswith('(end)')]) == 1, 'More than one end position found.'
            start_str = [i for i in self.columns if i.endswith('(start)')][0]
            end_str = [i for i in self.columns if i.endswith('(end)')][0]
            self.columns.append('sweep_mot_mid_pos')
            self.data['sweep_mot_mid_pos'] = [(s+e)/2 for s,e in zip(self.data[start_str], self.data[end_str])]

    def export(self , fn: str):
        """
        Exports the data to a specified json file.

        Args:
            fn (str): The file path to export the data to.
        """
        with open(fn, 'w') as f:
            json.dump(self.__dict__, open(fn, 'w'), default=str, indent=4, sort_keys=True)

    def getDataFile(self, channel=None): # this is a crappy method
        assert self.fioType in ['fastsweep2', 'supersweep2', 'timesweep2'], 'Only fastsweep and supersweep fio objects implement this method.'
        assert len(list(self.channels.keys())) == 1, 'Only one channel is supported.'
        assert len(list(self.channels.values())[0]) == 1, 'Only one detector per channel is supported.'
        if channel is None:
            channel = list(self.channels.keys())[0]
        assert self.channelData[channel][list(self.channels.values())[0][0]]['Filepattern'].endswith('.h5'), 'Only h5 files are supported.'
        path = self.channelData[channel][list(self.channels.values())[0][0]]['Filedir']
        file = self.channelData[channel][list(self.channels.values())[0][0]]['Filepattern']
        return os.path.join(path, file), channel

def test(f='ts2.fio'):
    a = fio(f)
    a._getChannels()
    print(f'{a.channels=}')
    for ch in a.channels.keys():
        a._getChannelData(ch)
    print(f'{a.channelData["3"].keys()=}')
    for ch in a.channels.keys():
        print(f'{ch=}')
        for k,v in a.channelData[ch].items():
            print(f'{k=}')
            print(f'{v.keys()=}')
            print(f'{a.channelData[ch][k]["imageID"]=}')
    
    return a


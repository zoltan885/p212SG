#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 10 10:57:06 2020

@author: hegedues
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.patches import Rectangle

#from PIL import Image
import dateutil
import os, time
import fabio

try:
    import PyTango as PT
    import HasyUtils as HU
except ImportError:
    print('WARNING! Could not import PyTango & HasyUtils')


DEBUG = 1



def _getMovableSpockNames():
    '''
       gets the stepping_motor devices
    '''
    try:
        import PyTango as PT, HasyUtils as HU
    except(ImportError):
        print('Could not import modules PyTango and HasyUtils')
        return -1

    names=dict()
    try:
        for rec in HU.getOnlineXML():
            # the phy_motion is type_tango
            if rec['type'].lower() == 'stepping_motor' or rec['type'].lower() == 'type_tango':
                names[rec['name'].lower()] = rec['device'].lower()
    except:
        pass
    return names




def _fioparser(fn=None, onlyexp=True):
    '''
    :param fn: fio file
    :param onlyexp: if true it only returns the exposure frames
    :return:
    '''
    if fn is None:
        raise ValueError
    lines = open(fn).read().splitlines()
    comment = []
    parameter = []
    data = {}
    datatmp = []
    columns = []
    cdatatype = []
    c = lines.index('%c')
    p = lines.index('%p')
    d = lines.index('%d')
    e = len(lines)-1

    for l in range(len(lines)):
        if lines[l].startswith('! Acquisition ended'):
            e = l

    for l in range(len(lines)):
        if not lines[l].startswith('!'):
            if l > c and l < p:
                comment.append(lines[l])
            if l > p and l < d:
                parameter.append(lines[l])
            if d < l < e or l == e: # this is for the lambda fio!!!
                    if lines[l].split()[0] == 'Col':
                        if len(lines[l].split()) == 4:
                            columns.append(lines[l].split()[2])
                        else: # this can handle multi-word column names
                            columns.append(' '.join(lines[l].split()[2:-1]))

                        cdatatype.append(lines[l].split()[-1])
                    else:
                        if onlyexp:
                            if 'exposure' in lines[l]: # poorly written filter for exposure frames
                                datatmp.append([i for i in lines[l].split()])
                        else:
                            datatmp.append([i for i in lines[l].split()])

    for i in range(len(columns)):
        if cdatatype[i].lower() in ['float', 'double']:
            data[columns[i]] = np.array(np.array(datatmp)[:,i], dtype=float)
        if cdatatype[i].lower() in ['string', 'integer']:
            data[columns[i]] = np.array(np.array(datatmp)[:,i], dtype=str)

    command = comment[0]
    #print('Command: ', command)
    user = comment[1].split(' ')[1]
    #print('User: ', user)
    date = dateutil.parser.parse(' '.join(comment[1].split(' ')[5:]))
    # get filedirs:
    savedir = {}
    for i in parameter:
        if 'filedir' in i.lower() or 'filepath' in i.lower() or 'downloaddirectory' in i.lower():
            channelNo = int(i.lower().partition('_')[0][-1])
            savedir['%d' % channelNo] = i.rpartition(' = ')[2].replace('\\', '/').replace('t:/', '/gpfs/').replace('/ramdisk/', '/gpfs/')

    return data, savedir, command


def imagesFromFio(fiofile, channel=1):
    data, savedir, _ = _fioparser(fiofile)
    # lambda or only one tif image
    if len(set(data['filename'])) == 1:
        channel=2   # TODO
        files = savedir[str(channel)] + '/' + data['filename'][0]
    else:
        files = []
        for t,fn in zip(data['type'], data['filename']):
            # filter for exposure frames
            if t == 'exposure':
                ###########################################
                #number = fn[:-4].rpartition('_')[2]
                #while not number.isdigit():
                #    number = number[1:]
                #fn = fn.replace(str(number), '%05i'%(int(number)))
                ###########################################
                files.append(savedir[str(channel)] + fn)
    return files



def _getPosOfImage(imagename):
    '''
    look for the given image (path and number) in the fio files and then get the position from there
    not high priority
    '''
    pass


def explorer(imsource, ROI=None):
    """
    function for initial grain hunt
    shows the list of images with a slider to inspect them individually

    TODO:
        could work with keyboard
    """
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, Button, RadioButtons

    tif,nxs,fio,h5 = False,False,False,False
    if isinstance(imsource, list):
        imageList = imsource
        tif = True
        if DEBUG: print('List of tif files')
    elif isinstance(imsource, str):
        if imsource.endswith('nxs'):
            data = getDataNXSLambda(imsource)
            nxs = True
            if DEBUG: print('Nexus file')

        elif imsource.endswith('.fio'):
            fiodata, savedir,_ = _fioparser(imsource) # this would be great except I have no means to know what kind of fio I'm looking at, which motor positions to take
            fio = True
            il = imagesFromFio(imsource)
            print(il)
            if isinstance(il, str):
                if il.endswith('nxs'):
                    data = getDataNXSLambda(il)
                    nxs = True
                elif il.endswith('.h5'):
                    data = getEigerDataset(il)
                    h5 = True
            elif isinstance(il, list):
                imageList = il
                tif = True
        elif imsource.endswith('.h5'):
            data = getEigerDataset(imsource)
            if DEBUG: print('Eiger file')
            h5 = True

    else:
        raise ValueError('Source format not recognized.')


    #if tif and DEBUG: print(imageList)

    # generate figure
    fig = plt.figure()
    ax = plt.subplot(111)
    fig.subplots_adjust(left=0.25, bottom=0.25)

    # get image positions if the source is a fio file
    positions = None
    if fio:
        # fastsweep:
        if len(fiodata.keys()) == 6:
            positions = fiodata['idrz1(encoder)']
            positions += (positions[1]-positions[0])/2
        # supersweep
        elif len(fiodata.keys()) == 7:
            for k in fiodata.keys():
                if k not in ['idrz1(encoder)', 'type', 'filename', 'end pos', 'unix time', 'channel']:
                    positions = fiodata[k]
    # select first image
    if tif:
        im = np.array(fabio.open(imageList[0]).data)
        if positions is not None:
            ax.set_title(imageList[0].rpartition('/')[2] + ': %.4f'%positions[0])
        else:
            ax.set_title(imageList[0].rpartition('/')[2])
        ax.set_title(imageList[0].rpartition('/')[2])
    if nxs or h5:
        im = np.array(data[0])
        if positions is not None:
            ax.set_title('0: %.4f'%positions[0])
        else:
            ax.set_title(0)
    # if h5:
    #     im = np.array(data[0])
    #     if positions is not None:
    #         ax.set_title('0: %.4f'%positions[0])
    #     else:
    #         ax.set_title(0)

    # display image
    plot = ax.imshow(im, cmap='jet')
    # define sliders
    axmin = fig.add_axes([0.25, 0.1, 0.65, 0.03], facecolor='azure')
    axmax  = fig.add_axes([0.25, 0.15, 0.65, 0.03], facecolor='azure')
    smin = Slider(axmin, 'color min', 0, im.max(), valinit=0, valfmt='%i')
    smax = Slider(axmax, 'color max', 0, im.max(), valinit=im.max()/5, valfmt='%i')

    def updateColor(val):
        plot.set_clim([smin.val, smax.val])
        fig.canvas.draw()
    smin.on_changed(updateColor)
    smax.on_changed(updateColor)

    if tif: noImages = len(imageList)
    if nxs or h5: noImages = data.shape[0]

    ax2 = fig.add_axes([0.25, 0.05, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    imSlider = Slider(ax2, 'image', 0, noImages - 1, valinit=0, valfmt='%i')

    def updateImage(val):
        indx = int(np.round(val))
        if tif:
            im = fabio.open(imageList[indx]).data
            if positions is not None:
                ax.set_title(imageList[indx].rpartition('/')[2] + ': %.4f'%positions[indx])
            else:
                ax.set_title(imageList[indx].rpartition('/')[2])
        if nxs or h5:
            im = data[indx]
            ax.set_title(indx)
        #print('Update image to %s' % (imageList[indx]))

        plot.set_data(im)
        fig.canvas.draw()

    imSlider.on_changed(updateImage)

    def zmax(event):
        '''
        the projection should only be done for the first time,
        but in order to realize this function should be a class member...
        '''
        sumi = np.zeros_like(im)
        if tif:
            for i in imageList:
                sumi = np.maximum(sumi, fabio.open(i).data)
        if nxs or h5:
            for i in range(noImages):
                sumi = np.maximum(sumi, data[i])
        ax.set_title('Z project max')
        plot.set_data(sumi)

    axproj = plt.axes([0.05, 0.8, 0.1, 0.075])
    bproj = Button(axproj, 'Zmax')
    bproj.on_clicked(zmax)

    def zave(event):
        avei = np.zeros_like(im)
        if tif:
            for i in imageList:
                avei = np.sum((avei, fabio.open(i).data), axis=0)
            avei = avei / len(imageList)
        if nxs or h5:
            for i in range(noImages):
                avei = np.sum((avei, data[i]), axis=0)
            avei = avei / data.shape[0]

        ax.set_title('Z average')
        plot.set_data(avei)

    axave = plt.axes([0.05, 0.7, 0.1, 0.075])
    bave = Button(axave, 'Zave')
    bave.on_clicked(zave)

    # ROI definition
    limits={'xmin':0, 'xmax':10000, 'ymin':0, 'ymax':10000}

    def on_xlims_change(axes):
        limits['xmin'] = int(np.floor(ax.get_xlim()[0]))
        limits['xmax'] = int(np.ceil(ax.get_xlim()[1]))
        #print("updated xlims: ", ax.get_xlim())

    def on_ylims_change(axes):
        limits['ymin'] = int(np.floor(ax.get_ylim()[1]))
        limits['ymax'] = int(np.ceil(ax.get_ylim()[0]))
        #print("updated ylims: ", ax.get_ylim())
    ax.callbacks.connect('xlim_changed', on_xlims_change)
    ax.callbacks.connect('ylim_changed', on_ylims_change)

    if ROI is not None:
        xpos = ROI['xmin']
        ypos = ROI['ymin']
        width = ROI['xmax']-ROI['xmin']
        height = ROI['ymax']-ROI['ymin']
        rect = Rectangle((xpos, ypos), width, height, linewidth=1, edgecolor='r', facecolor='none')
        ax.add_patch(rect)

    plt.show(block=True)
    # catch ROI
    limitsNP = {'xmin':limits['ymin'], 'xmax':limits['ymax'], 'ymin':limits['xmin'], 'ymax':limits['xmax']}
    return limits, limitsNP

def _readFastsweepLog(filename):
    # dtype=None is needed for automatic detemination of the data type in each column
    # skip_header is needed because the first line after skip_header is taken as names for the columns
    # names=True is needed because then the column names will be read
    log = np.genfromtxt(filename, dtype=None, comments='#', usecols=(0,1,2,3),
                        skip_header=9, names=True, encoding=None)
    # drop the clearing frames
    log = np.array([i for i in log if i[2]=='r'], dtype=log.dtype)
    print(log)

    # determining the average encoder position for every image
    avepos = (log['encoder_end_position']+log['encoder_start_position'])/2
    # determining the average motor position for every image (111111 is the encoder conversion factor)
    avemotpos = avepos/111111

def getEigerDataLength(datafile):
    import h5py
    a = h5py.File(datafile, 'r')
    datalen = 0
    for aa in a['entry']['data']:
        datalen += a['entry']['data'][aa].shape[0]
    return datalen

def getEigerDataset(datafile, ind=None):
    '''
    get the eiger dataset
    if index is given it returns a 2d array (the indexth image)
    if omitted it returns the full dataset
    '''
    import h5py
    a = h5py.File(datafile, 'r')
    data = []
    if ind is not None:
        ctr, tctr = 0, 0
        dset = 0
        lst = list(a['entry']['data'].keys())
        for i,l in enumerate(lst):
            tctr += a['entry']['data'][l].shape[0]
            if tctr > ind:
                dset = i
                break
            else:
                ctr = tctr
        indinset = ind-ctr
        data = a['entry']['data'][str(lst[dset])][indinset,:,:].astype('int16')
    else:
        print('here')
        lst = list(a['entry']['data'].keys())
        print(lst)
        for ds in lst:
            data.append(np.array(a['entry']['data'][ds]).astype('int16'))
    return np.squeeze(data)  # otherwise there is an extra dimension (God knows why)

def getDataNXSLambda(filename, seq=None):
    '''
    seq is the sequence of the exposure types to dispose 'garbage' frames
    '''
    try:
        import h5py
    except:
        raise ImportError('Could not import h5py')

    nxs = h5py.File(filename)
    data = np.array(nxs['entry/instrument/detector/data'])
    filtered_data = []
    if seq:
        for i,s in enumerate(seq):
            if s == 'exposure':
                filtered_data.append(data[i])
        data = filtered_data
    return data

def getDataTIFCBF(listOfImages):
    data = []
    for i in listOfImages:
        data.append(fabio.open(i))
    print(np.array(data).shape)
    return np.array(data)

def subtractDark(img, dark, negval=0):
    '''
    subtracts the dark from img and sets the negative pixel values to negval\n
    if negval is set to 1 then all zeros are also set to 1, this could be useful for log color-scaling,
    but it is not a good idea for integration\n
    img & dark are np.array-s
    '''
    img = img - dark
    img[img < negval] = negval
    return img

def integrateROI(data, ROI, dark=None, show=False):
    '''
    returns the sum of the ROI of an image, if dark is given it is first subtracted
    '''
#    print('Working on image %s' % imfile)
    img = data
    if dark:
        img = subtractDark(img, dark)
    # the index variables are swapped, because PIL and np.array does not define them the same way
    #img = img.transpose()
    # the numpy convention is different than the PIL therefore the image is transposed
    xmin = ROI['ymin']
    xmax = ROI['ymax']
    ymin = ROI['xmin']
    ymax = ROI['xmax']
    #print('taking the sum with limits: %d %d & %d %d' % (xmin, xmax, ymin, ymax))
    if show:
        im = img[xmin:xmax, ymin:ymax]
        fig, ax = plt.subplots()
        ax.imshow(im, vmin=0, vmax=im.max()/5, cmap='jet')
        plt.show()
    return np.mean(img[xmin:xmax, ymin:ymax])

def getIntensities(imsource, roi):
#    tif,nxs = False,False
#    if isinstance(imsource, list):
#        imageList = imsource
#        tif = True
#        if DEBUG: print('List of tif files')
#    elif isinstance(imsource, str):
#        if imsource.endswith('nxs'):
#            data = getDataNXSLambda(imsource)
#            nxs = True
#            if DEBUG: print('Nexus file')
#
#        elif imsource.endswith('.fio'):
#            il = imagesFromFio(imsource)
#            print(il)
#            if isinstance(il, str):
#                if il.endswith('nxs'):
#                    data = getDataNXSLambda(il)
#                    nxs = True
#            elif isinstance(il, list):
#                imageList = il
#                tif = True
#    else:
#        raise ValueError('Source format not recognized.')
#    print(':getIntensities: tif/nxs' , tif, nxs)

    tif,nxs,fio,h5 = False,False,False,False
    if isinstance(imsource, list):
        imageList = imsource
        tif = True
        if DEBUG: print('List of tif files')
    elif isinstance(imsource, str):
        if imsource.endswith('nxs'):
            data = getDataNXSLambda(imsource)
            nxs = True
            if DEBUG: print('Nexus file')

        elif imsource.endswith('.fio'):
            fiodata, savedir, _ = _fioparser(imsource) # this would be great except I have no means to know what kind of fio I'm looking at, which motor positions to take
            fio = True
            il = imagesFromFio(imsource)
            print(il)
            if isinstance(il, str):
                if il.endswith('nxs'):
                    data = getDataNXSLambda(il)
                    nxs = True
                elif il.endswith('.h5'):
                    data = getEigerDataset(il)
                    h5 = True
            elif isinstance(il, list):
                imageList = il
                tif = True
        elif imsource.endswith('.h5'):
            data = getEigerDataset(imsource)
            if DEBUG: print('Eiger file')
            h5 = True
    else:
        raise ValueError('Source format not recognized.')

    print(':getIntensities: tif/nxs' , tif, nxs)
    intensities = []
    if tif:
        for i in imageList:
            im = fabio.open(i).data
            intensities.append(integrateROI(im, roi))
    elif nxs or h5:
        for i in range(data.shape[0]):
            im = data[i]
            intensities.append(integrateROI(im, roi))
    return np.array(intensities)


def fitGauss(scanFileName, roi, motor=None, show=True, gotoButton=False, gotofitpos=True):
    '''
    TODO this could simply return the results object and the center functions should take care of the moveto and displaying the results
    :param scanFileName: fio file of the scan to fit
    :param roi: ROI to use for integration
    :param motor: motor name to get positions from fio file
    :param show: if true it shows the fit
    :param gotoButton:
    :return:
    '''
    try:
        from lmfit.models import GaussianModel, LinearModel
        from matplotlib.widgets import Button
    except:
        raise ImportError('gitGauss func: could not import...')

    fiodata, path, command = _fioparser(scanFileName)
    ya = getIntensities(scanFileName, roi) # here we also read back every clearing frame from the beamline file system, not good
    # filtering for exposure frames
    if motor is None:
        motor = command.split(' ')[1]
        if motor == 'idrz1':
            motor = 'idrz1(encoder)'
        if DEBUG:
            print('Motor determined from fio file as: %s', motor)
    x = np.array([p for (p,t) in zip(fiodata[motor], fiodata['type']) if t=='exposure'])
    # one would need to know if this was a supersweep or a fastsweep
    # if it was a fastsweep then x needs to be incremented by half the stepsize (this is temporary, eventually the end position will be implemented in the fio)
    y = np.array([i for (i,t) in zip(ya, fiodata['type']) if t=='exposure'])

    print(x)
    print(y)

    gmod = GaussianModel(prefix='peak_')
    lmod = LinearModel(prefix='line_')

    print(len(x), len(y))

    try:
        pars = gmod.guess(y, x=x)
        pars += lmod.guess(y, x=x)
    except:
        print('Automatic parameter guess failed')
        pars = gmod.make_params()
        pars += lmod.make_params()
        # peak_center parameter is restricted to the data region
        pars['peak_center'].set(x[np.argmax(y)], min = np.min(x), max = np.max(x))
        pars['peak_amplitude'].set(np.max(y)-np.min(y))
        pars['peak_sigma'].set(0.2*(np.max(x)-np.min(x)))
        pars['line_slope'].set((y[-1]-y[0])/(x[-1]-x[0]))
        pars['line_intercept'].set(np.min(y))

    mod = lmod + gmod

    #print(x, y)
    #print(pars)

    result = mod.fit(y, pars, x=x)
    move = False
    if result.success:
        cen = result.best_values['peak_center']
#        cen_err = pars['peak_center'].stderr
        amp = result.best_values['peak_amplitude']
        fwhm = 2.35482*result.best_values['peak_sigma']
        # sanity check
        sane = True
        scanRange = (np.max(x)-np.min(x))
        # closer than 10% to the min
        if cen < np.min(x)+0.1*scanRange:
            sane = False
        # closer than 10% to the max
        if cen > np.max(x)-0.1*scanRange:
            sane = False
        # fwhm larger than half the range
        if fwhm > 0.5*scanRange:
            sane = False

        if sane and gotofitpos:
            move = True
        if move:
            print('center: %.3f\nfwhm: %.3f (moving automatically)' % (cen, fwhm))
        else:
            print('center: %.3f\nfwhm: %.3f' % (cen, fwhm))
        # 2nd try
        if show:
            fig = plt.figure()
            ax = plt.subplot(111)
            fig.subplots_adjust(left=0.25, bottom=0.25)
            result.plot_fit(ax=ax, numpoints=200)
            ax.axvline(x=cen)
            ax.text(cen, y.min()+0.2*(y.max()-y.min()), 'center=%.3f\nFWHM=%.3f' % (cen, fwhm))
            ax.set_xlabel(motor)
            ax.set_ylabel('Intensity')
            ax.set_title(scanFileName+'\n'+str(roi))
            def moveto(self):
                plt.close(fig)
                # TODO set move=True
            if gotoButton:
                axmoveto = plt.axes([0.05, 0.7, 0.1, 0.075])
                movetoButton = Button(axmoveto, 'Moveto')
                movetoButton.on_clicked(moveto)

            plt.show(block=True)
        #if show:
        #    result.plot_fit(numpoints=200)
        #    plt.axvline(x=cen)
        #    plt.text(cen, y.min()+0.2*(y.max()-y.min()), 'center=%.3f\nFWHM=%.3f' % (cen, fwhm))
        #    plt.show()
        return {'cen': cen, 'fwhm': fwhm, 'moveto': move}
    else:
        raise ValueError('Fit did not work')


def center(direction, start, end, NoSteps, rotstart, rotend,
           exposure=2, channel=1, horizontalCenteringMotor='idty2', verticalCenteringMotor='idtz2', roi=None, auto=False):
    '''
    drives a supersweep for the vertical or horizontal DIRECTION from START to END in NOSTEPS steps
    at every step it takes a single omega integration from currentpos-SWIVEL/2 to currentpos+SWIVEL/2
    logs the result -- no it does not!
    :param direction:
    :param start:
    :param end:
    :param NoSteps:
    :param rotstart:
    :param rotend:
    :param exposure:
    :param channel:
    :param horizontalCenteringMotor:
    :param verticalCenteringMotor:
    :param roi:
    :param auto: pass on parameter, if true, then it supposed to move to the center automatically and does not show the image in the figGauss function
    :return:
    '''

    horizontal = ['horizontal', 'hor', 'h', 'y']
    vertical = ['vertical', 'vert', 'v', 'z']
    if direction.lower() in horizontal:
        mot = horizontalCenteringMotor
    elif direction.lower() in vertical:
        mot = verticalCenteringMotor
    else:
        print('ERROR: direction variable (%s) is not in\nhorizontal (%s) or\nvertical (%s) lists' %(direction, horizontal, vertical))
        return -1
    #
    # get current idrz2 motor pos
    d = _getMovableSpockNames()
    centeringMotDev = PT.DeviceProxy(d[mot])
    centeringMotInitPos = centeringMotDev.position

    print('initial %s motor position: %.3f' % (mot, centeringMotInitPos))

    #envlist = HU.runMacro('lsenv')
    #ScanDir = [l for l in envlist if 'ScanDir' in l][0].split()[1]
    #ScanID = int([l for l in envlist if 'ScanID' in l][0].split()[1])
    #ScanFile = [l for l in envlist if 'ScanFile' in l][0].split()[1].rpartition('.')[0][2:]
    ScanDir = HU.getEnv('ScanDir')
    ScanID = HU.getEnv('ScanID')
    ScanFile = HU.getEnv('ScanFile') # if fio and spec are also saved this is a list
    if isinstance(ScanFile, list):
        for i in ScanFile:
            if i.endswith('.fio'):
                ScanFile = i.replace('.fio', '')
                break

    scanFileName = ScanDir + '/' + ScanFile + '_%.05d.fio' % (ScanID+1)
    print(scanFileName)

    supersweepCommand = 'supersweep %s %.3f %.3f %d idrz1 %.3f %.3f %d:1/%.1f 4' % (mot, start, end, NoSteps, rotstart, rotend, channel, exposure)
    print(supersweepCommand)

    supersweepOut = HU.runMacro(supersweepCommand)
    time.sleep(0.1)
    fiodata, path, _ = _fioparser(scanFileName)
    path = path['%d' % channel]
    # get ROI:
    if roi is None:
        roi, roiNP = explorer(scanFileName)
    positions = fiodata[mot]
    if DEBUG:
        print('Positions: %d' % len(positions))
    res = fitGauss(scanFileName, roi, motor=mot)
    return positions, res, roi, scanFileName


def centerOmega(start, end, NoSteps, exposure=2, channel=1, roi=None, mot='idrz1(encoder)', auto=False):
    '''
    :param start:
    :param end:
    :param NoSteps:
    :param exposure:
    :param channel:
    :param roi:
    :param mot:
    :param auto: pass on parameter, if true, then it supposed to move to the center automatically and does not show the image in the figGauss function
    :return:
    '''
    ScanDir = HU.getEnv('ScanDir')
    ScanID = HU.getEnv('ScanID')
    ScanFile = HU.getEnv('ScanFile') # if fio and spec are also saved this is a list
    if isinstance(ScanFile, list):
        for i in ScanFile:
            if i.endswith('.fio'):
                ScanFile = i.replace('.fio', '')
                break

    scanFileName = ScanDir + '/' + ScanFile + '_%.05d.fio' % (ScanID+1)
    print(scanFileName)
    sweepCommand = 'fastsweep idrz1 %.3f %.3f %d:%d/%.1f 4' % (start, end, channel, NoSteps, exposure)
    print(sweepCommand)
    sweepOut = HU.runMacro(sweepCommand)
    time.sleep(0.1)
    fiodata, path, _ = _fioparser(scanFileName)
    path = path['%d' % channel]

    # get ROI:
    if roi is None:
        roi, roiNP = explorer(scanFileName)
    positions = fiodata[mot]
    if DEBUG: print('Positions: %d' % len(positions))
    res = fitGauss(scanFileName, roi, motor=mot)
    return positions, res, roi, scanFileName


def getProj(imageArray, roi, projAxis=0):
    '''
    vertical projection: axis = 0
    horizontal projection: axis = 1
    '''
    projections = []
    # the numpy convention is different than the PIL therefore the image is transposed(?)
    xmin = roi['ymin']
    xmax = roi['ymax']
    ymin = roi['xmin']
    ymax = roi['xmax']
    for i in range(imageArray.shape[0]):
        im = imageArray[i, xmin:xmax, ymin:ymax]
        projections.append(np.sum(im, axis=projAxis))
    return np.array(projections)


def showMap(fiofile, roi=None, etascale=False, maxint=None, percentile=98, save=False):
    '''
    creates a map from an already existing measurement
    '''
    d, savedir, _ = _fioparser(fiofile)
    omega = np.array(d['idrz1(encoder)'])
    omega -= (omega[1]-omega[0])/2. # shifting the omega, because only the final angles are saved for each image

    image = imagesFromFio(fiofile, channel=3)
    if not isinstance(image, str):
        raise ValueError('fio file contains several images... Supposed to be a single nxs/h5 file')
    if image.endswith('.nxs'):
        imageArray = getDataNXSLambda(image)
    if image.endswith('.h5'):
        imageArray = getEigerDataset(image)
        #raise ValueError('fio file does not point to an nxs or h5 file')
    if roi is None:
        roi, roiNP = explorer(fiofile, ROI=False)

    print("Using roi: %s"%roi)

    azimutalMap = getProj(imageArray, roi, projAxis=0)

    # Set up the axes with gridspec
    fig = plt.figure()
    grid = plt.GridSpec(4, 4, hspace=0.5, wspace=0.5)

    y_hist = fig.add_subplot(grid[:-1, 0], xticklabels=[])
    x_hist = fig.add_subplot(grid[-1, 1:], yticklabels=[])
    main_ax = fig.add_subplot(grid[:-1, 1:4], sharey=y_hist, sharex=x_hist)
    y_hist.set_ylabel('omega angle [deg]')
    main_ax.set_title('%s' % fiofile)
    main_ax.get_yaxis().set_visible(False)


    y_hist.plot(np.sum(azimutalMap[:, ::-1], axis=1), omega)



    if maxint is None:
        print('Using %.0f percentile as max' % percentile)
        maxint = np.percentile(azimutalMap[:, ::-1], percentile)

    if etascale:
        dist = 1100 # Lambda dist from direct beam [mm]
        x_hist.set_xlabel('eta [roughly scaled mdeg start set to 0]')

        plot = main_ax.imshow(azimutalMap[:, ::-1], cmap='jet', vmax=maxint, interpolation='none',
                         extent=[0, 1000*azimutalMap.shape[1]*0.055/dist, omega[0], omega[-1]], aspect='auto')
        etas = np.linspace(0,1000*azimutalMap.shape[1]*0.055/dist, azimutalMap[:, ::-1].shape[0])
        x_hist.plot(etas, np.sum(azimutalMap[:, ::-1], axis=0))
    else:
        x_hist.set_xlabel('eta [unscaled, pix]')
        plot = main_ax.imshow(azimutalMap[:, ::-1], cmap='jet', vmax=maxint, interpolation='none',
                         extent=[0, azimutalMap.shape[1], omega[-1], omega[0]], aspect='auto')
        x_hist.plot(np.arange(azimutalMap.shape[1]), np.sum(azimutalMap[:, ::-1], axis=0))

    if save:
        name = savedir['3']+image.replace('.nxs', '')
        np.save(name+'.npy', azimutalMap[:, ::-1])
        with open(name+'.meta') as meta:
            meta.write('File %s\n' % (name+'.npy'))
            meta.write('Used ROI: %s\n'%roi)
            meta.write('Omega values:\n')
            for o in omega:
                meta.write('%.4f\n'%o)
            meta.write('Radial pixels on the Lambda and rough eta in mdeg calculated with %.2f mm distance from the direct beam\n')
            for i in range(azimutalMap.shape[1]):
                meta.write('%i %.2f'%(i,1000*i*0.055/dist))

    fig.colorbar(plot)
    plt.show()



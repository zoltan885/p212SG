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

from PIL import Image
import dateutil
import os, time

try:
    import PyTango as PT
    import HasyUtils as HU
except:
    raise ImportError('Could not import PyTango or HasyUtils')


DEBUG = 1



def _getMoveableSpockNames():
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
            if rec['type'].lower() == 'stepping_motor':
                names[rec['name'].lower()] = rec['device'].lower()
    except:
        pass
    return names




def _fioparser(fn=None):
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
                        if 'exposure' in lines[l]: # poorly written filter for exposure frames
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
    
    return data, savedir


def imagesFromFio(fiofile, channel=1):
    data, savedir = _fioparser(fiofile)
    # lambda or only one tif image
    if len(set(data['filename'])) == 1:
        channel=3
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


def explorer(imsource, ROI=False):
    """
    function for initial grain hunt
    shows the list of images with a slider to inspect them individually
    
    TODO:
        could work with keybord
        if ROI is already given it should show a rectangle
    """
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, Button, RadioButtons
    
    tif,nxs = False,False
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
            il = imagesFromFio(imsource)
            print(il)
            if isinstance(il, str):
                if il.endswith('nxs'):
                    data = getDataNXSLambda(il)
                    nxs = True 
            elif isinstance(il, list):
                imageList = il
                tif = True
    else:
        raise ValueError('Source format not recognized.')
    
    
    #if tif and DEBUG: print(imageList)
    
    # generate figure
    fig = plt.figure()
    ax = plt.subplot(111)
    fig.subplots_adjust(left=0.25, bottom=0.25)

    # select first image
    if tif:
        im = np.array(Image.open(imageList[0]))
        ax.set_title(imageList[0].rpartition('/')[2])
    if nxs:
        im = np.array(data[0])
        ax.set_title(0)
    
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
    if nxs: noImages = data.shape[0]
    
    ax2 = fig.add_axes([0.25, 0.05, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    imSlider = Slider(ax2, 'image', 0, noImages - 1, valinit=0, valfmt='%i')
    def updateImage(val):
        indx = int(np.round(val))
        if tif:
            im = np.array(Image.open(imageList[indx]))
            ax.set_title(imageList[indx].rpartition('/')[2])
        if nxs:
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
                sumi = np.maximum(sumi, np.array(Image.open(i)))
        if nxs:
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
                avei = np.sum((avei, np.array(Image.open(i))), axis=0)
        if nxs:
            for i in noImages:
                avei = np.sum(avei, data[i], axis=0)
            
        avei = avei / len(imageList)
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


def getDataNXSLambda(filename):
    try:
        import h5py
    except:
        raise ImportError('Could not import h5py')

    nxs = h5py.File(filename)
    data = np.array(nxs['entry/instrument/detector/data'])
    return data


def getDataTIF(listOfImages):
    data = []
    for i in listOfImages:
        data.append(np.array(Image.open(i)))
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
    tif,nxs = False,False
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
            il = imagesFromFio(imsource)
            print(il)
            if isinstance(il, str):
                if il.endswith('nxs'):
                    data = getDataNXSLambda(il)
                    nxs = True 
            elif isinstance(il, list):
                imageList = il
                tif = True
    else:
        raise ValueError('Source format not recognized.')
    
    print(':getIntensities: tif/nxs' , tif, nxs)
    
    intensities = []
    if tif:
        for i in imageList:
            im = np.array(Image.open(i))
            intensities.append(integrateROI(im, roi))
    elif nxs:
        for i in range(data.shape[0]):
            im = data[i]
            intensities.append(integrateROI(im, roi))
    
    return np.array(intensities)



def fitGauss(imsource, roi, positions, show=True, gotoButton=True):
    try:
        from lmfit.models import GaussianModel, LinearModel
    except:
        raise ImportError('Could not import lmfit.models')
    
    y = getIntensities(imsource, roi)
    #x = np.arange(len(y))
    x = positions
    gmod = GaussianModel(prefix='peak_')
    lmod = LinearModel(prefix='line_')

    print(len(x), len(y))
    
    pars = gmod.guess(y, x=x)
    pars += lmod.guess(y, x=x)
    # peak_center parameter is restricted to the data region
    #pars['peak_center'].set(x[np.argmax(y)], min = np.min(x), max = np.max(x))
    mod = lmod + gmod
    
    #print(x, y)
    #print(pars)
    
    result = mod.fit(y, pars, x=x)
    
    if result.success:
        cen = result.best_values['peak_center']
#        cen_err = pars['peak_center'].stderr
        amp = result.best_values['peak_amplitude']
        fwhm = 2.3557*result.best_values['peak_sigma']
        # sanity check
        sane = True
        scanRange = (np.max(positions)-np.min(positions))
        # closer than 10% to the min
        if cen < np.min(positions)+0.1*scanRange:
            sane = False
        # closer than 10% to the max
        if cen > np.max(positions)-0.1*scanRange:
            sane = False
        # fwhm larger than half the range
        if fwhm > 0.5*scanRange:
            sane = False
        
        
        if show:
            result.plot_fit(numpoints=200)
            plt.axvline(x=cen)
            plt.text(cen, y.min()+0.2*(y.max()-y.min()), 'center=%.3f\nFWHM=%.3f' % (cen, fwhm))
            plt.show()
        print('center: %.3f\nfwhm: %.3f' % (cen, fwhm))
        return cen
    else:
        raise ValueError('Fitting did not work')





def center(direction, start, end, NoSteps, rotstart, rotend, 
           exposure=2, channel=1, horizontalCenteringMotor='idty2', verticalCenteringMotor='idtz2', roi=None):
    '''
    drives a supersweep for the vertical or horizontal DIRECTION from START to END in NOSTEPS steps
    at every step it takes a single omega integration from currentpos-SWIVEL/2 to currentpos+SWIVEL/2
    logs the result -- no it does not!
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
    d = _getMoveableSpockNames()
    centeringMotDev = PT.DeviceProxy(d[mot])
    centeringMotInitPos = centeringMotDev.position
    
    print('initial %s motor position: %.3f' % (mot, centeringMotInitPos))
    
    envlist = HU.runMacro('lsenv')
    ScanDir = [l for l in envlist if 'ScanDir' in l][0].split()[1]
    ScanID = int([l for l in envlist if 'ScanID' in l][0].split()[1])
    ScanFile = [l for l in envlist if 'ScanFile' in l][0].split()[1].rpartition('.')[0][2:]
    
    scanFileName = ScanDir + '/' + ScanFile + '_%.05d.fio' % (ScanID+1)
    print(scanFileName)
    
    supersweepCommand = 'supersweep %s %.3f %.3f %d idrz1 %.3f %.3f %d:1/%.1f 4' % (mot, start, end, NoSteps, rotstart, rotend, channel, exposure)
    print(supersweepCommand)
    

    
    supersweepOut = HU.runMacro(supersweepCommand)
    time.sleep(0.1)
    fiodata, path = _fioparser(scanFileName)
    path = path['%d' % channel] 
    
    # get ROI:
    if roi is None:
        roi, roiNP = explorer(scanFileName)
    

    positions = fiodata[mot]
    if DEBUG: print('Positions: %d' % len(positions))

    fitGauss(scanFileName, roi, positions)    

    return positions, roi


def centerOmega(start, end, NoSteps, exposure=2, channel=1, roi=None, mot='idrz1(encoder)'):
    envlist = HU.runMacro('lsenv')
    ScanDir = [l for l in envlist if 'ScanDir' in l][0].split()[1]
    ScanID = int([l for l in envlist if 'ScanID' in l][0].split()[1])
    ScanFile = [l for l in envlist if 'ScanFile' in l][0].split()[1].rpartition('.')[0][2:]
    
    scanFileName = ScanDir + '/' + ScanFile + '_%.05d.fio' % (ScanID+1)
    print(scanFileName)
    sweepCommand = 'fastsweep idrz1 %.3f %.3f %d:%d/%.1f 4' % (start, end, channel, NoSteps, exposure)
    print(sweepCommand)
    
    
    sweepOut = HU.runMacro(sweepCommand)
    time.sleep(0.1)
    fiodata, path = _fioparser(scanFileName)
    path = path['%d' % channel] 
    
    # get ROI:
    if roi is None:
        roi, roiNP = explorer(scanFileName)
    
    positions = fiodata[mot]
    if DEBUG: print('Positions: %d' % len(positions))

    cen = fitGauss(scanFileName, roi, positions)    

    return cen, roi


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


def showMap(fiofile, roi=None, etascale=False, save=False):
    '''
    creates a map from an already existing measurement
    '''

    d, savedir = _fioparser(fiofile)
    omega = np.array(d['idrz1(encoder)'])
    omega += (omega[1]-omega[0])/2. # shifting the omega, because the only the starting angles are saved

    image = imagesFromFio(fiofile, channel=3)
    if not isinstance(image, str):
        raise ValueError('fio file contains several images... Supposed to be a single nxs file')
    if not image.endswith('.nxs'):
        raise ValueError('fio file does not point to an nxs file')
    imageArray = getDataNXSLambda(image)

    if roi is None:
        roi, roiNP = explorer(fiofile, ROI=False)

    print("Using roi: %s"%roi)

    azimutalMap = getProj(imageArray, roi, projAxis=0)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax.set_ylabel('omega angle [deg]')
    
    if etascale:
        dist = 1100 # Lambda dist from direct beam [mm]
        ax.set_xlabel('eta [roughly scaled mdeg start set to 0]')
        plot = ax.imshow(azimutalMap[:, ::-1], cmap='jet', vmax=200, interpolation='none',
                         extent=[0, 1000*azimutalMap.shape[1]*0.055/dist, omega[0], omega[-1]], aspect='auto')
    else:
        ax.set_xlabel('eta [unscaled, pix]')
        plot = ax.imshow(azimutalMap[:, ::-1], cmap='jet', vmax=200, interpolation='none',
                         extent=[0, azimutalMap.shape[1], omega[0], omega[-1]], aspect='auto')

    if save:
        name = savedir+image.replace('.nxs', '')
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





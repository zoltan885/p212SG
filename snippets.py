#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 12 18:36:18 2020

@author: hegedues
"""

def tifexplorer_old(imageList):
    """
    function for initial grain hunt
    shows the list of images with a slider to inspect them individually
    """
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, Button, RadioButtons
    
    # generate figure
    fig = plt.figure()
    ax = plt.subplot(111)
    fig.subplots_adjust(left=0.25, bottom=0.25)

    # select first image
    im = np.array(Image.open(imageList[0]))
    ax.set_title(imageList[0].rpartition('/')[2])
    
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
    
    ax2 = fig.add_axes([0.25, 0.05, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    imSlider = Slider(ax2, 'image', 0, len(imageList) - 1, valinit=0, valfmt='%i')
    def updateImage(val):
        indx = int(np.round(val))
        im = np.array(Image.open(imageList[indx]))
        #print('Update image to %s' % (imageList[indx]))
        ax.set_title(imageList[indx].rpartition('/')[2])
        plot.set_data(im)
        fig.canvas.draw()

    imSlider.on_changed(updateImage)
    plt.show(block=True)


def nxsexplorer(nexusfile):
    data = getDataNXSLambda(nexusfile)
    print(data.shape)
    
    # generate figure
    fig = plt.figure()
    ax = plt.subplot(111)
    fig.subplots_adjust(left=0.25, bottom=0.25)

    # select first image
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
    
    ax2 = fig.add_axes([0.25, 0.05, 0.65, 0.03], facecolor='lightgoldenrodyellow')
    imSlider = Slider(ax2, 'image', 0, data.shape[0] - 1, valinit=0, valfmt='%i')
    def updateImage(val):
        indx = int(np.round(val))
        im = data[indx]
        #print('Update image to %s' % (imageList[indx]))
        ax.set_title(indx)
        plot.set_data(im)
        fig.canvas.draw()

    imSlider.on_changed(updateImage)
    plt.show(block=True)
# next image with arrows:
# https://stackoverflow.com/questions/6697259/interactive-matplotlib-plot-with-two-sliders    





def getROI(showROI=False):
    '''
    Shows the image for the user to select a ROI with the magnifying glass
    Has two sliders to set the colorscale min and max values
    '''
    i = np.array(Image.open('/home/p212user/data/sg_test/PE1_al14_00454.tif'))
    #if len(path) > 0 and path[-1]=='/':
    #    filename = path + imfile
    #else:
    #    filename = path + '/' + imfile
    
    #i = np.array(Image.open(filename))

    

    def on_xlims_change(axes):
        limits['xmin'] = int(np.floor(ax.get_xlim()[0]))
        limits['xmax'] = int(np.ceil(ax.get_xlim()[1]))
        #print("updated xlims: ", ax.get_xlim())

    def on_ylims_change(axes):
        limits['ymin'] = int(np.floor(ax.get_ylim()[1]))
        limits['ymax'] = int(np.ceil(ax.get_ylim()[0]))
        #print("updated ylims: ", ax.get_ylim())

    limits={'xmin':0, 'xmax':10000, 'ymin':0, 'ymax':10000}

    fig = plt.figure()
    ax = fig.add_subplot(111)
#    fig, ax = plt.subplots(111)
    fig.subplots_adjust(left=0.25, bottom=0.25)
    plot = ax.imshow(i, vmin=0, vmax=i.max()/5, cmap='jet')
    fig.colorbar(plot)
    
    axmin = fig.add_axes([0.25, 0.1, 0.65, 0.03])
    axmax  = fig.add_axes([0.25, 0.15, 0.65, 0.03])
    
    smin = Slider(axmin, 'Min', 0, i.max(), valinit=0)
    smax = Slider(axmax, 'Max', 0, i.max(), valinit=i.max()/5)

    def update(val):
        plot.set_clim([smin.val,smax.val])
        fig.canvas.draw()
    smin.on_changed(update)
    smax.on_changed(update)
    ax.callbacks.connect('xlim_changed', on_xlims_change)
    ax.callbacks.connect('ylim_changed', on_ylims_change)
    plt.show(block=True)

    print("Selected ROI:")
    print("x: %d -- %d" %(limits['xmin'], limits['xmax']))
    print("y: %d -- %d" %(limits['ymin'], limits['ymax']))
    
    if showROI:
        fig, ax = plt.subplots(1)
        ax.imshow(i, vmin=0, vmax=i.max()/5, cmap='jet')
    
        p = Rectangle((limits['xmin'], limits['ymin']), 
                      limits['xmax']-limits['xmin'], limits['ymax']-limits['ymin'], 
                      edgecolor='r', facecolor='none')
        ax.add_patch(p)
    
        plt.show(block=True)
    #ca = plt.gca()
    #ca.add_pathc(p)
    limitsNP = {'xmin':limits['ymin'], 'xmax':limits['ymax'], 'ymin':limits['xmin'], 'ymax':limits['xmax']}

    return limits, limitsNP


def getIntensities(imageArray, roi):
    #ov, dar, imgs = getFilelist(folder)
    intensities = []
    for i in range(imageArray.shape[0]):
        intensities.append(integrateROI(imageArray[i,:,:], roi))
    
    return np.array(intensities)





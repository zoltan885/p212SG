import sys
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication, QGridLayout
from PySide6.QtCore import QPointF
from pyqtgraph.Qt import QtGui
import pyqtgraph as pg
import numpy as np
import lmfit
import time
from functools import partial
import h5py
import fabio

uiclass, baseclass = pg.Qt.loadUiType("interface.ui")

def gaussian(x, mu, sig, noise=0):
    y = (1.0 / (np.sqrt(2.0 * np.pi) * sig) * np.exp(-np.power((x - mu) / sig, 2.0) / 2))
    y_n = y + noise * np.random.normal(size=y.shape)
    return x, y_n

def fit_gaussian(x, y):
    model = lmfit.models.GaussianModel()
    params = model.guess(y, x=x)
    result = model.fit(y, params, x=x)
    return result



class MainWindow(uiclass, baseclass):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.plot1d()
        self.plot2d()
        self.ploth5('/home/hegedues/prog/p212SG/test.h5')
        self.proxies = []
        self.populateTree()
        

        self.proxies.append(pg.SignalProxy(self.mapplot.scene().sigMouseMoved, rateLimit=10, slot=self.mapHoverEvent))
        self.mapplot.scene().sigMouseMoved.connect(self.mapHoverEvent)

        self.proxies.append(pg.SignalProxy(self.imsplot.scene().sigMouseMoved, rateLimit=10, slot=self.imsHoverEvent))
        self.imsplot.scene().sigMouseMoved.connect(self.imsHoverEvent)
        
        # this seems to work, alebeit not very elegant, the widgets, spinboxes and infLines are hardcoded
        plw = [self.widget_plot4, self.widget_plot5, self.widget_plot6]
        spinBoxes = [self.spinBox_1, self.spinBox_2, self.spinBox_3]
        
        for p,s,l in zip(plw, spinBoxes, self.infLines):
            self.proxies.append(pg.SignalProxy(p.scene().sigMouseMoved, rateLimit=10, slot=partial(self.centerHoverEvent, plotWidget=p,infLine=l, spinBox=s)))
            p.scene().sigMouseMoved.connect(partial(self.centerHoverEvent, plotWidget=p, infLine=l, spinBox=s))

        for p,s,l in zip(plw, spinBoxes, self.infLines):
            #s.valueChanged.connect(lambda x: self.updateh5plot(s.value()))
            s.valueChanged.connect(partial(self.updateVline, plotWidget=p, infLine=l))
        



        self.spinBox_1.valueChanged.connect(self.updateh5plot1)
        self.checkBox_4.stateChanged.connect(self.updateh5plot1)
        self.checkBox_maxproj_1.stateChanged.connect(self.updateh5plot1)

        self.spinBox_2.valueChanged.connect(self.updateh5plot2)
        self.checkBox_5.stateChanged.connect(self.updateh5plot2)
        self.checkBox_maxproj_2.stateChanged.connect(self.updateh5plot2)

        self.spinBox_3.valueChanged.connect(self.updateh5plot3)
        self.checkBox_6.stateChanged.connect(self.updateh5plot3)
        self.checkBox_maxproj_3.stateChanged.connect(self.updateh5plot3)

        #### TypeError: MainWindow.updateh5plot() got multiple values for argument 'h5data'

        # h5data = [self.h5data1, self.h5data2, self.h5data3]
        # image = [self.h5img1, self.h5img2, self.h5img3]
        # spinbox = [self.spinBox_1, self.spinBox_2, self.spinBox_3]
        # checkbox_max = [self.checkBox_maxproj_1, self.checkBox_maxproj_2, self.checkBox_maxproj_3]
        # checkbox_auto = [self.checkBox_4, self.checkBox_5, self.checkBox_6]
        # for h5d, im, sp, cm, ca in zip(h5data, image, spinbox, checkbox_max, checkbox_auto):
        #     sp.valueChanged.connect(partial(self.updateh5plot, h5data=h5d, image=im, spinbox=sp, checkbox_max=cm, checkbox_auto=ca))
        #     cm.stateChanged.connect(partial(self.updateh5plot, h5data=h5d, image=im, spinbox=sp, checkbox_max=cm, checkbox_auto=ca))
        #     ca.stateChanged.connect(partial(self.updateh5plot, h5data=h5d, image=im, spinbox=sp, checkbox_max=cm, checkbox_auto=ca))


    def getData(self):
        pass

    def console(self):
        namespace = {'pg': pg, 'np': np}
        text = """
        This is an interactive python console. The numpy and pyqtgraph modules have already been imported 
        as 'np' and 'pg'. 

        Go, play.
        """
        self.console = pg.console.ConsoleWidget(namespace=namespace, text=text)
        # embed ipython console:
        #https://www.tutorialspoint.com/jupyter/embedding_ipython.htm
        # better yet:
        # https://qtconsole.readthedocs.io/en/stable/

    def plot1d(self):
        self.infLines = [pg.InfiniteLine(movable=True, angle=90, pen='g'),
                         pg.InfiniteLine(movable=True, angle=90, pen='g'),
                         pg.InfiniteLine(movable=True, angle=90, pen='g')]
        self.centerPlots = {'y': 
                                {'data': gaussian(np.linspace(0,10,30), 5, 1, 0.01),
                                 'plot': [self.widget_plot1, self.widget_plot4],
                                 'details': [1], # determines later which plot widget is a detailed view
                                 'log': self.textEdit_1,
                                 'ScanID': 1001,
                                 'fitresult': None,
                                 'pen': (255,0,0),
                                 'plotdata': None},
                            'z': {'data': gaussian(np.linspace(0,10,20), 4, 2, 0.015),
                                  'plot': [self.widget_plot2, self.widget_plot5],
                                  'details': [1],
                                  'log': self.textEdit_2,
                                  'ScanID': 1002,
                                  'fitresult': None,
                                  'pen': (0,255,0),
                                  'plotdata': None},
                            'omega': {'data': gaussian(np.linspace(0,10,20), 6, 3, 0.01),
                                      'plot': [self.widget_plot3, self.widget_plot6],
                                      'details': [1],
                                      'log': self.textEdit_3,
                                      'ScanID': 1003,
                                      'fitresult': None,
                                      'pen': (255,255,0),
                                      'plotdata': None},
                            }

        for i,(k,v) in enumerate(self.centerPlots.items()):
            # fit the gaussian curves
            v['fitresult'] = fit_gaussian(*v['data'])
            # log the fit results
            v['log'].setText(time.asctime()+'\n')
            v['log'].append(str(v['fitresult'].fit_report()))

            # plot the results 
            for j,p in enumerate(v['plot']):
                p.clear()
                p.setLabel("left", "Intensity")
                p.setLabel("bottom", f"{k.capitalize()} motor position")
                p.showGrid(x=True, y=True)
                p.setTitle(f"{str(v['ScanID'])}.fio: {v['fitresult'].params['center'].value:.2f} +/- {v['fitresult'].params['center'].stderr:.2f}")
                v['plotdata'] = p.plot(v['data'][0], v['data'][1], name=f"{k} motor position", symbolBrush=v['pen'], symbolPen='w', pen=None)
                p.plot(np.linspace(v['data'][0][0], v['data'][0][-1], 100), v['fitresult'].eval(x=np.linspace(v['data'][0][0], v['data'][0][-1], 100)), pen=v['pen'])
                if j in v['details']:
                    p.addItem(self.infLines[i])


    def populateTree(self):
        i1  = QtWidgets.QTreeWidgetItem(["Item 1"])
        i11  = QtWidgets.QTreeWidgetItem(["Item 1.1"])
        i12  = QtWidgets.QTreeWidgetItem(["Item 1.2"])
        i2  = QtWidgets.QTreeWidgetItem(["Item 2"])
        i21  = QtWidgets.QTreeWidgetItem(["Item 2.1"])
        i211  = pg.TreeWidgetItem(["Item 2.1.1"])
        i212  = pg.TreeWidgetItem(["Item 2.1.2"])
        i22  = pg.TreeWidgetItem(["Item 2.2"])
        i3  = pg.TreeWidgetItem(["Item 3"])
        i4  = pg.TreeWidgetItem(["Item 4"])
        i5  = pg.TreeWidgetItem(["Item 5"])
        b5 = QtWidgets.QPushButton('Button')
        i5.setWidget(1, b5)
        d1 = QtWidgets.QComboBox()
        li = ['fio1', 'fio2', 'fio3']
        d1.addItems(li)
        # for i in li:
        #     d1.addItems(i)
        i3.setWidget(1, d1)


        w = self.widget_pgtree
        w.setColumnCount(2)
        w.addTopLevelItem(i1)
        w.addTopLevelItem(i2)
        w.addTopLevelItem(i3)
        w.addTopLevelItem(i4)
        w.addTopLevelItem(i5)
        i1.addChild(i11)
        i1.addChild(i12)
        i2.addChild(i21)
        i21.addChild(i211)
        i21.addChild(i212)
        i2.addChild(i22)

        b1 = QtWidgets.QPushButton("Button")
        w.setItemWidget(i1, 1, b1)
        b21 = QtWidgets.QPushButton('My button')
        w.setItemWidget(i21, 1, b21)


    def plot2d(self):
        # https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/imageitem.html
        # 
        # self.glw1 is a promoted pg.GraphicsLayoutWidget
        self.mapTr = QtGui.QTransform()  # prepare ImageItem transformation:
        self.mapTr.scale(0.5, 2.0)       # scale horizontal and vertical axes
        self.mapTr.translate(-100, -200)       # shift image
        
        self.mapdata = np.random.normal(size=(200, 400))
        self.mapimg = pg.ImageItem(image=self.mapdata)
        self.mapimg.setTransform(self.mapTr) # assign transformation to ImageItem
        
        self.mapplot = self.glw1.addPlot()
        self.mapplot.addItem(self.mapimg)
        self.mapLUT = pg.HistogramLUTItem(image=self.mapimg)
        self.mapLUT.imageItem().setLookupTable('flame')
        self.glw1.addItem(self.mapLUT, row=0, col=1)


        # self.glw2 is a promoted pg.GraphicsLayoutWidget
        self.imsTr = QtGui.QTransform()  # prepare ImageItem transformation:
        self.imsTr.scale(1, 1.0)       # scale horizontal and vertical axes
        self.imsTr.translate(-250, -500)       # shift image
        
        self.imsdata = 10*np.random.normal(size=(500, 1000))+100
        self.imsimg = pg.ImageItem(image=self.imsdata)
        self.imsimg.setTransform(self.imsTr) # assign transformation to ImageItem
        
        self.imsplot = self.glw2.addPlot()
        self.imsplot.addItem(self.imsimg)
        self.imsLUT = pg.HistogramLUTItem(image=self.imsimg)
        self.imsLUT.imageItem().setLookupTable('flame')
        self.glw2.addItem(self.imsLUT, row=0, col=1)


    def ploth5(self, h5file):
        #data = np.array(h5py.File(h5file)['entry/data/data'])
        self.h5data1 = fabio.open(h5file)
        self.h5img1 = pg.ImageItem(image=np.clip(self.h5data1.data, max=100))
        h5plot = self.glw3.addPlot()
        h5plot.addItem(self.h5img1)
        self.h5LUT1 = pg.HistogramLUTItem(image=self.h5img1, orientation='horizontal')
        self.h5LUT1.imageItem().setLookupTable('flame')
        self.glw3.addItem(self.h5LUT1, row=1, col=0)

        self.h5data2 = fabio.open(h5file)
        self.h5img2 = pg.ImageItem(image=np.clip(self.h5data2.data, max=100))
        h5plot = self.glw4.addPlot()
        h5plot.addItem(self.h5img2)
        self.h5LUT2 = pg.HistogramLUTItem(image=self.h5img2, orientation='horizontal')
        self.h5LUT2.imageItem().setLookupTable('flame')
        self.glw4.addItem(self.h5LUT2, row=1, col=0)

        self.h5data3 = fabio.open(h5file)
        self.h5img3 = pg.ImageItem(image=np.clip(self.h5data3.data, max=100))
        h5plot = self.glw5.addPlot()
        h5plot.addItem(self.h5img3)
        self.h5LUT3 = pg.HistogramLUTItem(image=self.h5img3, orientation='horizontal')
        self.h5LUT3.imageItem().setLookupTable('flame')
        self.glw5.addItem(self.h5LUT3, row=1, col=0)

    def updateh5plot(self, h5data=None, image=None, spinbox=None, checkbox_max=None, checkbox_auto=None, usemask=False):
        if checkbox_max.isChecked(): # max projection
            # TODO implement mask
            currentim = np.max([np.clip(h5data.get_frame(i).data, max=100) for i in range(30)], axis=0)
        else:
            # TODO implement mask
            currentim = np.clip(h5data.get_frame(spinbox.value()).data, max=100)
        image.setImage(np.clip(currentim, max=100), autoLevels=checkbox_auto.isChecked(), autoRange=False)

    def updateh5plot1(self):
        # the GraphicsLayoutWidget contains the PlotItem, which should contain the ImageItem, but I can't get to it
        #data = self.glw3.getItem(0,0).
        #print(type(data))
        #print(type(self.h5img))
        h5data = self.h5data1
        image = self.h5img1
        spinbox = self.spinBox_1
        checkbox_max = self.checkBox_maxproj_1
        checkbox_auto = self.checkBox_4
        if checkbox_max.isChecked(): # max projection
            currentim = np.max([np.clip(h5data.get_frame(i).data, max=100) for i in range(30)], axis=0)
        else:
            currentim = np.clip(h5data.get_frame(spinbox.value()).data, max=100)
        image.setImage(np.clip(currentim, max=100), autoLevels=checkbox_auto.isChecked(), autoRange=False)

    def updateh5plot2(self):
        h5data = self.h5data2
        image = self.h5img2
        spinbox = self.spinBox_2
        checkbox_max = self.checkBox_maxproj_2
        checkbox_auto = self.checkBox_5
        if checkbox_max.isChecked(): # max projection
            currentim = np.max([np.clip(h5data.get_frame(i).data, max=100) for i in range(30)], axis=0)
        else:
            currentim = np.clip(h5data.get_frame(spinbox.value()).data, max=100)
        image.setImage(np.clip(currentim, max=100), autoLevels=checkbox_auto.isChecked(), autoRange=False)
    
    def updateh5plot3(self):
        h5data = self.h5data3
        image = self.h5img3
        spinbox = self.spinBox_3
        checkbox_max = self.checkBox_maxproj_3
        checkbox_auto = self.checkBox_6
        if checkbox_max.isChecked(): # max projection
            currentim = np.max([np.clip(h5data.get_frame(i).data, max=100) for i in range(30)], axis=0)
        else:
            currentim = np.clip(h5data.get_frame(spinbox.value()).data, max=100)
        image.setImage(np.clip(currentim, max=100), autoLevels=checkbox_auto.isChecked(), autoRange=False)


    def updateVline(self, value:int=None, plotWidget:pg.PlotWidget=None, infLine:pg.InfiniteLine=None):
        data = plotWidget.getPlotItem().listDataItems()[0]
        x = data.xData # could also use getOriginalDataset() to get the original data
        y = data.yData
        try:
            infLine.setPos(x[value])
        except IndexError:
            pass

    def mapHoverEvent(self, event):
        pos = event
        if isinstance(event, tuple):
            pos = event[0]
        if self.mapplot.sceneBoundingRect().contains(pos):
            mousePoint = self.mapplot.vb.mapSceneToView(pos)
            x, y = mousePoint.x(), mousePoint.y()
            #px, py = self.mapimg.mapFromScene(pos)
            #i = int(np.clip(px, 0, self.mapdata.shape[0] - 1))
            #j = int(np.clip(py, 0, self.mapdata.shape[1] - 1))
            #val = self.mapdata[i, j]
            #self.label_status_right.setText(f'pos: ({x:.1f}, {y:.1f})  pixel: ({i:d}, {j:d})  value: {val:.1g}')
            self.label_status_right.setText(f'pos: ({x:.1f}, {y:.1f})')
        else:
            self.label_status_right.setText('')

    def imsHoverEvent(self, event):
        pos = event
        if isinstance(event, tuple):
            pos = event[0]
        if self.imsplot.sceneBoundingRect().contains(pos):
            mousePoint = self.imsplot.vb.mapSceneToView(pos)
            x, y = mousePoint.x(), mousePoint.y()
            self.label_status_right.setText('%.1f     %.4g' % (x, y))
        else:
            self.label_status_right.setText('')

    def centerHoverEvent(self, event, plotWidget:pg.PlotWidget=None, infLine:pg.InfiniteLine=None, spinBox=None):
        # event is mostly of type QPointF, but sometimes a messed up tuple!!!
        pos = event
        if isinstance(event, tuple):
            pos = event[0]
        if plotWidget.sceneBoundingRect().contains(pos):
            mousePoint = plotWidget.plotItem.vb.mapSceneToView(pos)
            xx = mousePoint.x()
            widget_data = plotWidget.getPlotItem().listDataItems()[0]
            pts = widget_data.xData # could also use getOriginalDataset() to get the original data
            try:
                index = np.searchsorted(pts, xx, side="left")
                position = pts[index]
            except IndexError:
                index = len(pts) - 1
                position = pts[-1]
            self.label_status_right.setText(f'{position=:.4f} {index=:d}')
            spinBox.setValue(index)
            infLine.setPos(position)
        else:
            self.label_status_right.setText('')
  

    def closeEvent(self, event):
        self.close()
        event.accept()




app = QApplication(sys.argv)
window = MainWindow()
window.show()
app.exec()






'''
Notes:
add button to tree view:
https://stackoverflow.com/questions/59202334/python-pyqt5-is-it-possible-to-add-a-button-to-press-inside-qtreeview

callback function with arguments:
https://stackoverflow.com/questions/69852292/pyqt-how-do-i-get-which-element-triggered-a-callback-function-when-many-elemen

'''
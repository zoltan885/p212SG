
import gui_data
import json
import traceback
import time

def printerr(e):
    print('\33[31m\n')
    print(traceback.format_exc())
    print('\33[37m\n')

def printpass(test):
    print('\33[36m')
    print(f'\n{test.upper()} PASSED\n')
    print('\33[37m')


if __name__ == "__main__":
    import sys
    import os
    errorMess = f'This is a module. For testing use:\npython {sys.argv[0]} --test\nor\npython {sys.argv[0]} --testdbmod'
    if len(sys.argv) == 1:
        sys.exit(errorMess)
    if sys.argv[1] not in ['--test', '--testdbmod']:
        sys.exit(errorMess)
    if sys.argv[1] == '--test':
        gsd = gui_data.grainStateData()
        
        ### read_fios()
        # add a fio file
        print('\n\nREAD FIOS\n\n')
        try:
            gsd.data.centerYs[-1]['fiofile'] = '/home/hegedues/prog/p212SG/fs2_abtg_00055.fio'
            gsd.read_fios()
            gsd.update_empty()
            # add another fio file to the same type
            gsd.data.centerYs.append(gui_data._centeringData())
            gsd.data.centerYs[-1]['fiofile'] = '/home/hegedues/prog/p212SG/fs2_abtg_00056.fio'
            gsd.read_fios()
            gsd.update_empty()
            # add another fio file to another type
            gsd.data.centerZs[-1]['fiofile'] = '/home/hegedues/prog/p212SG/fs2_abtg_00057.fio'
            gsd.read_fios()
            gsd.update_empty()
            print(json.dumps(gsd.empty, indent=4))
            printpass('read_fios')
        except Exception as e:
            printerr(e)
            print(gsd)
            print(json.dumps(gsd.empty, indent=4))
            

        ### load_h5()
        print('\n\nLOAD H5\n\n')
        try:
            gsd.load_h5(gsd.data.centerYs[-1]['fiofile'], test=True)
            gsd.update_empty()
            gsd.load_h5(gsd.data.centerYs[0]['fiofile'], test=True)
            gsd.update_empty()
            gsd.load_h5(gsd.data.centerZs[-1]['fiofile'], test=True)
            gsd.update_empty()
            printpass('load_h5')
        except Exception as e:
            printerr(e)
            print(json.dumps(gsd.empty, indent=4))


        ### get_intensity()
        print('\n\nGET INTENSITY\n\n')
        try:
            x,y,roi = gsd.get_intensity('/home/hegedues/prog/p212SG/fs2_abtg_00055.fio', test=True)
            #print(f'{x=}\n{y=}\n{roi=}\n')
            # add roi
            gsd.rois.append(gui_data.ROI(0, 0, 100, 100))
            x,y,roi = gsd.get_intensity('/home/hegedues/prog/p212SG/fs2_abtg_00055.fio', test=True)
            #print(f'{x=}\n{y=}\n{roi=}\n')
            gsd.update_empty()
            printpass('get_intensity')
        except Exception as e:
            printerr(e)
            print(gsd)
            print(json.dumps(gsd.empty, indent=4))

        ### fit_center()
        print('\n\nFIT CENTER\n\n')
        try:
            gsd.fit_center('/home/hegedues/prog/p212SG/fs2_abtg_00055.fio', test=True)
            gsd.fit_center('/home/hegedues/prog/p212SG/fs2_abtg_00056.fio', bg='constant', test=True)
            gsd.fit_center('/home/hegedues/prog/p212SG/fs2_abtg_00057.fio', bg='linear', test=True)
            gsd.update_empty()
            printpass('fit_center')
        except Exception as e:
            printerr(e)
            print(gsd)
            print(json.dumps(gsd.empty, indent=4))
        
        ### set_save_path()
        print('\n\nSET SAVE PATH\n\n')
        try:
            gsd._set_save_path('/tmp/test/')
            gsd._set_save_path('/home/hegedues/prog/p212SG/testdir/')
            printpass('_set_save_path')
        except Exception as e:
            printerr(e)
        
        ### _save_to_file()
        print('\n\nSAVE TO FILE\n\n')
        try:
            gsd._save_to_file('testfile')
            printpass('_save_to_file')
        except Exception as e:
            printerr(e)

        ### check_JSON_modification()
        print('\n\nCHECK JSON MODIFICATION\n\n')
        try:
            difference = gsd._check_JSON_modification()
        except Exception as e:
            printerr(e)
            sys.exit()
        if difference != {}:
            print('\33[31m\n')
            print('Checking JSON modification failed')
            print('\33[37m\n')
            print(json.dumps(difference, indent=4))
            #sys.exit('Difference is not empty')
        #something is wrong if it read back json is already different
        if False:
            if difference:
                print('\33[31m\n')
                print('Checking JSON modification failed')
                print('\33[37m\n')
                print('Difference:\n')
                print(json.dumps(difference, indent=4))
                print('Live one:\n')
                print(json.dumps(gsd.empty, indent=4))
            if difference == {}:
                try:
                    print('Waiting for JSON modification...')
                    while not gsd._check_JSON_modification():
                        time.sleep(1)
                except KeyboardInterrupt as e:
                    print('KeyboardInterrupt')
                except Exception as e:
                    printerr(e)
        
        ### _check_JSON_corruption()
        print('\n\nCHECK JSON CORRUPTION\n\n')
        print('Not yet tested')

        ### update_data()
        print('\n\nUPDATE DATA\n\n')
        try:
            gsd.update_data()
            printpass('update_data')
        except Exception as e:
            printerr(e)
            print(gsd.data.centerYs[0])
            sys.exit()

    

        
        
        
        sys.exit()


        x,y,roi = gsd.get_intensity('/home/hegedues/prog/p212SG/fs2_abtg_00055.fio', test=True)
        print(f'{x=}\n{y=}\n{roi=}\n')
        gsd.read_fios()
        gsd.update_empty() # works!

        print(f'\nData object:\n')
        print(gsd)
        print(f'\nDatabase object:\n')
        print(json.dumps(gsd.empty, indent=4))



# terminal colors: https://askubuntu.com/questions/27314/script-to-display-all-terminal-colors
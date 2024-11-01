import unittest
from _fiosupport import fio
import os

class TestFio(unittest.TestCase):

    def setUp(self):
        # Create a sample fio file for testing
        self.test_file = 'test.fio'
        with open(self.test_file, 'w') as f:
            f.write('%c\n')
            f.write('test_command\n')
            f.write('test_user Date: 2023-10-01 12:00:00\n')
            f.write('%p\n')
            f.write('Darkoffset = -100\n')
            f.write('Filedir = "/gpfs/current/raw/TUBAF_CW_241_sweep/Varex_3"\n')
            f.write('Filepattern = "frame_%05u.cbf"\n')
            f.write('Gain = 7\n')
            f.write('%d\n')
            f.write(' Col1 Col2\n')
            f.write(' 1 2\n')
            f.write(' 3 4\n')

    def tearDown(self):
        # Remove the sample fio file after testing
        #os.remove(self.test_file)
        pass

    def test_init(self):
        fio_instance = fio(self.test_file)
        self.assertIsNotNone(fio_instance.parameters)
        self.assertIsNotNone(fio_instance.data)
        self.assertIsNotNone(fio_instance.columns)
        self.assertIsNotNone(fio_instance.command)
        self.assertIsNotNone(fio_instance.fioType)
        self.assertIsNotNone(fio_instance.user)
        self.assertIsNotNone(fio_instance.date)
        self.assertIsNotNone(fio_instance.detectors)

    def test_getComments(self):
        fio_instance = fio(self.test_file)
        self.assertEqual(fio_instance.command, 'test_command')
        self.assertEqual(fio_instance.fioType, 'test_command')
        self.assertEqual(fio_instance.user, 'test_user')
        self.assertEqual(fio_instance.date, dateutil.parser.parse('2023-10-01 12:00:00'))

    def test_getParameters(self):
        fio_instance = fio(self.test_file)
        expected_parameters = {
            'Darkoffset': -100,
            'Filedir': '/gpfs/current/raw/TUBAF_CW_241_sweep/Varex_3',
            'Filepattern': 'frame_%05u.cbf',
            'Gain': 7
        }
        self.assertEqual(fio_instance.parameters, expected_parameters)

    def test_getData(self):
        fio_instance = fio(self.test_file)
        expected_columns = ['Col1', 'Col2']
        expected_data = [[1, 3], [2, 4]]
        self.assertEqual(fio_instance.columns, expected_columns)
        self.assertEqual(fio_instance.data, expected_data)

    def test_export(self):
        fio_instance = fio(self.test_file)
        export_file = 'export.json'
        fio_instance.export(export_file)
        self.assertTrue(os.path.exists(export_file))
        os.remove(export_file)

if __name__ == '__main__':
    unittest.main()
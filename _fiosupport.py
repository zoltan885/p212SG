import dateutil.parser
import json


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
        self.data = None
        self.columns = None
        self.command = None
        self.fioType = None
        self.user = None
        self.date = None
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
        self.data = self._getData(lines=lines, start=d+1, end=e)

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
        self.date = dateutil.parser.parse(' '.join(comment[1].split(' ')[5:]))
    
    
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
            if isinstance(v, str):
                if v.startswith('{') and v.endswith('}'):
                    v = v[1:-1]
                    if ',' in v:
                        self.detectors[k] = {}
                        key_val = v.split(',')
                        for kv in key_val:
                            key = kv.split(':')[0].strip().strip('"')
                            val = kv.split(':')[1].strip().strip('"')
                            self.detectors[k][key] = self._type(val)
        for k in self.detectors.keys():
            pars.pop(k)
        return pars

    def _getData(self, lines: str, start: int, end: int):
        """
        Extracts data and column names from a given range of lines.

        Args:
            lines (str): The input lines from which data and columns are extracted.
            start (int): The starting index of the range of lines to process.
            end (int): The ending index of the range of lines to process.

        Returns:
            np.ndarray: A 2D numpy array containing the extracted data, transposed.
        """
        self.columns = []
        data = []
        for l in lines[start:end]:
            if l.startswith(' Col'):
                self.columns.append(l.split()[2])
            else:
                data.append([self._type(ll) for ll in l.split()])  # Convert to float
        data = list(map(list, zip(*data)))  # Transpose the data
        return data

    def export(self , fn: str):
        """
        Exports the data to a specified json file.

        Args:
            fn (str): The file path to export the data to.
        """
        with open(fn, 'w') as f:
            json.dump(self.__dict__, open(fn, 'w'), default=str, indent=4, sort_keys=True)

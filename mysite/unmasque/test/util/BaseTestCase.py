import signal
import sys
import unittest
from _decimal import Decimal

from mysite.unmasque.test.util.TPCH_backup_restore import TPCHRestore
from ...src.util.ConnectionFactory import ConnectionHelperFactory
from ...src.util.configParser import Config
from ...src.pipeline.abstract.TpchSanitizer import TpchSanitizer
from ...src.util.PostgresConnectionHelper import PostgresConnectionHelper


def signal_handler(signum, frame):
    print('You pressed Ctrl+C!')
    sigconn = PostgresConnectionHelper(Config())
    sigconn.connectUsingParams()
    sanitizer = TpchSanitizer(sigconn)
    sanitizer.sanitize()
    sigconn.closeConnection()
    print("database restored!")
    sys.exit(0)


class BaseTestCase(unittest.TestCase):
    conn = ConnectionHelperFactory().createConnectionHelper()
    sigconn = ConnectionHelperFactory().createConnectionHelper()
    sanitizer = TPCHRestore(sigconn)
    global_attrib_types = []
    global_attrib_types_dict = {}
    global_min_instance_dict = {}

    def get_dmin_val(self, attrib: str, tab: str):
        values = self.global_min_instance_dict[tab]
        attribs, vals = values[0], values[1]
        attrib_idx = attribs.index(attrib)
        val = vals[attrib_idx]
        ret_val = float(val) if isinstance(val, Decimal) else val
        return ret_val

    def do_init(self):
        for entry in self.global_attrib_types:
            # aoa change
            self.global_attrib_types_dict[(entry[0], entry[1])] = entry[2]

    def get_datatype(self, tab_attrib):
        if any(x in self.global_attrib_types_dict[tab_attrib] for x in ['int', 'integer', 'number']):
            return 'int'
        elif 'date' in self.global_attrib_types_dict[tab_attrib]:
            return 'date'
        elif any(x in self.global_attrib_types_dict[tab_attrib] for x in ['text', 'char', 'varbit']):
            return 'str'
        elif any(x in self.global_attrib_types_dict[tab_attrib] for x in ['numeric', 'float']):
            return 'numeric'
        else:
            raise ValueError

    def setUp(self):
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        self.sanitize_db()

    def sanitize_db(self):
        self.sigconn.connectUsingParams()
        self.sanitizer.doJob()
        self.sigconn.closeConnection()

    def tearDown(self):
        self.sanitize_db()


if __name__ == '__main__':
    unittest.main()

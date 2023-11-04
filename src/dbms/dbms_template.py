from abc import ABC, abstractmethod
import json
import os
import re

class DBMSTemplate(ABC):
    """ Base template to be extended to support various dbms (e.g., postgresql, mysql) """
    def __init__(self, db, user, password, restart_cmd, recover_script, knob_info_path):
        
        self.db = db
        self.user = user
        self.password = password
        self.restart_cmd = restart_cmd
        self.config = {}
        self.knob_info = None
        self.connection = None
        self.timeout_s = 120
        self.failed_times = 0
        self.recover_script = recover_script
        self.get_knob_info(knob_info_path)
        self._connect()

    @classmethod   
    def from_file(cls, config):
        db = config['DATABASE']['db']
        db_user = config['DATABASE']['user']
        password = config['DATABASE']['password']
        restart_cmd = config['DATABASE']['restart_cmd']
        recover_script = config['DATABASE']['recover_script']
        knob_info_path = config['DATABASE']['knob_info_path']
        return cls(db, db_user, password, restart_cmd, recover_script, knob_info_path)
    
    def get_knob_info(self, knob_info_path):
        """ Get knob info from json file and store the result in self.knob_info """
        with open(knob_info_path) as json_file:
            knob_info = json.load(json_file)
        self.knob_info = knob_info

    def is_numerical(self, value):
        """ Returns true iff value is number, optionally followed by unit. """
        param_reg = r'[a-z_]+_[a-z]+'
        value_reg = r'(\d+(\.\d+)?)(%|\w*)'
        return True if re.match(value_reg + r'$', str(value)) else False

    def datetime_serializer(self, obj):
        """ Serialize datetime objects into string format """
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        raise TypeError("Type not serializable")
    
    def recover_dbms(self):
        """Recover the dbms if the dbms has a crash"""
        os.system(f"sh {self.recover_script}")
        print("DBMS recovered")

    def restart_dbms(self):
        os.system(self.restart_cmd)

    def create_template(self, test):
        self.copy_db(source_db="benchbase", target_db=f"{test}_template")
        print(f"created {test}_template for {test}")
        return True

    @abstractmethod
    def reconfigure(self):
        """ Makes all parameter changes take effect (may require restart). 
        
        Returns:
            Whether reconfiguration was successful
        """
        pass
    
    @abstractmethod
    def reset_config(self):
        """ Reset all parameters to default values. """
        pass
    
    @abstractmethod    
    def _connect(self):
        """ Establish connection to database, return success flag """
        pass
        
    @abstractmethod
    def _disconnect(self):
        """ Disconnect from database. """
        pass

    @abstractmethod
    def _disconnect(self):
        """ Disconnect from database. """
        pass
    
    
    @abstractmethod
    def get_sql_result(self, sql):
        """ Execute sql query on dbms and return the result and its description """
        pass
    
    @abstractmethod
    def extract_knob_info(self, dest_path):
        """ Extract knob information and store the query result in json format """
        pass
    
    @abstractmethod
    def update_dbms(self, sql):
        """ Execute sql query on dbms to update knob value and return success flag """
        pass
    
    @abstractmethod
    def set_knob(self, knob, knob_value):
        """ Set the knob to knob_value """
        pass
    
    @abstractmethod
    def get_knob_value(self, knob):
        """ Returns current value for given knob """
        pass
    
    @abstractmethod
    def check_knob_exists(self, knob):
        """ check if a knob exists in DBMS """
        pass
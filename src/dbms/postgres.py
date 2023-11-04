from dbms.dbms_template import DBMSTemplate
import psycopg2
import os
import time
import json

class PgDBMS(DBMSTemplate):
    """ Instantiate DBMSTemplate to support PostgreSQL DBMS """
    def __init__(self, db, user, password, restart_cmd, recover_script, knob_info_path):
        super().__init__(db, user, password, restart_cmd, recover_script, knob_info_path)
        self.name = "postgres"
    
    def _connect(self, db=None):
        """ Establish connection to database, return success flag """
        self.failed_times = 0
        if db==None:
            db=self.db
        print(f'Trying to connect to {db} with user {self.user}')
        while True:
            try:            
                self.connection = psycopg2.connect(
                    database = db, user = self.user, 
                    password = self.password, host = "localhost"
                )
                print(f"Success to connect to {db} with user {self.user}")
                self.failed_times = 0
                return True
            except Exception as e:
                self.failed_times += 1
                print(f'Exception while trying to connect: {e}')
                if self.failed_times == 4:
                    self.recover_dbms()
                    return False
                print("Reconnet again")
                time.sleep(3)

            
    def _disconnect(self):
        """ Disconnect from database. """
        if self.connection:
            print('Disconnecting ...')
            self.connection.close()
            print('Disconnecting done ...')
            self.connection = None


    def copy_db(self, target_db, source_db):
        # for tpcc, recover the data for the target db(benchbase)
        self.update_dbms(f'drop database if exists {target_db}')
        self.update_dbms(f'create database {target_db} with template {source_db}')

    
    def reset_config(self):
        """ Reset all parameters to default values. """
        self.update_dbms('alter system reset all;')
        
    def reconfigure(self):
        """ 
            Restart to make parameter settings take effect. Returns true if successful.
            The configuration could make the dbms crash, so that maybe we need recovery operation.
        """
        self._disconnect()
        os.system(self.restart_cmd)
        time.sleep(2)
        success = self._connect()
        if success:
            return success
        else:
            try:
                self.recover_dbms()
                time.sleep(3)
                return True
            except Exception as e:
                print(f'Exception while trying to recover dbms: {e}')
                return False
    
    def get_sql_result(self, sql):
        """ Execute sql query on dbms and return the result and its description """
        self.connection.autocommit = True
        cursor = self.connection.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        description = cursor.description
        cursor.close()
        
        return result, description
    
    def extract_knob_info(self, dest_path):
        """ execute "pg_settings" sql on dbms for knob information and store the query result in json format """
        knob_info = {}
        knobs_sql = "SELECT name FROM pg_settings;"
        knobs, _ = self.get_sql_result(knobs_sql)
        for knob in knobs:
            knob = knob[0]  # Extract the knob name from the result tuple
            knob_details_sql = f"SELECT * FROM pg_settings WHERE name = '{knob}';"
            knob_detail, description = self.get_sql_result(knob_details_sql)
            if knob_detail:
                column_names = [desc[0] for desc in description]
                knob_detail = knob_detail[0]
                knob_attributes = {}
                for i, column_name in enumerate(column_names):
                    knob_attributes[column_name] = knob_detail[i]
                knob_info[knob] = knob_attributes
        with open(dest_path, "w") as json_file:
            json.dump(knob_info, json_file, indent=4, sort_keys=True)
        print(f"The knob info is written to {dest_path}")


    
    def update_dbms(self, sql):
        """ Execute sql query on dbms to update knob value and return success flag """
        try:
            self.connection.autocommit = True
            cursor = self.connection.cursor()
            cursor.execute(sql)
            cursor.close()
            return True
        except Exception as e:
            print(f"Failed to execute {sql} to update dbms for error: {e}")
            return False 

    def set_knob(self, knob, knob_value):
        query_one = f'alter system set {knob} to \'{knob_value}\';'
        success =  self.update_dbms(query_one)
        if success:
            self.config[knob] = knob_value
        return success 
    
    def get_knob_value(self, knob):
        """ Get the current value for a knob """
        result, _ = self.get_sql_result(f"show {knob}")
        return result

        
    def check_knob_exists(self, knob):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM pg_settings WHERE name = %s", (knob,))
        row = cursor.fetchone()
        cursor.close()
        
        return row is not None

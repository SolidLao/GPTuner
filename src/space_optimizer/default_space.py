from abc import abstractmethod
from config_recommender.workload_runner import BenchbaseRunner
import time
import sys
import os
import json
import threading
import glob
import re
from ConfigSpace import (
    ConfigurationSpace,
    UniformIntegerHyperparameter,
    UniformFloatHyperparameter,
    CategoricalHyperparameter,
)

class DefaultSpace:
    """ Base template of GPTuner"""
    def __init__(self, dbms, test, timeout, target_knobs_path, seed=1):
        self.dbms = dbms
        self.seed = seed if seed is not None else 1
        self.test = test
        self.timeout = timeout
        self.target_knobs_path = target_knobs_path
        self.round = 0
        self.summary_path = "./optimization_results/temp_results"
        self.benchmark_copy_db = ['tpcc', 'twitter', "sibench", "voter", "tatp", "smallbank", "seats"]   # Some benchmark will insert or delete data, Need to be rewrite each time.
        self.benchmark_latency = ['tpch']
        self.search_space = ConfigurationSpace()
        self.skill_path = f"./knowledge_collection/{self.dbms.name}/structured_knowledge/normal"
        self.target_knobs = self.knob_select()
        if self.test in self.benchmark_copy_db:
            self.dbms.create_template(self.test)
        self.penalty = self.get_default_result()


    def _transfer_unit(self, value):
        value = str(value)
        value = value.replace(" ", "")
        value = value.replace(",", "")
        if value.isalpha():
            value = "1" + value
        pattern = r'(\d+\.\d+|\d+)([a-zA-Z]+)'
        match = re.match(pattern, value)
        if not match:
            return float(value)
        number, unit = match.group(1), match.group(2)
        unit_to_size = {
            'kB': 1e3,
            'KB': 1e3,
            'MB': 1e6,
            'GB': 1e9,
            'TB': 1e12,
            'K': 1e3,
            'M': 1e6,
            'G': 1e9,
            'B': 1,
            'ms': 1,
            's': 1000,
            'min': 60000,
            'day': 24 * 60 * 60000,
        }
        return float(number) * unit_to_size[unit]
    
    def _type_transfer(self, knob_type, value):
        value = str(value)
        value = value.replace(",", "")
        if knob_type == "integer":
            return int(round(float(value)))
        if knob_type == "real":
            return float(value)

    def knob_select(self):
        """ 
            Select which knobs to be tuned, store the names in 'self.target_knobs' 
            Read knobs from 'knowledge_collection/{dbms}/target_knobs.txt'. Provide the path to the file containing the knobs' names.
        """
        with open(self.target_knobs_path, 'r') as file:
            lines = file.readlines()
        candidate_knobs = [line.strip() for line in lines]
        target_knobs = []
        for knob in candidate_knobs:
            if "vartype" not in self.dbms.knob_info[knob] or self.dbms.knob_info[knob]["vartype"] == "string":
                continue
            else:
                target_knobs.append(knob)
        return target_knobs
    
    def get_default_space(self, knob_name, info):
        boot_value = info["reset_val"]
        min_value = info["min_val"]
        max_value = info["max_val"]
        knob_type = info["vartype"]
        if knob_type == "integer":
            if int(max_value) > sys.maxsize:
                knob = UniformIntegerHyperparameter(
                    knob_name, 
                    int(int(min_value) / 1000), 
                    int(int(max_value) / 1000),
                    default_value = int(int(boot_value) / 1000)
                )
            else:
                knob = UniformIntegerHyperparameter(
                    knob_name,
                    int(min_value),
                    int(max_value),
                    default_value = int(boot_value),
                )
        elif knob_type == "real":
            knob = UniformFloatHyperparameter(
                knob_name,
                float(min_value),
                float(max_value),
                default_value = float(boot_value)
            )
        elif knob_type == "enum":
            knob = CategoricalHyperparameter(
                knob_name,
                [str(enum_val) for enum_val in info["enumvals"]],
                default_value = str(boot_value),
            )
        elif knob_type == "bool":
            knob = CategoricalHyperparameter(
                knob_name,
                ["on", "off"],
                default_value = str(boot_value)
            )
        return knob
    
    def get_latest_summary_file(self):
        files = glob.glob(os.path.join(self.summary_path, '*summary.json'))
        files.sort(key=os.path.getmtime, reverse=True)  
        return files[0] if files else None
    
    def clear_summary_dir(self):
        for filename in os.listdir(self.summary_path):
            print(f"REMOVE {filename}")
            filepath = os.path.join(self.summary_path, filename)
            os.remove(filepath)

    def get_throughput(self):
        summary_file = self.get_latest_summary_file()
        try:
            with open(summary_file, 'r') as file:
                data = json.load(file)
            throughput = data["Throughput (requests/second)"]
            if throughput==-1 or throughput == 2147483647:
                raise ValueError(f"Benchbase return error throughput:{throughput}")
            print(f"Throughput: {throughput}")
        except Exception as e:
            print(f'Exception for JSON: {e}')
            throughput = self.penalty - 2
        return throughput

    def get_latency(self):
        summary_file = self.get_latest_summary_file()
        try:
            with open(summary_file, 'r') as file:
                data = json.load(file)
            average_latency = data["Latency Distribution"]["Average Latency (microseconds)"]
            if average_latency == -1 or average_latency == 2147483647:
                raise ValueError(f"Benchbase return error average_latency:{average_latency}")
            print(f"Latency: {average_latency}")
        except Exception as e:
            print(f'Exception for JSON: {e}')
            average_latency = self.penalty - 2
        return average_latency

    def get_default_result(self):
        print("Test the result in default conf")
        dbms = self.dbms
        self.clear_summary_dir()
        print(f"--- Restore the dbms to default configuration ---")
        dbms.reset_config()
        dbms.reconfigure()

        try:
            if self.test in self.benchmark_copy_db:
            # reload the data
                print("Reloading the data")
                dbms.copy_db(target_db="benchbase", source_db=f"{self.test}_template")
                print("Reloading completed")
                time.sleep(12)
                dbms._disconnect()
                time.sleep(4)
                dbms._connect('benchbase')
                time.sleep(3)
                pass
                
            print("Begin to run benchbase...")
            runner = BenchbaseRunner(dbms=dbms, test=self.test)
            t = threading.Thread(target=runner.run_benchmark)
            t.start()
            t.join()
            throughput, average_latency = self.get_throughput(), self.get_latency()
        except Exception as e:
            print(f'Exception for {self.test}: {e}')

        if self.test not in self.benchmark_latency:
            return throughput
        else:
            return average_latency

    def set_and_replay(self, config, seed=0):
        self.round += 1
        print(f"Tuning round {self.round} ...")
        dbms = self.dbms
        self.clear_summary_dir()
        print(f"--- Restore the dbms to default configuration ---")
        dbms.reset_config()
        dbms.reconfigure()
        print(f"--- knob setting procedure ---")
        for knob in self.target_knobs:
            try:
                control_para = config[f"control_{knob}"]
                if control_para == "0":
                    value = config[knob]       
                elif control_para == "1":
                    value = config[f"special_{knob}"]
            except:
                value = config[knob]
            dbms.set_knob(knob, value)
            
        dbms.reconfigure()
        if self.test not in self.benchmark_latency:
            if dbms.failed_times == 4:
                return -int(self.penalty) / 2
        else:
            if dbms.failed_times == 4:
                return self.penalty * 2
            
        try:
            if self.test in self.benchmark_copy_db:
            # reload the data
                print("Reloading the data")
                dbms.copy_db(target_db="benchbase", source_db=f"{self.test}_template")
                print("Reloading completed")
                time.sleep(12)
                dbms._disconnect()
                time.sleep(4)
                dbms._connect('benchbase')
                time.sleep(3)
                pass
                
            print("Begin to run benchbase...")
            runner = BenchbaseRunner(dbms=dbms, test=self.test)
            t = threading.Thread(target=runner.run_benchmark)
            t.start()
            t.join(timeout=self.timeout)
            if t.is_alive():
                print("Benchmark is still running. Terminate it now.")
                runner.process.terminate()
                time.sleep(2)
                throughput = self.penalty - 2
                average_latency =  self.penalty - 2
            else:
                print("Benchmark has finished.")
                throughput, average_latency = self.get_throughput(), self.get_latency()
        except Exception as e:
            print(f'Exception for {self.test}: {e}')
            # update worst_perf
            if self.test not in self.benchmark_latency:
                if throughput < self.penalty:
                    self.penalty = throughput
                return -int(self.penalty) / 2
                ###tpch
            else:
                if average_latency > self.penalty:
                    self.penalty = average_latency
                    return self.penalty * 2
    

        if self.test not in self.benchmark_latency:
            return -throughput
        else:
            return average_latency


    @abstractmethod
    def define_search_space(self):
        pass
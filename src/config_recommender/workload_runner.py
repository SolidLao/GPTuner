import subprocess
import os
import glob
import json
from dbms.mysql import MysqlDBMS
from dbms.postgres import PgDBMS

class BenchbaseRunner:
    def __init__(self, dbms, test, target_path="./optimization_results/temp_results"):
        """target_path is the relative path under the GPTuner folder"""
        self.process = None
        self.test = test
        self.dbms = dbms
        self.target_path = target_path

        if isinstance(self.dbms, PgDBMS):  
            self.benchmark_path = "./benchbase/target/benchbase-postgres"
        else:
            self.benchmark_path = "./benchbase/target/benchbase-mysql"

    def run_benchmark(self):
        if isinstance(self.dbms, PgDBMS):
            self.process = subprocess.Popen(
                ['java', '-jar', 'benchbase.jar', '-b', self.test, 
                "-c", "config/postgres/sample_{}_config.xml".format(self.test), 
                "--create=false", "--clear=false", "--load=false", '--execute=true', 
                "-d", os.path.join("../../../", self.target_path)],
                cwd=self.benchmark_path
            )
        elif isinstance(self.dbms, MysqlDBMS):
            self.process = subprocess.Popen(
                ['java', '-jar', 'benchbase.jar', '-b', self.test, 
                "-c", "config/mysql/sample_{}_config.xml".format(self.test), 
                "--create=false", "--clear=false", "--load=false", '--execute=true', 
                "-d", os.path.join("../../../", self.target_path)],
                cwd=self.benchmark_path
            )
        self.process.wait()

    def clear_summary_dir(self):
        for filename in os.listdir(self.target_path):
            print(f"REMOVE {filename}")
            filepath = os.path.join(self.target_path, filename)
            os.remove(filepath)

    def get_latest_summary_file(self):
        files = glob.glob(os.path.join(self.target_path, '*summary.json'))
        files.sort(key=os.path.getmtime, reverse=True)  
        return files[0] if files else None

    def get_latest_raw_file(self):
        files = glob.glob(os.path.join(self.target_path, '*raw.csv'))
        files.sort(key=os.path.getmtime, reverse=True)  
        return files[0] if files else None

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
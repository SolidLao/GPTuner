from dbms.mysql import MysqlDBMS
from dbms.postgres import PgDBMS
import subprocess


class BenchbaseRunner:
    def __init__(self, dbms, test):
        self.process = None
        self.test = test
        self.dbms = dbms
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
                "-d", "../../../optimization_results/temp_results"],
                cwd=self.benchmark_path
            )
        elif isinstance(self.dbms, MysqlDBMS):
            self.process = subprocess.Popen(
                ['java', '-jar', 'benchbase.jar', '-b', self.test, 
                "-c", "config/mysql/sample_{}_config.xml".format(self.test), 
                "--create=false", "--clear=false", "--load=false", '--execute=true', 
                "-d", "../../../optimization_results/temp_results"],
                cwd=self.benchmark_path
            )
        self.process.wait()
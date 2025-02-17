import os
import textwrap
import json
import pandas as pd
from configparser import ConfigParser
import threading
from knowledge_handler.gpt import GPT
from config_recommender.workload_runner import BenchbaseRunner

class KnobSelection(GPT):
    def __init__(self, api_base, api_key, db, dbms, benchmark, model=GPT.__init__.__defaults__[0]):
        super().__init__(api_base, api_key, model=model)
        self.db = db
        self.dbms = dbms
        self.benchmark = benchmark
        self.config = ConfigParser()
        if self.benchmark == 'tpch':
            self.workload = "OLAP"
        else:
            self.workload = "OLTP"
        self.system_view_dir = f"./knowledge_collection/{self.db}/candidate_knobs.txt"
        self.target_knobs_dir = f"./knowledge_collection/{self.db}/target_knobs.txt"
        if os.path.exists(self.target_knobs_dir):
            print(f"Knobs already selected for {self.db}")
        else:
            self.candidate_knobs = self.get_candidate_konbs()
        
    def get_candidate_konbs(self):
        knobs = []
        with open(self.system_view_dir, 'r') as file:
            data = json.load(file)
            for key, item in data.items():
                knobs.append(key)
        return knobs

    def read_files_in_directory(directory_path):
            files_and_directories = os.listdir(directory_path)
            all_files = [f for f in files_and_directories if os.path.isfile(os.path.join(directory_path, f))]
            return all_files

    def select_on_system_level(self):
        print("select_on_system_level")
        selected_knobs = {}
        for i in range(0, len(self.candidate_knobs), 30):
            candidates = self.candidate_knobs[i:i + 30]
            prompt = textwrap.dedent(f"""
                You are an experienced DBA and your will determine which knobs are worth tuning. You only tune knobs that have a significant impact on DBMS performance and the target DBMS is {self.db}. Given the following candidate knobs, score the importance for each knob between 0 and 1, with a higher value indicating that it is more likey to impact {self.db} performance significantly. 
                Candidate knobs: {candidates}
                DBMS: {self.db};
                Now let us think step by step and give me your scoring of all the candidate knobs in json format:
                {{
                    "knob_name": {{score}}    // fill "score" with a number between 0 and 1
                }}
                If no knobs are suggested, just fill "knob_list" with "None" and also return result in json format. 
                """)
            
            json_result = self.get_GPT_response_json(prompt, json_format=True)
            print(json_result)
            selected_knobs.update(json_result)

        print(selected_knobs)
        return selected_knobs

    def select_on_workload_level(self):
        print("select_on_workload_level")
        selected_knobs = {}
        for i in range(0, len(self.candidate_knobs), 30):
            candidates = self.candidate_knobs[i:i + 30]
            prompt = textwrap.dedent(f"""
                You are an experienced DBA and your will determine which knobs are worth tuning. You only tune knobs that have a significant impact on DBMS performance and the target DBMS is {self.db}. Which knobs are important heavily depends on the workload type because different workloads result in different performance bottleneck.Given the workload type, analyze and identify the important knobs that significantly impact database performance when such workload is deployed.  Given the following candidate knobs, score the importance for each knob between 0 and 1, with a higher value indicating that it is more likey to impact {self.db} performance significantly. 
                Candidate knobs: {candidates}
                DBMS: {self.db};
                WORKLOAD TYPE:{self.workload}
                Now let us think step by step and give me your scoring of all the candidate knobs in json format:
                {{
                    "knob_name": {{score}}    // fill "score" with a number between 0 and 1
                }}
                If no knobs are suggested, just fill "knob_list" with "None" and also return result in json format. 
                """)
                
            json_result = self.get_GPT_response_json(prompt, json_format=True)
            print(json_result)
            selected_knobs.update(json_result)
        print(selected_knobs)
        return selected_knobs

    def get_top_tpch_query(self, raw_file, n=5):
        df = pd.read_csv(raw_file)
        sorted_df = df.sort_values(by='Latency (microseconds)', ascending=False)
        top_sqls = sorted_df['Transaction Name'].head(n)
        query_list = []
        for sql in top_sqls:
            with open(os.path.join("./sql/tpch", f"{sql}.sql")) as file:
                sql = file.read()
                for query in sql.split(';'):
                    if query != "":
                        query_list.append(query)

        return query_list

    def select_on_query_level(self):
        print("select_on_query_level")

        if self.benchmark == 'tpch':
            target_path = "./optimization_results/temp_results"
            print(f"--- Restore the dbms to default configuration ---")
            self.dbms.reset_config()
            self.dbms.reconfigure()
            runner = BenchbaseRunner(dbms=self.dbms, test=self.benchmark, target_path=target_path)
            runner.clear_summary_dir()
            t = threading.Thread(target=runner.run_benchmark)
            t.start()
            t.join()
            raw_file = runner.get_latest_raw_file()
            query_list = self.get_top_tpch_query(raw_file, n=2)

        else:
            return {}

        selected_knobs = {}
        for i, query in enumerate(query_list):
            query_plan, __ = self.dbms.get_sql_result(f"EXPLAIN {query}")
            print(f"### PLAIN: {query_plan}")
            for j in range(0, len(self.candidate_knobs), 30):
                candidates = self.candidate_knobs[i:i + 30]
                prompt = textwrap.dedent(f"""
                    You are an experienced DBA and your will determine which knobs are worth tuning. You only tune knobs that have a significant impact on DBMS performance and the target DBMS is {self.db}. Which knobs are important heavily depends on the query plan because different query plans result in different performance bottlenecks.Given SQL and its QUERY PLAN from 'EXPLAIN', analyze and suggest which knobs should be tuned to improve the performance of this SQL.  Given the following candidate knobs, score the importance for each knob between 0 and 1, with a higher value indicating that it is more likey to impact {self.db} performance significantly. 
                    Candidate knobs: {candidates}
                    DBMS: {self.db};
                    SQL:{query}
                    QUERY PLAN:{query_plan}
                    Now let us think step by step and give me your scoring of all the candidate knobs in json format:
                    {{
                        "knob_name": {{score}}    // fill "score" with a number between 0 and 1
                    }}
                    If no knobs are suggested, just fill "knob_list" with "None" and also return result in json format. 
                    """)
                    
                json_result = self.get_GPT_response_json(prompt, json_format=True)
                print(json_result)
                selected_knobs.update(json_result)
        print(selected_knobs)
        return selected_knobs

    def select_interdependent_all_knobs(self):
        if os.path.exists(self.target_knobs_dir):
            print(f"Knobs already selected for {self.db}")
            return None

        system_knobs = self.select_on_system_level()
        workload_knobs = self.select_on_workload_level()
        query_knobs = self.select_on_query_level()

        all_keys = set(system_knobs).union(workload_knobs, query_knobs)
        selected_knobs = {key: system_knobs.get(key, 0) + workload_knobs.get(key, 0) + query_knobs.get(key, 0) for key in all_keys}

        top_50_items = sorted(selected_knobs.items(), key=lambda item: item[1], reverse=True)[:50]
        selected_knobs = [key for key, value in top_50_items]
        print(top_50_items)
        prompt = textwrap.dedent(f"""
        I am solving database configuration tuning problem. 
        There exist dependencies between knobs, which are mentioned in manuals and act as your training data.   
        For example, the official PostgreSQL document suggests “Larger settings for 'shared_buffers' usually require a corresponding increase in 'checkpoint_segments',
        indicating that we should consider the two knobs at the same time.
        TASK:
        Now there is a collection of knobs that need to be adjusted, but we may have overlooked 
        knobs that are related to these knobs (i.e., knobs that need to be adjusted at the same time, according to past knowledge). 
        Please add the knobs that are interdependent with these knobs in the set according to your knowledge. 
        NOTE:
        If the given DBMS is 'postgres', the interdependent knobs should be supported by PostgreSQL;
        If the given DBMS is 'mysql', the interdependent knobs should be supported by Mysql;
        KNOB COLLECTION:{selected_knobs}
        DBMS:{self.db}
        Now let us think step by step and give me result in json format, 
        {{
           "think_procedure": {{procedure}}    // fill "procedure" with your "think step by step procedure"
           "knob_list": {{knob_list}}          // fill "knob_list" with a list of the name of interdependent knobs
        }}
        If no knobs are interdependent, just fill "knob_list" with "None". 
        """
        )
        
        json_result = self.get_GPT_response_json(prompt, json_format=True)
        if json_result.get("knob_list") != 'None':
            selected_knobs = list(selected_knobs) + json_result["knob_list"]
        else:
            selected_knobs = list(selected_knobs)
        selected_knobs = list(set(selected_knobs))
        with open(self.target_knobs_dir, 'w') as file:
            for line in selected_knobs:
                file.write(line + "\n")
                
        return selected_knobs
        
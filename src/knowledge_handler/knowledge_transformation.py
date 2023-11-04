import openai
import re
import psutil
import textwrap
import json
import os
import random
import tiktoken
from collections import Counter
import time

class KGTrans:
    def __init__(self, api_base, api_key, db="postgres", model="gpt-4"):
        self.db = db
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.knob_path = f"./knowledge_collection/{self.db}"
        self.knob_num = 0
        self.money = 0
        self.token = 0
        self.total_time = 0
        self.cur_token = 0
        self.cur_money = 0
        self.cur_time = time.time()
        self.__connect()
        self._define_path()
        
    def __connect(self):
        openai.api_base = self.api_base
        openai.api_key = self.api_key

    def _define_path(self):
        self.knob_info_path = os.path.join(self.knob_path, "knob_info/system_view.json")
        self.summary_path = os.path.join(self.knob_path, "tuning_lake")
        self.skill_json_path = os.path.join(self.knob_path, "structured_knowledge/normal/")    
        self.max_path = os.path.join(self.knob_path, "structured_knowledge/max/")
        self.official_path = os.path.join(self.knob_path, "/knob_info/official_document.json")
        self.special_path = os.path.join(self.knob_path, "structured_knowledge/special/")
    
    def get_answer(self, prompt):
        response = openai.ChatCompletion.create(
            model=self.model,
            messages = [{
            "role": "user",
            "content": prompt
            }],
            n=1,
            stop=None,
            temperature=0
        )
        return response.choices[0].message["content"].strip()
    
    def calc_token(self, in_text, out_text=""):
        enc = tiktoken.encoding_for_model("gpt-4")
        return len(enc.encode(out_text+in_text))

    def calc_money(self, in_text, out_text):
        """money for gpt4"""
        return (self.calc_token(in_text) * 0.03 + self.calc_token(out_text) * 0.06) / 1000

    def remove_html_tags(self, text):
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
    
    def extract_json_from_text(self, text):
        json_pattern = r'\{[^{}]*\}'
        match = re.search(json_pattern, text)
        if match:
            try:
                json_data = json.loads(match.group())
                return json_data
            except json.JSONDecodeError:
                return None
        else:
            return None

    def get_hardware_info(self):
        available_cpu_cores = psutil.cpu_count(logical=False)
        memory = psutil.virtual_memory()
        total_memory = memory.total
        total_memory = total_memory / (1024 * 1024 * 1024)
        root_disk = psutil.disk_usage('/')
        total_disk_space = root_disk.total
        total_disk_space = total_disk_space / (1024 * 1024 * 1024)
        return available_cpu_cores, int(total_memory), int(total_disk_space)

    def get_disk_type(self, device="sda"):
        rotational_path = f'/sys/block/{device}/queue/rotational'
        if os.path.exists(rotational_path):
            with open(rotational_path, 'r') as file:
                rotational_value = file.read().strip()
                if rotational_value == '0':
                    return 'SSD'
                elif rotational_value == '1':
                    return 'HDD'
                else:
                    return 'Unknown'
        else:
            return 'Unknown'

    def get_examples(self):
        example_path = f"./example_pool/"
        file_list = os.listdir(example_path)
        # 使用random.sample()函数从文件列表中随机选择三个文件
        random_examples_name = random.sample(file_list, 3)
        random_examples = []
        for i in range(3):
            with open(os.path.join(example_path, random_examples_name[i]), "r") as file:
                example = f"<example>\n{file.read()}\n<\example>"
                random_examples.append(example)
        return '\n'.join(random_examples)

    def get_skill(self, knob):
        cpu_cores, ram_size, disk_size = self.get_hardware_info()
        disk_type = self.get_disk_type()
        try:
            with open(os.path.join(self.summary_path, knob+".txt"), 'r') as file:
                summary = file.read()
        except:
            print(f"The tuning pool of {knob} is empty, generate the tuning pool first.")
            raise 
        
        prompt = textwrap.dedent(f"""
            Suppose you are an experienced DBA, and you are required to tune a knob of {self.db}.

            TASK DESCRIPTION:
            Given the knob name along with its suggestion and hardware information, your job is to offer three values that may lead to the best performance of the system and meet the hardware resource constraints. The three values you need to provide are 'suggested_values', 'min_values', and 'max_values'. If you can identify one or more exact discrete suggested values, treat them as 'suggested_values'. If the suggested values fall within a continuous interval, provide the 'min_value' and 'max_value' for that interval.

            Note that the result you provide should be derived or inferred from the information provided. The result values should be numerical, and if a unit is needed, you can only choose from [KB, MB, GB, ms, s, min]; other units are not permitted.

            The question you need to solve will be given in the HTML tag <question>, the suggested steps to follow to finish the job are in <step>, and some examples will be given in the <example> tag.

            <step>
            Step 1: Check if the suggestion provides values for the knob; if so, identify the relevant sentences and move to Step 2. If not, move to Step 2. Note that there may be several sentences you should try to find them all.
            Step 2: Check if the suggestion recommends some values related to hardware information. If so, proceed to Step 3; if not, proceed to Step 4.
            Step 3: Read the hardware information to figure out the hardware-relevent value(s); some easy computation may be required.
            Step 4: Check whether the suggestion offers a specific recommended value or a recommended range for good performance or both of them. Note that sometimes the default value or the permitted value range of the knob is given, but these are not the recommended values for optimal DBMS performance, so ignore these values.
            Step 5: If discrete suggested values are given, list them under 'suggested_values'.
            Step 6: If a suggested range is given, set the upper and lower bounds of the range as the 'max_value' and 'min_value', respectively.
            Step 7: Return the result in JSON format.
            </step>

            <EXAMPLES>

            {self.get_examples()}

            </EXAMPLES>

            <question>
            KNOB: {knob}
            SUGGESTION: {summary}
            HARDWARE INFORMATION: The machine running the dbms has a RAM of {ram_size} GB, a CPU of {cpu_cores} cores, and a {disk_size} GB {disk_type} drive.
            JSON RESULT TEMPLATE:
            {{
                "suggested_values": [], // these should be exact values with a unit if needed (allowable units: KB, MB, GB, ms, s, min)
                "min_value": null,      // change it if there is a hint about the minimum value in SUGGESTIONS
                "max_value": null       // change it if there is a hint about the maximum value in SUGGESTIONS, it should be larger than min_value
            }}
            </question>

            Let us think step by step and finally provide me with the result in JSON format. If no related information is provided in suggestions, just keep the result values at their default.

                """)

        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return answer

    def vote(self, knob):
        skill_json_files = os.listdir(self.skill_json_path)
        if knob + ".txt" not in skill_json_files:
            min_l = []
            max_l = []
            suggested_l = []

            for i in range(5):
                print(f"vote for {knob}, round {i}")
                result_txt = self.get_skill(knob)
                result_json = self.extract_json_from_text(result_txt)
                suggested_values = result_json["suggested_values"]
                min_value = result_json["min_value"]
                max_value = result_json["max_value"]
                min_l.append(min_value)
                max_l.append(max_value)
                suggested_l = suggested_l + suggested_values
            skill_json = {}
            min_counts = Counter(min_l)
            max_counts = Counter(max_l)
            suggested_counts = Counter(suggested_l)
            sorted_min = sorted(min_counts.items(), key=lambda x: x[1], reverse=True)
            sorted_max = sorted(max_counts.items(), key=lambda x: x[1], reverse=True)
            sorted_suggested = sorted(suggested_counts.items(), key=lambda x: x[1], reverse=True)
            print(f"Vote result for {knob}:")
            print(sorted_min, sorted_max, sorted_suggested)
            if len(sorted_min)!=0:
                most_common_min, _ = sorted_min[0]
                skill_json["min_value"] = most_common_min
            else:
                skill_json["min_value"] = None
            if len(sorted_max)!=0:
                most_common_max, _ = sorted_max[0]
                skill_json["max_value"] = most_common_max
            else:
                skill_json["min_value"] = None
            if len(sorted_suggested) != 0:
                most_common_suggested_count = sorted_suggested[0][1]
                most_common_suggested = [item[0] for item in sorted_suggested if item[1] == most_common_suggested_count]
                skill_json["suggested_values"] = most_common_suggested
            else:
                skill_json["suggested_values"] = []
            
            with open(os.path.join(self.skill_json_path, knob+".json"), 'w') as file:
                json.dump(skill_json, file)
    
    def classify_special_knob(self, knob_name):
        if os.path.exists(self.official_path):
            with open(self.official_path, 'r') as json_file:
                data = json.load(json_file)
            knob_list = data["params"]
            description = None
            for knob in knob_list:
                if knob["name"] == knob_name:
                    description = self.remove_html_tags(knob["description"])
            if description is None:
                return None
            prompt = textwrap.dedent(f"""
                Database Management Systems (DBMS) have settings referred to as 'knobs'. Numerical knobs typically have a natural order. However, some 'special' numerical knobs have special values, such as -1 or 0, that break this natural order. When set to a special value, such knob performs a very different function compared to its regular operation, such as disabling a feature. Otherwise, it behaves like a regular numerical knob. Let us think step by step, please classify a knob as a 'special knob' based on its DESCRIPTION and provide the RESULT in JSON format. 
                KNOB: 
                {knob_name}
                DESCRIPTION: 
                {description}
                RESULT: 
                {{
                    "think_procedure": {{procedure}}    // fill 'procedure' with your 'think step by step procedure'
                    "special_knob”: {{bool}},           // fill 'bool' with 'true' or 'false' 
                    "special_value: {{value}}           // fill 'value' with its special value if it is a special knob
                }}
            """)
        else:
            prompt = textwrap.dedent(f"""
            Database Management Systems (DBMS) have settings referred to as 'knobs'. Numerical knobs typically have a natural order. However, some 'special' numerical knobs have special values, such as -1 or 0, that break this natural order. When set to a special value, such knob performs a very different function compared to its regular operation, such as disabling a feature. Otherwise, it behaves like a regular numerical knob. Let us think step by step, please classify a knob of {self.db}as a 'special knob' and provide the RESULT in JSON format. 
            KNOB: 
            {knob_name}

            RESULT: 
            {{
                "think_procedure": {{procedure}}    // fill 'procedure' with your 'think step by step procedure'
                "special_knob”: {{bool}},           // fill 'bool' with 'true' or 'false' 
                "special_value: {{value}}           // fill 'value' with its special value if it is a special knob
            }}
        """)

        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        print(f"prepare special skill for {knob_name}")
        return answer

    def prepare_special_skill(self, knob):
        file_name = f"{knob}.json"
        if file_name not in os.listdir(self.special_path):
            result = self.classify_special_knob(knob)
            if result is not None:
                json_result = self.extract_json_from_text(result)
                with open(f"{self.special_path}{file_name}", 'w') as file:
                    json.dump(json_result, file)

    def mysql_provide_max(self, knob):
        if os.path.exists(os.path.join(self.max_path, knob+".txt")):
            return None

        cpu_cores, ram_size, disk_size = self.get_hardware_info()
        disk_type = self.get_disk_type()

        with open(self.knob_info_path, 'r') as file:
            knob_info = json.load(file)[knob]
            upper_bound = knob_info.get("max_val")
            
        prompt = textwrap.dedent(f"""
            Database Management Systems (DBMS) have settings referred to as 'knobs'. There is always a legitimate range for a numerical knob. But for some knobs, the upper bound is too large, so that it is impossible to set such a large value in practice. Given a knob of mysql, your job is to judge whether the upper bound of this knob is too large, if so, offer your suggested upper bound according to your experience and the hardware information I provide. Your suggested upper bound cannot be larger than the upper bound of the knob and cannot be larger than '9,223,372,036,854,775,807'. If the knob is not numerical, return null. 
              
            KNOB: 
            {knob}
            UPPER_BOUND:
            {upper_bound}
            HARDWARE INFORMATION: The machine running the dbms has a RAM of {ram_size} GB, a CPU of {cpu_cores} cores, and a {disk_size} GB {disk_type} drive.

            Now think step by step and give me the suggested upper bound. The answer should either be a number or null. Just return the answer, do not provide other information.
        """)
        
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        with open(os.path.join(self.max_path, knob+".txt"), 'w') as file:
            file.write(answer)
        return answer

    def pipeline(self, knob):
        print(f"begin to prepare structured knowledge for {knob}")
        self.cur_time = time.time()
        skill_json_files = os.listdir(self.skill_json_path)
        if knob + ".json" not in skill_json_files:
            self.vote(knob)

        # Special
        self.prepare_special_skill(knob)
        # Since the upper bound of some knob in mysql is too big, ask gpt to propose an upper bound.
        if self.db == "mysql":
            self.mysql_provide_max(knob)
        self.cur_time = time.time() - self.cur_time
        self.total_time = self.total_time + self.cur_time
        self.knob_num += 1
        print(f"Finished to prepare structured knowledge for {knob}")
        print(f"total token:{self.token}, total money:{self.money}, total time: {self.total_time}, knob num: {self.knob_num}")
        print(f"ave token: {self.token/self.knob_num}, ave money:{self.money/self.knob_num}, ave time:{self.total_time/self.knob_num},")
        
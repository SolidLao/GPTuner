import openai
import re
import psutil
import textwrap
import json
import os
import tiktoken
import time

class KGPre:
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
        self.knob_info_path = f"./knowledge_collection/{self.db}/knob_info/system_view.json"
        self.gpt_path = f"./knowledge_collection/{self.db}/knowledge_sources/gpt"
        self.web_path = f"./knowledge_collection/{self.db}/knowledge_sources/web"
        self.manual_path = f"./knowledge_collection/{self.db}/knowledge_sources/manual"
        self.summary_path = f"./knowledge_collection/{self.db}/tuning_lake"
        self.official_path = f"./knowledge_collection/{self.db}/knob_info/official_document.json"

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

    def get_suggestions_from_gpt(self, knob_name):
        suggestions_prompt = textwrap.dedent(f"""
            There are many useful manuals to guide the knob tuning process. For knob '{knob_name}' in {self.db}, summerize the way to set the value for it in a sentence. This sentence should be associated with concrete numbers as more detailed information if needed.
        """)
        suggestions = self.get_answer(suggestions_prompt)
        self.token += self.calc_token(suggestions_prompt, suggestions)
        self.money += self.calc_money(suggestions_prompt, suggestions)
        return suggestions
    
    def get_suggestions_from_manual(self, knob_name):
        if  not os.path.exists(f"./knowledge_collection/{self.db}/knob_info/official_document.json"):
            return None

        with open(self.official_path, 'r') as json_file:
            data = json.load(json_file)
        knob_list = data["params"]
        description = None
        for knob in knob_list:
            if knob["name"] == knob_name:
                description =  self.remove_html_tags(knob["description"])
        if description:
            summerize_prompt = textwrap.dedent(f"""
                Summerize the description for knob '{knob_name}' in a sentence. This sentence should be associated with concrete numbers as more detailed information if needed.
                DESCRIPTION:
                {description}
                SENTECNCE:
            """)
            answer = self.get_answer(summerize_prompt)
            self.token += self.calc_token(summerize_prompt, answer)
            self.money += self.calc_money(summerize_prompt, answer)
            return answer
        else:
            return None
    
    def prepare_knowledge(self, knob_name):
        knowledge_path = os.path.join(self.knob_path, "knowledge_sources")
        file_name = f"{knob_name}.txt"
    
        if file_name not in os.listdir(os.path.join(knowledge_path, "gpt")):
            print(f"Preparing knowledge from gpt for knob: {knob_name}")
            gpt_suggestions = self.get_suggestions_from_gpt(knob_name)
            with open(os.path.join(knowledge_path, "gpt", file_name), "w") as file:
                file.write(gpt_suggestions)
        if file_name not in os.listdir(os.path.join(knowledge_path, "manual")):
            print(f"Preparing knowledge from manual for knob: {knob_name}")
            manual_suggestions = self.get_suggestions_from_manual(knob_name)
            if manual_suggestions:
                with open(os.path.join(knowledge_path, "gpt", file_name), "w") as file:
                    file.write(manual_suggestions)

    def prune_suggestion(self, official_doc, gpt_suggestion, web_suggestion):
        prompt = textwrap.dedent(f"""
           I first give you information of a knob of {self.db} which is extracted from the official document in json format, this offers the constraints of the value of each knob. Then I offer you two suggestions for this knob from GPT and WEB, judge whether each suggestion satisfies the constraints of the offcial document. If there is a contradiction between certain suggestion and the official document, remove the contradictory part. If there is not a contradiction, return the original suggestion.  

            Step 1: Read the OFFICIAL_DOC especially the "max_val", "min_val" and "unit". Figure out the actual min_value and max_value. Note that sometimes "min_val and "max_val" are not the actual min_value and max_value, they need to be computed considering "unit" which is the actual unit of the "max_val", "min_val", "reset_val".
            Step 2: Figure out if the suggestions contain any numerical value that is illegal according to the OFFICIAL_DOC, unit conversion may be required in the process. If so, remove the illegal values and the relevant information, rewrite the corresponding suggestion. 
            Step 3: Return your answer in json format.

            OFFICIAL_DOC:
            {official_doc}
            GPT_SUGGESTION:
            {gpt_suggestion}
            WEB_SUGGESTION:
            {web_suggestion}

            Now think step by step, and give me the result in json format.:
            {{
                "gpt_suggestion": null ,   // if there is a contradiction, remove the contradictory part, else return the corresponding original suggestion.
                "web_suggestion": null   // if there is a contradiction, remove the contradictory part, else return the corresponding original suggestion.
            }}
    """    
    )
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return self.extract_json_from_text(answer)

    def prune_contradiction(self, suggestions_json):
        prompt = textwrap.dedent(f"""
        I will give you three suggestions for tuning a knob of {self.db}. Your job is to find contradictions between the given suggestions. If there is contradictory information between certain suggestions, especially the contradictions of values, keep the information provided by the higher-priority suggestion and only remove the contradictory information provided by the lower-priority suggestion. Do not remove the other information. The priority is defined in sequence as "manual_suggestion, web_suggestion, gpt_suggestion" from higher to lower. So manual_suggestion should not be changed. If there is contradiction within the same suggestion, keep it.  Try to make your summary encapsulates information from the three suggestions as much as possible except from the contradictory parts.    
        THREE SUGGESTIONS:
        {suggestions_json}

        Now let's think step by step, and give me the result in legal json format.:
            {{
                "gpt_suggestion": null,  // if the original provided suggestion is empty, return null, else return the corresponding answer.
                "web_suggestion": null,  // if the original provided suggestion is empty, return null, else return the corresponding answer.
                "manual_suggestion": null // if the original provided suggestion is empty, return null, else return the origional manual_suggestion.
            }}
        """    
        )
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return self.extract_json_from_text(answer)

    def prune_default(self, official_doc, suggestions_json):
        prompt = textwrap.dedent(f"""
            I offer you three suggestions for tuning a knob of {self.db} derived from GPT, web and manual. Your job is to identify whether each suggestion contains information which state the legal range of the knob witch is the same as the OFFICIAL_DOC and remove it. If you find this kind of information, rewrite the suggestion so that it does not include this information about "min_val" and "max_val" in the OFFICIAL_DOC, but it should contain all the other information included in the corresponding original information especially some suggested values or ranges. You need to read the OFFICIAL_DOC to figure out if the suggestion includes these values which exists in the official document implicitly, unit conversion may be considered in this process. 
            I need you to return the three suggestions in the same json format.      

            Step 1: Read the OFFICIAL_DOC especially the "max_val", "min_val" and "unit". Figure out the actual min_value, max_value. Note that sometimes "min_val and "max_val" are not the actual min_value and max_value, they need to be computed considering "unit" which is the actual unit of the "max_val", "min_val".
            Step 2: Figure out if the suggestions contain any numerical value that is the same as one of your computed min_value and max_value in Step 2. If so, remove them.
            Step 3: Rewrite the suggestion so that it does not include any information about "min_val" and "max_val", but it should contain all the other information included in the corresponding original information especially some suggested values or ranges.
            Step 4: Return your three suggestions in the same json format.

            OFFICIAL_DOC:
            {official_doc}
            THREE SUGGESTIONS:
            {suggestions_json}

            Now let's think step by step and give me the result in legal json format:
                {{
                    "gpt_suggestion": null ,   // if the original suggestion is empty, return null, else return the corresponding answer.
                    "web_suggestion": null,  // if the original suggestion is empty, return null, else return the corresponding answer.
                    "manual_suggestion": null  // if the original suggestion is empty, return null, else return the corresponding answer.
                }}
            """    
            )
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return self.extract_json_from_text(answer)

    def greedy_summarize(self, suggestions_json):
        prompt = textwrap.dedent(f"""
        Summarize the three suggestions provided in the JSON format below into a single comprehensive suggestion. Try to make your summary encapsulates information from the three suggestions as much as possible. If there is contradictory information between certain suggestions, keep the information provided by the higher-priority suggestion and remove the information provided by the lower-priority suggestion. The priority is defined in sequence as "manual_suggestion, web_suggestion, gpt_suggestion" from higher to lower.  Your response should also be structured as a suggestion. Now let's think step by step and give me the answer.
        THREE SUGGESTIONS:
        {suggestions_json}
        """    
        )
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return answer
    
    def check_summary(self, summary, suggestions_json):
        prompt = textwrap.dedent(f"""
        Decide if the following summary is consistent with corresponding suggestions which are provided in json format. Note that consistency means all information in the summary is supported by the suggestions. There should not be any contradiction in the summary, especially the contradictions of values. Your answer should either be "No" or "Yes".
        Suggestions:{suggestions_json}
        Summary:{summary}
        """    
        )
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return answer

    def revise_summarize(self, suggestions_json, summary):
        prompt = textwrap.dedent(f"""
        Given three suggestions provided in the JSON format below, you should summarize them into a single comprehensive suggestion. I will also provide you a improper summary suggestion which may be inconsistent with the three suggestions.You should identify the problem in the improper summary and resummarize the three suggestions into a single comprehensive suggestion which encapsulates all the information from the three suggestions. If there is conflicting information between certain suggestions, keep the information provided by the higher-priority suggestion and ignore the information provided by the lower-priority suggestion. The priority is defined in sequence as "manual_suggestion, web_suggestion, gpt_suggestion" from higher to lower. Your response should also be structured as a suggestion. Now let's think step by step and give me the answer.
        Note that you should just give me your summarized suggestion only. Do not provide me other information.
            THREE SUGGESTIONS: {suggestions_json}
            IMPROPER SUMMARY SUGGESTION: {summary}
        """    
        )
        answer = self.get_answer(prompt)
        self.token += self.calc_token(prompt, answer)
        self.money += self.calc_money(prompt, answer)
        return answer

    def pipeline(self, knob):
        print(f"begin to prepare the tuning pool for {knob}")
        self.cur_time = time.time()

        with open(self.knob_info_path) as json_file:
            knob_info = json.load(json_file)

        summary_files = os.listdir(self.summary_path)

        self.prepare_knowledge(knob)
        gpt_suggestion, web_suggestion, manual_suggestion = None, None, None
        try:
            with open(os.path.join(self.gpt_path, knob+".txt"), 'r') as file:
                gpt_suggestion = file.read()
        except:
            pass

        try:
            with open(os.path.join(self.web_path, knob+".txt"), 'r') as file:
                web_suggestion = file.readline()
        except:
            pass

        try:
            with open(os.path.join(self.manual_path, knob+".txt"), 'r') as file:
                manual_suggestion = file.readline()
        except:
            manual_suggestion 
            pass

        if knob + ".txt" not in summary_files:
            sources_json = self.prune_suggestion(knob_info[knob], gpt_suggestion, web_suggestion)
            sources_json["manual_suggestion"] = manual_suggestion
            sources_json = self.prune_contradiction(sources_json)
            sources_json = self.prune_default(knob_info[knob], sources_json)
            sources_json = sources_json
            summary = self.greedy_summarize(sources_json)
            print(f"SUMMARY:{summary}")
            check = self.check_summary(summary, sources_json)
            i = 1  # 防止死循环
            while check=="No":
                summary = self.revise_summarize(sources_json, summary)
                check = self.check_summary(summary, sources_json)
                print(f"RESUMMARY:{summary}")
                i += 1
                if i >= 3:
                    break
            with open(os.path.join(self.summary_path, knob+".txt"), 'w') as file:
                file.write(summary)

        self.cur_time = time.time() - self.cur_time
        self.total_time = self.total_time + self.cur_time
        self.knob_num += 1
        print(f"Finished to prepare knowledge source for {knob}")
        print(f"accumulated token:{self.token}, accumulated money:{self.money}, accumulated time: {self.total_time}, accumulated knob num: {self.knob_num}")
        print(f"ave token: {self.token/self.knob_num}, ave money:{self.money/self.knob_num}, ave time:{self.total_time/self.knob_num},")
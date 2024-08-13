import time
from knowledge_handler.utils import get_hardware_info, get_disk_type
from knowledge_handler.gpt import GPT

class KGUpdate(GPT):
    def __init__(self, api_base, api_key, db="postgres", model=GPT.__init__.__defaults__[0]):
        super().__init__(api_base, api_key, model=model)
        self.db = db
        self.knob_path = f"./knowledge_collection/{self.db}"
        self.knob_num = 0
        self.total_time = 0
        self.cur_time = time.time()
        self._define_path()

    def _define_path(self):
        # Method to set up necessary paths for files
        self.knob_info_path = f"./knowledge_collection/{self.db}/knob_info/system_view.json"
        self.gpt_path = f"./knowledge_collection/{self.db}/knowledge_sources/gpt"
        self.web_path = f"./knowledge_collection/{self.db}/knowledge_sources/web"
        self.manual_path = f"./knowledge_collection/{self.db}/knowledge_sources/manual"
        self.summary_path = f"./knowledge_collection/{self.db}/tuning_lake"
        self.official_path = f"./knowledge_collection/{self.db}/knob_info/official_document.json"
        self.update_path = f"./knowledge_collection/{self.db}/knob_info/knob_update.json"

    def pipeline(self, knob):
        print(f"begin {knob}")
        self.cur_time = time.time()
        # Implement the full pipeline as per the diagram
        resource_knobs = self.filter_knobs(knob)
        related_knowledge = self.filter_knowledge(resource_knobs)
        new_structure = self.update_knowledge(related_knowledge, knob)
        print(new_structure)

    # offline
    def filter_knobs(self, knob):

        # knob -> cpu, ram, disk_size, disk_type ?
        # LLM: True of False

        prompt = f"Filter knobs related to {knob}"
        response = self.get_GPT_response_json(prompt)
        with open(self.update_path, 'w') as f:
        json.dump(response, f, indent=4)

        self.token += self.calc_token(prompt, response)
        self.money += self.calc_money(prompt, response)
        return response

    # offline
    def filter_knowledge(self, knob):
  
        # given knob name, extract domain knowledge from tuning lake
        # self.summary_path -> knobname.txt

        # knowledge -> cpu, ram, disk_size, disk_type ?
        # LLM: cpu || ram || disk_size || disk_type

        prompt = "Further filter knowledge based on resource knobs"
        response = self.get_GPT_response_json(prompt)
        self.token += self.calc_token(prompt, response)
        self.money += self.calc_money(prompt, response)
        return response

    def read_knobs_from_json(type):
        # from knob
        NotImplementedError()

    # online
    def update_knowledge(self, knob, knowledge, old_hardware):        

        # get hardware information
        old_cpu, old_ram, old_disk_size, old_disk_type = old_hardware

        new_cpu, new_ram, new_disk_size = get_hardware_info()
        new_disk_type = get_disk_type()

        if old_cpu != new_cpu:
            # process cpu_related knobs
            # cpu_knobs = read_knobs_from_json(type="cpu")
            NotImplementedError()
        
        if old_ram != new_ram:
            NotImplementedError()

        if old_disk_size != new_disk_size:
            NotImplementedError()

        if old_disk_type != new_disk_type:
            NotImplementedError()

        prompt = "Generate new structured knowledge based on input knowledge"
        response = self.get_GPT_response_json(prompt)
        self.token += self.calc_token(prompt, response)
        self.money += self.calc_money(prompt, response)
        return response
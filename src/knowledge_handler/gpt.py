import openai
import re
import json
import tiktoken

class GPT:
    def __init__(self, api_base, api_key, model="gpt-4"):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.money = 0
        self.token = 0
        self.cur_token = 0
        self.cur_money = 0
        self.__connect()
        
    def __connect(self):
        openai.api_base = self.api_base
        openai.api_key = self.api_key

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
        enc = tiktoken.encoding_for_model(self.model)
        return len(enc.encode(out_text+in_text))

    def calc_money(self, in_text, out_text):
        """money for gpt4"""
        if self.model == "gpt-4":
            return (self.calc_token(in_text) * 0.03 + self.calc_token(out_text) * 0.06) / 1000
        elif self.model == "gpt-3.5-turbo":
            return (self.calc_token(in_text) * 0.0015 + self.calc_token(out_text) * 0.002) / 1000

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


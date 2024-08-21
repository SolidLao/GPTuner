from openai import OpenAI, APIError
import re
import json
import tiktoken

class GPT:
    def __init__(self, api_base, api_key, model="gpt-4o-mini"):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.money = 0
        self.token = 0
        self.cur_token = 0
        self.cur_money = 0

    def get_GPT_response_json(self, prompt, json_format=True): # This function returns the GPT response, which can be specified to return json or string format
        client = OpenAI(api_key=self.api_key, base_url = self.api_base)
        if json_format: # json
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You should output JSON."},
                    {'role':'user', 'content':prompt}],
                model=self.model, 
                response_format={"type": "json_object"}, 
                temperature=0.5,
            )
            # print(response)
            ans = response.choices[0].message.content
            completion = json.loads(ans)  # Convert to json object
            
        else: # string
            response = client.chat.completions.create(
                messages=[
                    {'role':'user', 'content':prompt}],
                model=self.model, 
                temperature=1,     
            )
            completion = response.choices[0].message.content
        return completion
    
    def calc_token(self, in_text, out_text=""):
        if isinstance(out_text, dict):
            out_text = json.dumps(out_text)
        enc = tiktoken.encoding_for_model(self.model)
        return len(enc.encode(out_text+in_text))

    def calc_money(self, in_text, out_text):
        """money for gpt4"""
        if self.model == "gpt-4":
            return (self.calc_token(in_text) * 0.03 + self.calc_token(out_text) * 0.06) / 1000
        elif self.model == "gpt-3.5-turbo":
            return (self.calc_token(in_text) * 0.0015 + self.calc_token(out_text) * 0.002) / 1000
        elif self.model == "gpt-4-1106-preview" or self.model == "gpt-4-1106-vision-preview":
            return (self.calc_token(in_text) * 0.01 + self.calc_token(out_text) * 0.03) / 1000
        else:
            return 0 

    def remove_html_tags(self, text):
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
    

from openai import OpenAI, APIError
import openai 
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

    def get_GPT_response_json(self, prompt, json_format=True): # 这函数的作用是返回GPT的回答，可以指定返回json格式或字符串格式
        client = OpenAI(api_key=self.api_key, base_url = self.api_base)
        if json_format: # 指定返回json
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You should output JSON."},
                    {'role':'user', 'content':prompt}],
                model=self.model, # 指定要使用的模型
                response_format={"type": "json_object"}, # 这里指定GPT要返回json
                temperature=0.5,
            )
            # print(response)
            ans = response.choices[0].message.content
            completion = json.loads(ans)  # 转化为json对象
            
        else: # 返回字符串
            response = client.chat.completions.create(
                messages=[
                    {'role':'user', 'content':prompt}],
                model=self.model, # 指定要使用的模型
                temperature=1,     
            )
            completion = response.choices[0].message.content
        return completion
    
    def calc_token(self, in_text, out_text=""):
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

    def remove_html_tags(self, text):
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text)
    
    # def extract_json_from_text(self, text):
    #     json_pattern = r'\{[^{}]*\}'
    #     match = re.search(json_pattern, text)
    #     if match:
    #         try:
    #             json_data = json.loads(match.group())
    #             return json_data
    #         except json.JSONDecodeError:
    #             return None
    #     else:
    #         return None


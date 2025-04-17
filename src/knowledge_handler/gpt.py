from openai import OpenAI, APIError
import re
import json
import tiktoken
import os


from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, ChainedTokenCredential, AzureCliCredential, get_bearer_token_provider

scope = "api://trapi/.default"
credential = get_bearer_token_provider(ChainedTokenCredential(
    AzureCliCredential(),
    DefaultAzureCredential(
        exclude_cli_credential=True,
        # Exclude other credentials we are not interested in.
        exclude_environment_credential=True,
        exclude_shared_token_cache_credential=True,
        exclude_developer_cli_credential=True,
        exclude_powershell_credential=True,
        exclude_interactive_browser_credential=True,
        exclude_visual_studio_code_credentials=True,
        # DEFAULT_IDENTITY_CLIENT_ID is a variable exposed in
        # Azure ML Compute jobs that has the client id of the
        # user-assigned managed identity in it.
        # See https://learn.microsoft.com/en-us/azure/machine-learning/how-to-identity-based-service-authentication#compute-cluster
        # In case it is not set the ManagedIdentityCredential will
        # default to using the system-assigned managed identity, if any.
        managed_identity_client_id=os.environ.get("DEFAULT_IDENTITY_CLIENT_ID"),
    )
),scope)

api_version = '2024-10-21' # Ensure this is a valid API version see: https://learn.microsoft.com/en-us/azure/ai-services/openai/api-version-deprecation#latest-ga-api-release
model_name = 'gpt-4o-mini' # Ensure this is a valid model name
model_version = '2024-07-18' # Ensure this is a valid model version
deployment_name = re.sub(r'[^a-zA-Z0-9-_]', '', f'{model_name}_{model_version}') # If your Endpoint doesn't have harmonized deployment names, you can use the deployment name directly: see: https://aka.ms/trapi/models
instance = 'gcr/shared' # See https://aka.ms/trapi/models for the instance name, remove /openai (library adds it implicitly) 
endpoint = f'https://trapi.research.microsoft.com/{instance}'


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
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=credential,
            api_version=api_version,
        )

        print("[GPT][TO]:", prompt, "[END]")
        
        if json_format: # json
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You should output JSON."},
                    {'role':'user', 'content':prompt}],
                model=deployment_name, 
                response_format={"type": "json_object"}, 
                temperature=0.5,
            )
            print("[GPT][FROM]:", response, "[END]")
            ans = response.choices[0].message.content
            completion = json.loads(ans)  # Convert to json object
            
        else: # string
            response = client.chat.completions.create(
                messages=[
                    {'role':'user', 'content':prompt}],
                model=deployment_name, 
                temperature=1,     
            )
            print("[GPT][FROM]:", response, "[END]")
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
    

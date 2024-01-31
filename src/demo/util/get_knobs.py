import json
import streamlit as st
import pandas as pd
import textwrap
import time
from knowledge_handler.knowledge_preparation import KGPre
from demo.util.knowledge_transformation import KGTrans
from knowledge_handler.gpt import GPT

@st.cache_data 
def get_knobs(db):
    if db == 'Postgres 14.9':
        system_view_path = "./knowledge_collection/postgres/knob_info/system_view.json"
    elif db == 'MySQL 8.0':
        system_view_path = "./knowledge_collection/mysql/knob_info/system_view.json"
    else:
        raise ValueError("Illegal DBMS")
    with open(system_view_path, "r") as file:
        system_view = json.load(file)
        knobs = []
        for key, value in system_view.items():
            knobs.append(key)
        knobs.sort()
        return knobs

@st.cache_data 
def get_target_knobs(db):
    if db == 'Postgres 14.9':
        knobs_path = "./knowledge_collection/postgres/target_knobs.txt"
    elif db == 'MySQL 8.0':
        knobs_path = "./knowledge_collection/mysql/target_knobs.txt"
    else:
        raise ValueError("Illegal DBMS")
    try:
        with open(knobs_path, "r") as file:
            temp = file.readlines()
            knobs = [knob.strip() for knob in temp]
            return knobs
    except:
        return []

@st.cache_data 
def get_suggestions(db):
    suggestions = dict()
    if db == 'Postgres 14.9':
        path = "./src/demo/suggestion_postgres.json"
    elif db == 'MySQL 8.0':
        path = "./src/demo/suggestion_mysql.json"
    else:
        raise ValueError("Illegal DBMS")
    with open(path, "r") as file:
        suggestions = json.load(file)
    for knob, value in suggestions.items():
        value["add"] = None
        suggestions[knob] = value
    return suggestions

@st.cache_data 
def get_structured_knowledge(db):
    structured_knowledge = dict()
    suggested_values = dict()
    if db == 'Postgres 14.9':
        path = "./src/demo/structured_knowlegde_postgres.json"
    elif db == 'MySQL 8.0':
        path = "./src/demo/structured_knowlegde_mysql.json"
    else:
        raise ValueError("Illegal DBMS")
    with open(path, "r") as file:
        suggestions = json.load(file)
    for key, value in suggestions.items():
        ans = pd.DataFrame([[value["min_value"], value["max_value"], value["special_knob"], value["special_value"]]], columns=["min_value", "max_value", "special_knob", "special_value"])
        structured_knowledge[key] = ans
        suggested_values[key] = value["suggested_values"]

    return structured_knowledge, suggested_values


def re_summary(gpt_suggestion, manual_suggestion, web_suggestion, add_suggestion,
                u_gpt, u_manual, u_web, u_add, model, api_key, api_base):

    print("Regenerating Summary")
    suggestions_json = dict()
    kgpre = KGPre(api_base, api_key)
    if u_gpt:
        suggestions_json["gpt_suggestion"] = gpt_suggestion
    if u_manual:
        suggestions_json["manual_suggestion"] = manual_suggestion
    if u_web:
        suggestions_json["web_suggestion"] = web_suggestion

    suggestions_json = kgpre.prune_contradiction(suggestions_json)

    if u_add:
        suggestions_json["additional_suggestion"] = add_suggestion

    return kgpre.greedy_summarize(suggestions_json)


def re_structured(knob, summary, model, api_base, api_key, hardware_info):
    if summary is None:
        raise ValueError("No Summary")
    
    kgtrans = KGTrans(api_base, api_key, hardware_info=hardware_info, model=model)
    skill_json = kgtrans.vote(knob, summary)
    special_json = None
    while special_json is None:
        special_json = kgtrans.extract_json_from_text(kgtrans.classify_special_knob(knob))

    return [skill_json["min_value"], skill_json["max_value"], special_json["special_knob"], special_json["special_value"]], skill_json["suggested_values"] 
    


@st.cache_data 
def get_system_view(path):
    keys = ["reset_val", "vartype", "short_desc", "enumvals", "min_val", "max_val", "unit"]
    with open(path, 'r') as file:
        data = json.load(file)
    system_view = dict()
    for knob, value in data.items():
        temp = dict()
        for key, v in value.items():
            if key in keys:
                if not isinstance(v, str):
                    v = str(v)
                temp[key] = [v]
        system_view_df = pd.DataFrame(temp)
        system_view[knob] = system_view_df
    return system_view

def get_txt_height(txt):
    if txt is None:
        return 100
    return int(len(txt)/2.6)


def gpt_filter_noisy_knowledge(official_doc, gpt_suggestion, web_suggestion, add_suggestion, api_base, api_key, model):
    gpt = GPT(api_base, api_key, model)
    ans_json = None
    while ans_json is None:
        prompt = textwrap.dedent(f"""
            I first give you information of a knob which is extracted from the official document, this offers the constraints of the value of each knob. Then I offer you three tuning suggestions for this knob , judge whether each suggestion satisfies the constraints of the offcial document. If there is a contradiction between the suggestion and the official document, return true. If there is not a contradiction, return false.  

            Step 1: Read the OFFICIAL_DOC especially the "max_val", "min_val", "reset_val" and "unit". Figure out the actual min_value, max_value and default value. Note that sometimes "min_val, "max_val" and "reset_val" are not the actual min_value, max_value and reset value, they need to be computed considering "unit" which is the actual unit of the "max_val", "min_val", "reset_val".
            Step 2: Figure out if the suggestions contain any numerical value that is illegal according to the OFFICIAL_DOC, unit conversion may be required in the process. If so, return null. If not, return the original suggestion.
            Step 3: Return your answer in json format.

            OFFICIAL_DOC:
            {official_doc}
            suggestion_1:
            {gpt_suggestion}
            suggestion_2:
            {web_suggestion}
            suggestion_3:
            {add_suggestion}

            Now think step by step, and give me the result in json format.:
            {{
                "suggestion_1": false,   // if there is a contradiction, return true, else return false.
                "suggestion_2": false,  // if there is a contradiction, return true, else return false.
                "suggestion_3": false.  // if there is a contradiction, return true, else return false.
                ""explaination":        // you should give the reason for your answer.
            }}
        """)
        answer = gpt.get_answer(prompt)
        ans_json = gpt.extract_json_from_text(answer)
        print(ans_json)
        if ans_json is None:
            continue
        for suggestion in ["suggestion_1", "suggestion_2", "suggestion_3"]:
            if suggestion not in ans_json:
                ans_json = None
                break
               
    ans = {"gpt_suggestion":ans_json["suggestion_1"], "web_suggestion":ans_json["suggestion_2"], "additional_suggestion":ans_json["suggestion_3"]}
    return ans


@st.cache_data 
def check_summary(summary, suggestions_json, api_base, api_key, model):
    kgpre = KGPre(api_base, api_key, model=model)
    ans = kgpre.check_summary(summary, suggestions_json)
    if "No" in ans:
        return False
    else:
        return True

      
      
@st.cache_data   
def revise_summarize(suggestions_json, summary, api_base, api_key, model):
    kgpre = KGPre(api_base, api_key, model=model)
    return kgpre.revise_summarize(suggestions_json, summary)
    
import json
import os
import sys
import time
import shutil
import re
import pandas as pd
from dbms.mysql import MysqlDBMS
def get_default_space(knob_name, info):
        boot_value = info["reset_val"][0]
        min_value = info["min_val"][0]
        max_value = info["max_val"][0]
        knob_type = info["vartype"][0]
        knob = {}
        if knob_type == "integer":
            if int(max_value) > sys.maxsize:
                knob["lower"] = int(int(min_value) / 1000)
                knob["upper"] = int(int(max_value) / 1000)
                knob["default"] = int(int(boot_value) / 1000)
            else:
                knob["lower"] = int(min_value)
                knob["upper"] = int(max_value)
                knob["default"] = int(boot_value)
                
        elif knob_type == "real":
            knob["lower"] = float(min_value)
            knob["upper"] = float(max_value)
            knob["default"] = float(boot_value)
            
        elif knob_type == "enum":
            knob["choices"] = [str(enum_val) for enum_val in info["enumvals"]]
            knob["default"] = boot_value
            
        elif knob_type == "bool":
            knob["choices"] = ["on", "off"]
            knob["default"] = boot_value
        else:
            knob["choices"] = None
            knob["default"] = boot_value
        
        return knob
    
def _type_transfer(knob_type, value):
    value = str(value)
    value = value.replace(",", "")
    if knob_type == "integer":
        return int(round(float(value)))
    if knob_type == "real":
        return float(value)
    
def get_knowledge_dict(structured_knowledge, suggested_values):
        kg_dict = {key: df.iloc[0].to_dict() for key, df in structured_knowledge.items()}
        for key, value in kg_dict.items():
            kg_dict[key]["suggested_values"] = suggested_values[key] 
        return kg_dict

def _transfer_unit(value):
        value = str(value)
        value = value.replace(" ", "")
        value = value.replace(",", "")
        if value.isalpha():
            value = "1" + value
        pattern = r'(\d+\.\d+|\d+)([a-zA-Z]+)'
        match = re.match(pattern, value)
        if not match:
            return float(value)
        number, unit = match.group(1), match.group(2)
        unit_to_size = {
            'kB': 1e3,
            'KB': 1e3,
            'MB': 1e6,
            'GB': 1e9,
            'TB': 1e12,
            'K': 1e3,
            'M': 1e6,
            'G': 1e9,
            'B': 1,
            'ms': 1,
            's': 1000,
            'min': 60000,
            'day': 24 * 60 * 60000,
        }
        return float(number) * unit_to_size[unit]
        
def define_search_space(knob_, structured_knowledge, suggested_values, dbms, system_view, coarse_fine): # 如果coarse_fine为1，表示coarse,否则fine  
        knob_coarse_value = {}
        datas = get_knowledge_dict(structured_knowledge, suggested_values)
        factors = [0, 0.25, 0.5]
        info = system_view[knob_]
        knob_type = info["vartype"][0]

        if knob_type == "enum" or knob_type == "bool" or knob_type == "string":
            choices = get_default_space(knob_, info)["choices"]
            special_value = [datas[knob_]["special_value"]]
            return {"choices":choices, "special":special_value}

        elif knob_ in datas:
            data = datas[knob_]
            print(f"Defining coarse search space for knob: {knob_}")
            suggested_values = data["suggested_values"]
            boot_value = info["reset_val"][0]
            unit = info["unit"][0]
            # hardware constraint if exists
            min_from_sys, max_from_sys = False, False
            min_value = data["min_value"]
            if min_value is None:
                min_value = info["min_val"][0]
                min_from_sys = True
            
            max_value = data["max_value"]
            if max_value is None:
                max_value = info["max_val"][0]
                max_from_sys = True

            if not min_from_sys:
                if unit:
                    unit = _transfer_unit(unit)
                    min_value = _transfer_unit(min_value) / unit

                    min_value = _type_transfer(knob_type, min_value)
                    sys_min_value = _type_transfer(knob_type, info["min_val"][0])

                    if min_value < sys_min_value:
                        min_value = sys_min_value

            if not max_from_sys:
                if unit:
                    unit = _transfer_unit(unit)
                    max_value = _transfer_unit(max_value) / unit
                    max_value = _type_transfer(knob_type, max_value)
                    sys_max_value = _type_transfer(knob_type, info["max_val"][0])
                    if max_value > sys_max_value:
                        max_value = sys_max_value
            # Since the upper bound of some knob in mysql is too big, use GPT's offered upperbound for mysql
            if isinstance(dbms, MysqlDBMS):
                if max_from_sys or max_value >= sys.maxsize / 10:  #   for mysql
                    max_path = "./knowledge_collection/mysql/structured_knowledge/max"
                    with open(os.path.join(max_path, knob_+".txt"), 'r') as file:
                        upperbound = file.read()
                    if upperbound != 'null':
                        upperbound = _type_transfer(knob_type, upperbound)
                        max_value = _type_transfer(knob_type, max_value)
                        if int(upperbound) < max_value:
                            max_value = upperbound

            # unit transformation
            if unit is not None:
                unit = _transfer_unit(unit)
                suggested_values = [(_transfer_unit(value) / unit) for value in suggested_values]
            
            # type transformation
            try:
                suggested_values = [_type_transfer(knob_type, value) for value in suggested_values]
                min_value = _type_transfer(knob_type, min_value)
                max_value = _type_transfer(knob_type, max_value)
                boot_value = _type_transfer(knob_type, boot_value)
            except:
                def match_num(value):
                    pattern = r"(\d+)"
                    match = re.match(pattern, value)
                    if match:
                        return match.group(1)
                    else:
                        return ""

                pattern = r"(\d+)"
                suggested_values = [_type_transfer(knob_type, re.match(pattern, value).group(1)) for value in suggested_values if re.match(pattern, value) is not None]
                min_value = _type_transfer(knob_type, match_num(min_value))
                max_value = _type_transfer(knob_type, match_num(max_value))
                boot_value = _type_transfer(knob_type, match_num(boot_value))
                
            if boot_value > sys.maxsize / 10:
                boot_value = sys.maxsize / 10
            
                
            sequence = []
            min_value = min(min_value, boot_value)
            max_value = max(max_value, boot_value) 
            for value in suggested_values:
                for factor in factors:
                    explore_up = value + factor * (max_value - value) # scale up the suggested value
                    explore_down = value + factor * (min_value - value) # scale down the suggested value
                    if explore_up < sys.maxsize / 10 and explore_down < explore_up:
                        sequence.append(explore_up)
                        sequence.append(explore_down)
                
            # if a suggested value is not given but a min_val or masx_val is suggested in skill library, equidistant sample.
            if sequence == [] and (not min_from_sys or not max_from_sys):
                for factor in [0.25, 0.5, 0.75]:
                    sequence.append(boot_value + factor * (max_value - boot_value)) 
                if not min_from_sys: 
                    sequence.append(min_value)
                if not max_from_sys:
                    sequence.append(max_value)
            sequence.append(boot_value)
            
            if coarse_fine==0:
                if max_value > sys.maxsize / 10:
                    max_value = sys.maxsize / 10
                if min_value > sys.maxsize / 10:
                    min_value = sys.maxsize / 10
                    
                sequence = [value for value in sequence if value < sys.maxsize / 10]

            # check if this knob is special knob
            special_skill = datas[knob_]
            special = special_skill["special_knob"]
            if special is True:
                special_value = str(special_skill["special_value"])
            # control---
            control_value = {}
            control_value["choice"] = ["0", "1"]
            control_value["default"] = "0"
            
            if knob_type == "integer" or knob_type == "real":
                if coarse_fine:
                    sequence = [float(value) for value in sequence]
                    sequence = list(set(sequence))
                    sequence.sort()
                    if special and special_value is not None and not special_value.isspace() and special_value!="":
                        special_knob_value = {}
                        special_knob_value[f"special"] = [float(_transfer_unit(special_value) / unit)]
                        special_knob_value[f"choices"] = [float(value) for value in sequence]                       
                        
                    else:
                        special_knob_value = {}
                        special_knob_value[f"special"] = [None]
                        special_knob_value[f"choices"] = [float(value) for value in sequence]  
                    return special_knob_value
                else:
                    sequence = [int(value) for value in sequence]
                    min_value = min(min_value, min(sequence))
                    max_value = max(max_value, max(sequence))
                    normal_value = {}
                    normal_value["lower"] = float(min_value)
                    normal_value["upper"] = float(max_value)
                    if special and special_value is not None and not special_value.isspace() and special_value!="":
                        normal_value[f"special"] = [float(_transfer_unit(special_value) / unit)]        
                        
                    else:
                        normal_value[f"special"] = [None]
                    return normal_value
        
        return knob_coarse_value        


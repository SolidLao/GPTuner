from abc import ABC, abstractmethod
from demo.util.default_space import DefaultSpace
from dbms.mysql import MysqlDBMS
from dbms.postgres import PgDBMS
import sys
import os
import json
import re
from smac import HyperparameterOptimizationFacade, Scenario, initial_design, intensifier
from ConfigSpace import (
    UniformIntegerHyperparameter,
    UniformFloatHyperparameter,
    CategoricalHyperparameter,
    Constant,
    Configuration,
    EqualsCondition,
)

class FineSpace_get(DefaultSpace):
    def __init__(self, knob,dbms, test, timeout, structured_knowledge, suggested_values, target_knobs):
        super().__init__(dbms, test, timeout, structured_knowledge, suggested_values, target_knobs)
        self.factors = [0, 0.25, 0.5]
        self.knob_fine_value = {}
        self.knob_ = knob
        self.coarse_path = f"./optimization_results/{self.dbms.name}/coarse/{self.seed}/runhistory.json"
        self.define_search_space()
        
        
    def define_search_space(self):
        
        info = self.dbms.knob_info[self.knob_]
        knob_type = info["vartype"] 
        if info is None:
            self.target_knobs.remove(self.knob_) # this knob is not by the DBMS under specific version
            

        elif knob_type == "enum" or knob_type == "bool" or knob_type == "string":
            knob_dic = self.get_default_space(self.knob_, info)
            self.knob_fine_value[str(self.knob_)]=knob_dic.choices
            # self.search_space.add_hyperparameter(knob)
        
        elif self.knob_ in self.datas:
            data = self.datas[self.knob_]
            
            print(f"Defining fine search space for knob: {self.knob_}")
            suggested_values = data["suggested_values"]
            boot_value = info["reset_val"]
            unit = info["unit"]

            # hardware constraint if exists
            min_from_sys, max_from_sys = False, False
            min_value = data["min_value"]
            if min_value is None:
                min_value = info["min_val"]
                min_from_sys = True
            
            max_value = data["max_value"]
            if max_value is None:
                max_value = info["max_val"]
                max_from_sys = True

            if not min_from_sys:
                if unit:
                    unit = self._transfer_unit(unit)
                    min_value = self._transfer_unit(min_value) / unit

                    min_value = self._type_transfer(knob_type, min_value)
                    sys_min_value = self._type_transfer(knob_type, info["min_val"])

                    if min_value < sys_min_value:
                        min_value = sys_min_value

            if not max_from_sys:
                if unit:
                    unit = self._transfer_unit(unit)
                    max_value = self._transfer_unit(max_value) / unit

                    max_value = self._type_transfer(knob_type, max_value)
                    sys_max_value = self._type_transfer(knob_type, info["max_val"])
                    if max_value > sys_max_value:
                        max_value = sys_max_value
            # Since the upper bound of some knob in mysql is too big, use GPT's offered upperbound for mysql
            if isinstance(self.dbms, MysqlDBMS):
                if max_from_sys or max_value >= sys.maxsize / 10:  
                    max_path = "./knowledge_collection/mysql/structured_knowledge/max"
                    with open(os.path.join(max_path, self.knob_+".txt"), 'r') as file:
                        upperbound = file.read()
                    if upperbound != 'null':
                        upperbound = self._type_transfer(knob_type, upperbound)
                        max_value = self._type_transfer(knob_type, max_value)
                        if int(upperbound) < max_value:
                            max_value = upperbound

            # unit transformation
            if unit is not None:
                unit = self._transfer_unit(unit)
                suggested_values = [(self._transfer_unit(value) / unit) for value in suggested_values]
            
            # type transformation
            try:
                suggested_values = [self._type_transfer(knob_type, value) for value in suggested_values]
                min_value = self._type_transfer(knob_type, min_value)
                max_value = self._type_transfer(knob_type, max_value)
                boot_value = self._type_transfer(knob_type, boot_value)
            except:

                def match_num(value):
                    pattern = r"(\d+)"
                    match = re.match(pattern, value)
                    if match:
                        return match.group(1)
                    else:
                        return ""

                pattern = r"(\d+)"
                suggested_values = [self._type_transfer(knob_type, re.match(pattern, value).group(1)) for value in suggested_values if re.match(pattern, value) is not None]
                min_value = self._type_transfer(knob_type, match_num(min_value))
                max_value = self._type_transfer(knob_type, match_num(max_value))
                boot_value = self._type_transfer(knob_type, match_num(boot_value))
                
            if boot_value > sys.maxsize / 10:
                boot_value = sys.maxsize / 10

            # the search space of fine-grained stage should be superset of that of coarse stage
            coarse_sequence = []
            min_value = min(min_value, boot_value)
            max_value = max(max_value, boot_value)
            # scale up and down the suggested value
            for value in suggested_values:
                for factor in self.factors:
                    explore_up = value + factor * (max_value - value)
                    explore_down = value + factor * (min_value - value)
                    if explore_up < sys.maxsize / 10 and explore_down < explore_up:
                        coarse_sequence.append(explore_up)
                        coarse_sequence.append(explore_down)
            
            if coarse_sequence == [] and (not min_from_sys or not max_from_sys):
                for factor in [0.25, 0.5, 0.75]:
                    coarse_sequence.append(boot_value + factor * (max_value - boot_value)) 
                if not min_from_sys:
                    coarse_sequence.append(min_value)
                if not max_from_sys:
                    coarse_sequence.append(max_value)
            coarse_sequence.append(boot_value)

            if max_value > sys.maxsize / 10:
                max_value = sys.maxsize / 10
            
            if min_value > sys.maxsize / 10:
                min_value = sys.maxsize / 10

            coarse_sequence = [value for value in coarse_sequence if value < sys.maxsize / 10]
            # check if this knob is special knob
            special_skill = self.datas[self.knob_]
            special = special_skill["special_knob"]
            if special is True:
                special_value = special_skill["special_value"]
            # control---
            control_value = {}
            control_value["choice"] = ["0", "1"]
            control_value["default_value"] = "0"
            # normal ---
            normal_value = {}
            normal_value["normal"] = [str(value) for value in coarse_sequence]
            normal_value["default_value"] = str(boot_value)
            if knob_type == "integer":  
                coarse_sequence = [int(value) for value in coarse_sequence]
                min_value = min(min_value, min(coarse_sequence))
                max_value = max(max_value, max(coarse_sequence))
                normal_para = UniformIntegerHyperparameter(
                    self.knob_, 
                    int(min_value), 
                    int(max_value),
                    default_value = int(boot_value),
                )

                if special:
                    special_knob_value = {}
                    # special
                    if type(special_value) is list:
                        special_knob_value[f"special_{self.knob_}"] = [str(value) for value in special_value]
                    else:
                        special_knob_value[f"special_{self.knob_}"] = int(special_value)
                    # normal
                    special_knob_value[f"normal_{self.knob_}"] = normal_value                       
                    self.knob_fine_value[str(self.knob_)] = special_knob_value
                    
                else:
                    self.knob_fine_value[str(self.knob_)] = normal_value
                
            elif knob_type == "real":
                coarse_sequence = [float(value) for value in coarse_sequence]
                min_value = min(min_value, min(coarse_sequence))
                max_value = max(max_value, max(coarse_sequence))
                normal_para = UniformFloatHyperparameter(
                    self.knob_,
                    float(min_value),
                    float(max_value),
                    default_value = float(boot_value),
                )
                if special:
                    # special
                    if type(special_value) is list:
                        special_knob_value[f"special_{self.knob_}"] = [str(value) for value in special_value]
                    else:
                        special_knob_value[f"special_{self.knob_}"] = float(special_value)
                    # normal
                    special_knob_value[f"normal_{self.knob_}"] = normal_value
                    self.knob_fine_value[str(self.knob_)] = special_knob_value
                else:
                    # self.search_space.add_hyperparameter(normal_para)
                    knob_info = {}
                    knob_info["lower"] = normal_para.lower
                    knob_info["upper"] = normal_para.upper
                    knob_info["default"] = normal_para.default_value
                    self.knob_fine_value[str(self.knob_)] = knob_info
                    
        else:
            info = self.dbms.knob_info[self.knob_]
            if info is None:
                return
            knob,knob_type = self.get_default_space_value(self.knob_, info)
            # self.search_space.add_hyperparameter(knob)
            knob_info = {}
            if knob_type == "integer" or "real":
                knob_info[lower] = knob.lower
                knob_info[upper] = knob.upper
                knob_info[default] = knob.default_value
                self.knob_fine_value[str(self.knob_)] = knob_info
            else:
                self.knob_fine_value[str(self.knob_)] = knob.choices
    def get_fine_value(self):
        return self.knob_fine_value     
    
    def get_default_space_value(self, knob_name, info):
        boot_value = info["reset_val"]
        min_value = info["min_val"]
        max_value = info["max_val"]
        knob_type = info["vartype"]
        if knob_type == "integer": 
            if int(max_value) > sys.maxsize:
                knob = UniformIntegerHyperparameter(
                    knob_name, 
                    int(int(min_value) / 1000), 
                    int(int(max_value) / 1000),
                    default_value = int(int(boot_value) / 1000)
                )
                
            else:
                knob = UniformIntegerHyperparameter(
                    knob_name,
                    int(min_value),
                    int(max_value),
                    default_value = int(boot_value),
                )
        elif knob_type == "real":
            knob = UniformFloatHyperparameter(
                knob_name,
                float(min_value),
                float(max_value),
                default_value = float(boot_value)
            )
        elif knob_type == "enum":
            knob = CategoricalHyperparameter(
                knob_name,
                [str(enum_val) for enum_val in info["enumvals"]],
                default_value = str(boot_value),
            )
        elif knob_type == "bool":
            knob = CategoricalHyperparameter(
                knob_name,
                ["on", "off"],
                default_value = str(boot_value)
            )
        return knob,knob_type     
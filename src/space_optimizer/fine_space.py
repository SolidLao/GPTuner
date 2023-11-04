from abc import ABC, abstractmethod
from space_optimizer.default_space import DefaultSpace
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

class FineSpace(DefaultSpace):

    def __init__(self, dbms, test, timeout, target_knobs_path, seed):
        super().__init__(dbms, test, timeout, target_knobs_path, seed)
        self.factors = [0, 0.25, 0.5]
        self.define_search_space()
        self.coarse_path = f"./optimization_results/{self.dbms.name}/coarse/{self.seed}/runhistory.json"


    def define_search_space(self):
        for knob in self.target_knobs:
            info = self.dbms.knob_info[knob]
            if info is None:
                self.target_knobs.remove(knob) # this knob is not by the DBMS under specific version
                continue

            knob_type = info["vartype"] 
            if knob_type == "enum" or knob_type == "bool":
                knob = self.get_default_space(knob, info)
                self.search_space.add_hyperparameter(knob)
                continue
            
            file_name = f"{knob}.json"
            if file_name in os.listdir(self.skill_path):
                with open(os.path.join(self.skill_path, file_name), 'r') as json_file:
                    data = json.load(json_file)
                
                print(f"Defining fine search space for knob: {knob}")
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
                        max_path = "./skill_library/mysql/max"
                        with open(os.path.join(max_path, knob+".txt"), 'r') as file:
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
                if boot_value > sys.maxsize / 10:
                    boot_value = sys.maxsize / 10


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
                
                special_skill_path = f"./knowledge_collection/{self.dbms.name}/structured_knowledge/special/"
                # check if this knob is special knob
                if file_name in os.listdir(special_skill_path):
                    with open(os.path.join(special_skill_path, file_name), 'r') as json_file:
                        special_skill = json.load(json_file)
                    special = special_skill["special_knob"]
                    if special is True:
                        special_value = special_skill["special_value"]
                
                if knob_type == "integer":  
                    coarse_sequence = [int(value) for value in coarse_sequence]
                    min_value = min(min_value, min(coarse_sequence))
                    max_value = max(max_value, max(coarse_sequence))
                    normal_para = UniformIntegerHyperparameter(
                        knob, 
                        int(min_value), 
                        int(max_value),
                        default_value = int(boot_value),
                    )

                    if special:
                        control_para = CategoricalHyperparameter(f"control_{knob}", ["0", "1"], default_value="0") 
                        if type(special_value) is list:
                            # special_para = OrdinalHyperparameter(f"special_{knob}", [int(value) for value in special_value])
                            special_para = CategoricalHyperparameter(f"special_{knob}", [str(value) for value in special_value])
                        else:
                            special_para = Constant(f"special_{knob}", int(special_value))

                        self.search_space.add_hyperparameters([control_para, normal_para, special_para])
                        
                        normal_cond = EqualsCondition(self.search_space[knob], self.search_space[f"control_{knob}"], "0")
                        special_cond = EqualsCondition(self.search_space[f"special_{knob}"], self.search_space[f"control_{knob}"], "1")
                        
                        self.search_space.add_conditions([normal_cond, special_cond])
                    else:
                        self.search_space.add_hyperparameter(normal_para)
                    
                elif knob_type == "real":
                    coarse_sequence = [float(value) for value in coarse_sequence]
                    min_value = min(min_value, min(coarse_sequence))
                    max_value = max(max_value, max(coarse_sequence))
                    normal_para = UniformFloatHyperparameter(
                        knob,
                        float(min_value),
                        float(max_value),
                        default_value = float(boot_value),
                    )
                    if special:
                        control_para = CategoricalHyperparameter(f"control_{knob}", ["0", "1"], default_value="0") 
                        if type(special_value) is list:
                            special_para = CategoricalHyperparameter(f"special_{knob}", [str(value) for value in special_value])
                        else:
                            special_para = Constant(f"special_{knob}", float(special_value))

                        self.search_space.add_hyperparameters([control_para, normal_para, special_para])
                        normal_cond = EqualsCondition(self.search_space[knob], self.search_space[f"control_{knob}"], "0")
                        special_cond = EqualsCondition(self.search_space[f"special_{knob}"], self.search_space[f"control_{knob}"], "1")
                        
                        self.search_space.add_conditions([normal_cond, special_cond])
                    else:
                        self.search_space.add_hyperparameter(normal_para)
            else:
                info = self.dbms.knob_info[knob]
                if info is None:
                    continue
                knob = self.get_default_space(knob, info)
                self.search_space.add_hyperparameter(knob)
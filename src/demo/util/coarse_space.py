from demo.util.default_space import DefaultSpace
from dbms.mysql import MysqlDBMS
import sys
import os
import json
import re
from smac import HyperparameterOptimizationFacade, Scenario, initial_design
from ConfigSpace import (
    CategoricalHyperparameter,
    Constant,
    EqualsCondition,
)

class CoarseSpace(DefaultSpace):

    def __init__(self, dbms, test, timeout, structured_knowledge, suggested_values, target_knobs, workload_queries="", seed=1):
        super().__init__(dbms, test, timeout, structured_knowledge, suggested_values, target_knobs, workload_queries, seed)
        self.factors = [0, 0.25, 0.5]
        self.define_search_space()
        self.structured_knowledge = structured_knowledge
        self.suggested_values = suggested_values
    

    def define_search_space(self):
        for knob in self.target_knobs:
            print(knob)
            info = self.dbms.knob_info[knob]
            if info is None:
                self.target_knobs.remove(knob) # this knob is not by the DBMS under specific version
                continue

            knob_type = info["vartype"] 

            if knob_type == "enum" or knob_type == "bool":
                knob = self.get_default_space(knob, info)
                self.search_space.add_hyperparameter(knob)
                continue
            

            if knob in self.datas:
                data = self.datas[knob]

                print(f"Defining coarse search space for knob: {knob}")
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
                    if max_from_sys or max_value >= sys.maxsize / 10:  #   for mysql
                        max_path = "./knowledge_collection/mysql/structured_knowledge/max"
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
                sequence = []
                min_value = min(min_value, boot_value)
                max_value = max(max_value, boot_value)

                
                for value in suggested_values:
                    for factor in self.factors:
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
          

                # check if this knob is special knob
                special_skill = self.datas[knob]
                special = special_skill["special_knob"]
                if special is True:
                    special_value = special_skill["special_value"]

                if knob_type == "integer":  
                    sequence = [int(value) for value in sequence]
                    sequence = list(set(sequence))
                    sequence.sort()
                    normal_para = CategoricalHyperparameter(
                        knob,
                        [str(value) for value in sequence],
                        default_value = str(boot_value),
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
                    sequence = [float(value) for value in sequence]
                    sequence = list(set(sequence))
                    sequence.sort()

                    normal_para = CategoricalHyperparameter(
                        knob,
                        [str(value) for value in sequence],
                        default_value = str(boot_value),
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

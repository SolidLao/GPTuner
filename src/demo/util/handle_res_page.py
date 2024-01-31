import json
import os
import time
import shutil
import pandas as pd
import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_echarts import JsCode
from streamlit_autorefresh import st_autorefresh
knob_ls = set()
root_dir = os.path.abspath(os.path.join(os.getcwd()))
def getPerformance(default, workload,root_dir,data_coarse_dir,data_fine_dir):
    # parameters defined
    coarse_dir = root_dir + data_coarse_dir
    fine_dir = root_dir + data_fine_dir
    default_pos = 10
    gpt_cost = []
    rid_ten = True
    # check whether the files exists
    course_begin = os.path.exists(coarse_dir)
    fine_begin = os.path.exists(fine_dir)
    if course_begin:
        with open(coarse_dir, 'r') as file:
            coarse_history = json.load(file)
        coarse_len = len(coarse_history['data'])
        # print(coarse_len)
        for i, item in enumerate(coarse_history['data'][:coarse_len]):
            if item[4] == 2147483647:
                gpt_cost.append(default)
            else:
                gpt_cost.append(abs(item[4]))
    
    if fine_begin:
        with open(fine_dir, 'r') as file:
            fine_history = json.load(file)
        fine_len = len(fine_history['data'])
        for item in fine_history['data'][30:]:
            gpt_cost.append(abs(item[4]))
    if course_begin:
        gpt_cost = gpt_cost[1:]
        gpt_cost.insert(0, default)
        if len(gpt_cost)>=13 and rid_ten:
            min_LSH = min(gpt_cost[1:12])
            gpt_cost[1] = min_LSH
            gpt_cost = gpt_cost[:2] + gpt_cost[12:]
            gpt_cost = modify_list(gpt_cost, workload)
        elif len(gpt_cost)<13:
            return "wait"
    for i in range(len(gpt_cost)):
        gpt_cost[i] = gpt_cost[i]/1e6
    return gpt_cost

def modify_list(lst, benchmark):
    if benchmark == 'TPC-H' or benchmark == "Customized Workload":
        min_value = lst[0]
        modified_lst = [min_value]
        for i in range(1, len(lst)):
            lst[i] = abs(lst[i])
            if lst[i] > modified_lst[-1]:
                modified_lst.append(min_value)
            else:
                modified_lst.append(lst[i])
                min_value = min(min_value, lst[i])

    elif benchmark == 'TPC-C':
        max_value = lst[0]
        modified_lst = [max_value]
        for i in range(1, len(lst)):
            lst[i] = abs(lst[i])
            if lst[i] < modified_lst[-1]:
                modified_lst.append(max_value)
            else:
                modified_lst.append(lst[i])
                min_value = max(max_value, lst[i])

    return modified_lst


def get_sql_file(option,knob_list, knob_value):
    file_name = "iteration"+str(option)+"config.sql"
    mode = "w"
    knob_list = list(knob_list)
    with open(file_name, mode) as file:
        for i in range(len(knob_list)):
            query_one = f'alter system set {knob_list[i]} to \'{knob_value[i]}\';\n'
            file.write(query_one)

def getKnobLs(choice,data_coarse_dir,data_fine_dir):
    
    global knob_ls
    if len(knob_ls) == 0:
        knobs_dir = data_coarse_dir
        knobs_dir_ = data_fine_dir
        tune_begin = os.path.exists(knobs_dir)
        fine_begin = os.path.exists(data_fine_dir)
        if tune_begin:
            with open(knobs_dir, 'r') as ls_file:
                coarse_history = json.load(ls_file)
            if fine_begin and choice > 30:    
                with open(knobs_dir_, 'r') as ls_file:
                    fine_history = json.load(ls_file)  
                choice_knob_ls = fine_history['configs'][str(choice+10-30)]
            else:
                choice_knob_ls = coarse_history['configs'][str(choice)]
            temp_ls = set()
            for knob in choice_knob_ls:
                if knob.startswith("control_"):
                    knob_ = knob[len("control_"):]
                    temp_ls.add(knob_)
                elif knob.startswith("special_"):
                    knob_ = knob[len("special_"):]
                    temp_ls.add(knob_)
                else:
                    temp_ls.add(knob)
            knob_ls = temp_ls.copy()
        else:
            st.markdown("After the tuning finishes the first iteration, you can see the knobs and their value here;\
                        :tulip::cherry_blossom::rose::hibiscus::sunflower::blossom:")

    return knob_ls

def getKnobInfo(choice,data_coarse_dir,data_fine_dir):
    coarse_dir = root_dir + data_coarse_dir
    fine_dir = root_dir + data_fine_dir
    #
    course_begin = os.path.exists(coarse_dir)
    fine_begin = os.path.exists(fine_dir)
    # get knob_ls
    knob_list = getKnobLs(choice,coarse_dir,fine_dir)
    knob_value_list = []
    if course_begin and choice <= 30:
        with open(coarse_dir, 'r') as file:
            coarse_history = json.load(file)

        for knob in knob_list:
            # control_knob
            control_knob = "control_" + knob
            if control_knob in coarse_history['configs'][str(choice)]:
                if coarse_history['configs'][str(choice)][control_knob] == "0":
                    value = coarse_history['configs'][str(choice)][knob]
                    knob_value_list.append(value)
                else:  # special
                    special_knob = "special_" + knob
                    value = coarse_history['configs'][str(choice)].get(special_knob, "!!!!!!!!!!not found")
                    knob_value_list.append(value)
            else:
                value = coarse_history['configs'][str(choice)][knob]
                knob_value_list.append(value)

    # print(knob_value_list)
    if fine_begin and choice > 30:
        with open(fine_dir, 'r') as file:
            fine_history = json.load(file)
        for knob in knob_list:
            # control_knob
            control_knob = "control_" + knob
            if control_knob in fine_history['configs'][str(choice +10 - 30)]:
                if fine_history['configs'][str(choice - 30)][control_knob] == "0":
                    value = fine_history['configs'][str(choice +10 - 30)][knob]
                    knob_value_list.append(value)
                else:  # special
                    special_knob = "special_" + knob
                    print(fine_history['configs'][str(choice +10 - 30)])
                    value = fine_history['configs'][str(choice +10 - 30)][special_knob]
                    knob_value_list.append(value)
            else:
                value = fine_history['configs'][str(choice +10 - 30)][knob]
                knob_value_list.append(value)

    return knob_list, knob_value_list

def clear_history(data_coarse_dir,data_fine_dir):
    for root, dirs, files in os.walk(root_dir+data_coarse_dir, topdown=False):
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            try:
                shutil.rmtree(folder_path)
                print(f"The folder have been deleted: {folder_path}")
            except Exception as e:
                print(f"Cannot delete the folder!! {folder_path}: {e}")
    
    for root, dirs, files in os.walk(root_dir+data_fine_dir, topdown=False):
        for dir_name in dirs:
            folder_path = os.path.join(root, dir_name)
            try:
                shutil.rmtree(folder_path)
                print(f"The folder have been deleted: {folder_path}")
            except Exception as e:
                print(f"Cannot delete the folder!! {folder_path}: {e}")

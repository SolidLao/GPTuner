import psutil
import os

def get_hardware_info():
    available_cpu_cores = psutil.cpu_count(logical=False)
    memory = psutil.virtual_memory()
    total_memory = memory.total
    total_memory = total_memory / (1024 * 1024 * 1024)
    root_disk = psutil.disk_usage('/')
    total_disk_space = root_disk.total
    total_disk_space = total_disk_space / (1024 * 1024 * 1024)
    return available_cpu_cores, int(total_memory), int(total_disk_space)

def get_disk_type(device="sda"):
    rotational_path = f'/sys/block/{device}/queue/rotational'
    if os.path.exists(rotational_path):
        with open(rotational_path, 'r') as file:
            rotational_value = file.read().strip()
            if rotational_value == '0':
                return 'SSD'
            elif rotational_value == '1':
                return 'HDD'
            else:
                return 'Unknown'
    else:
        return 'Unknown'
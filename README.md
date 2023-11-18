<img align='right' src="/assets/gptuner.png" alt="GPTuner logo" width="130">

# GPTuner: A Manual-Reading Database Tuning System via GPT-Guided Bayesian Optimization

- This repository hosts the source code and supplementary materials for our VLDB 2024 submission, [GPTuner: A Manual-Reading Database Tuning System via GPT-Guided Bayesian Optimization](https://web1.arxiv.org/abs/2311.03157). 
- GPTuner collects and refines heterogeneous domain knowledge, unifies a structured view of the refined knowledge, and uses the knowlege to (1) select important knobs, (2) optimize the value range of each knob and (3) explore the optimized space with a novel Coarse-to-Fine Bayesian Optimization Framework.

>Stay tuned for the latest updates and enhancements in this project! 🚀<br/>
>Remember to star ⭐ and subscribe 🔔 for the newest features and improvements!

## Table of Contents
- [System Overview](#system-overview)
- [Quick Start](#quick-start)
- [Experimental Results](#experimental-result)
- [Code Structure](#code-structure)
- [Citation](#citation)

## System Overview

<img src="/assets/gptuner_overview.png" alt="GPTuner overview" width="800">

**GPTuner** is a manual-reading database tuning system to suggest satisfactory knob configurations with reduced tuning costs. The figure above presents the tuning workflow that involves seven steps:
1. 📌 User provides the DBMS to be tuned (e.g., PostgreSQL or MySQL), the target workload, and the optimization objective (e.g., latency or throughput).
2. 📌 GPTuner collects and refines the heterogeneous knowledge from different sources (e.g., GPT-4, DBMS manuals, and web forums) to construct _Tuning Lake_, a collection of DBMS tuning knowledge.
3. 📌 GPTuner unifies the refined tuning knowledge from _Tuning Lake_ into a structured view accessible to machines (e.g., JSON).
4. 📌 GPTuner reduces the search space dimensionality by selecting important knobs to tune (i.e., fewer knobs to tune means fewer dimensions).
5. 📌 GPTuner optimizes the search space in terms of the value range for each knob based on structured knowledge.
6. 📌 GPTuner explores the optimized space via a novel Coarse-to-Fine Bayesian Optimization framework.
7. 📌 Finally, GPTuner identifies satisfactory knob configurations within resource limits (e.g., the maximum optimization time or iterations specified by users).

## Quick Start
The following instructions have been tested on Ubuntu 20.04 and PostgreSQL v14.9:

### Step 1: Install PostgreSQL:
```
sudo apt-get update
sudo apt-get install postgresql-14
```

### Step 2: Install [BenchBase](https://github.com/cmu-db/benchbase) with our script:
- Note: the script is tested on `openjdk version "17.0.8.1" 2023-08-24`, please prepare your JAVA environment first
```
cd ./scripts
sh install_benchbase.sh postgres
```

### Step 3: Install Benchmark with our script:

- Note: modify `./benchbase/target/benchbase-postgres/config/postgres/sample_{your_target_benchmark}_config.xml` to customize your tuning setting first
```
sh build_benchmark.sh postgres tpch
```

### Step 4: Install dependencies:
```
sudo pip install -r requirements.txt
```

### Step 5: Execute the GPTuner to optimize your DBMS:

- Note: modify `configs/postgres.ini` to determine the target DBMS first, the `restart` and `recover` commands depend on the environment and we provide Docker version
- Note: modify `src/run_gptuner.py` to set up your `api_base`, `api_key` and `model` first
```
# PYTHONPATH=src python src/run_gptuner.py <dbms> <benchmark> <timeout> <seed>
PYTHONPATH=src python src/run_gptuner.py postgres tpch 180 -seed=100
```
where `<dbms>` specifies the DBMS (e.g., postgres or mysql), `<benchmark>` is the target workload (e.g., tpch or tpcc), `<timeout>` is the maximum time allowed to stress-test the benchmark, `<seed>` is the random seed used by the optimizer.

### Step 6: View the optimization result:
The optimization result is stored in `optimization_results/{dbms}/{stage}/{seed}/runhistory.json`, where `{dbms}` is the target DBMS, `{stage}` is coarse or fine and `{seed}` is the random seed given by user.
- the `data` block contains the following information, we explain the project-related information below. For more details, please refer to [SMAC3 Library](https://github.com/automl/SMAC3).
    - `config_id`: i is the identifier for the knob configuration given by i-th iteration 
    - instance
    - budget
    - seed
    - `cost`: the optimization objective (e.g., throughput or latency)
    - time
    - status
    - starttime
    - endtime
    - additional_info
- the `"configs"` block contains the knob configuration of the i-th iteration, for example:
```
"configs": {
    "1": {
      "effective_io_concurrency": 200,
      "random_page_cost": 1.2 
    },
}
```

## Experimental Result

### Baselines
We compare GPTuner with state-of-the-art methods both using or not using natural language knowledge as input:
- [DB-BERT SIGMOD'22](https://dl.acm.org/doi/10.1145/3514221.3517843): a DBMS tuning tool that uses BERT to read the manuals and use the gained information to guide Reinforcement Learning(RL)
- SMAC: the best Bayesian Optimiztion (BO)-based method evaluated in an [Experimental Evaluation VLDB'22](https://dl.acm.org/doi/10.14778/3538598.3538604)
- GP: the classic Gassian Process-based BO approach used in [iTuned VLDB'09](https://dl.acm.org/doi/10.14778/1687627.1687767) and [OtterTune SIGMOD'17](https://dl.acm.org/doi/10.1145/3035918.3064029)
- DDPG++: a RL-based tuning method proposed in [CDBTune SIGMOD'19](https://dl.acm.org/doi/10.1145/3299869.3300085) and improved in [Inquiry VLDB'21](https://dl.acm.org/doi/10.14778/3450980.3450992)

### Result on PostgreSQL
We compare GPTuner with baselines on different DBMS (PostgreSQL and MySQL), benchmarks (TPC-H and TPC-C) and metrics (throughput and latency). We present the results on PostgreSQL in this repository. For more details, please refer to our [paper](https://web1.arxiv.org/abs/2311.03157).

<img src="/assets/gptuner_result_postgresql.png" alt="GPTuner result on postgres" width="500">

## Code Structure
- `configs/`
  - `postgres.ini`: Configuration file to optimize PostgreSQL
  - `mysql.ini`: Configuration file to optimize MySQL
- `optimization_results/`
  - `temp_results/`: Temporary storage for optimization results
  - `postgres/`
    - `coarse/`: Coarse-stage optimization results for PostgreSQL
    - `fine/`: Fine-stage optimization results for PostgreSQL
- `scripts/`
  - `install_benbase.sh`: Script to install the BenchBase benchmark tool
  - `build_benchmark.sh`: Script to build benchmark environments
  - `recover_postgres.sh`: Script to recover the state of PostgreSQL database
  - `recover_mysql.sh`: Script to recover the state of MySQL database
- `knowledge_collection/`
  - `postgres/`
    - `target_knobs.txt`: List of target knobs for PostgreSQL tuning
    - `knob_info/`
      - `system_view.json`: Information from PostgreSQL system views (pg_settings)
      - `official_document.json`: Information from PostgreSQL official documentation
    - `knowledge_sources/`
      - `gpt/`: Knowledge sourced from GPT models
      - `manual/`: Knowledge from DBMS manuals
      - `web/`: Knowledge extracted from web sources
      - `dba/`: Knowledge from database administrators
    - `tuning_lake/`: Data lake for DBMS tuning knowledge
    - `structured_knowledge/`
      - `special/`: Specialized structured knowledge
      - `normal/`: General structured knowledge
- `example_pool/`: Pool of examples for prompt ensemble algorithm
- `sql`: Provide sql statements if you need query-level knob selection
- `src/`: Source code
  - `dbms/`
    - `dbms_template.py`: Template for database management systems
    - `postgres.py`: Implementation for PostgreSQL
    - `mysql.py`: Implementation for MySQL
  - `knowledge_handler/`
    - `gpt.py`: Module for interactions with GPT
    - `knowledge_preparation.py`: Module for knowledge preparation (**Sec. 5.1**)
    - `knowledge_transformation.py`: Module for knowledge transformation (**Sec. 5.2**)
  - `space_optimizer/`
    - `knob_selection.py`: Module for knob selection (**Sec. 6.1**)
    - `default_space.py`: Definition of default search space
    - `coarse_space.py`: Definition of coarse search space (**Sec. 6.2**)
    - `fine_space.py`: Definition of fine search space (**Sec. 6.2**)
  - `config_recommender/`
    - `workload_runner.py`: Module to run workloads
    - `coarse_stage.py`: Recommender for coarse stage configuration (**Sec. 7**)
    - `fine_stage.py`: Recommender for fine stage configuration (**Sec. 7**)
  - `run_gptuner.py`: Main script to run GPTuner

## Roadmap
- Paper version
  - GPTuner uses OpenAI completion API of `gpt-4` or `gpt-3.5-turbo`
  - GPTuner leverages tuning knowledge from `GPT-4`, `DBMS official manuals` and `web contents`
  - GPTuner supports `PostgreSQL` and `MySQL`
  - GPTuner stress-tests workloads through the `BenchBase` tool
- Future implementation
  - [] GPTuner employs `locally depolyed large language models` as well
  - [] GPTuner collects web contents through `web-gpt` and `web-crawler`
  - [] GPTuner uses a `generic` stress-test tool, supporting `any given workload` optimization
  - [] GPTuner supports more `DBMS`
  - [] GPTuner refines its `knowledge_collection` with a `human-in-the-loop` mechanism
  - [] to be continued...

## Citation
If you use this codebase, or otherwise found our work valuable, please cite:
```
@misc{lao2023gptuner,
    title={GPTuner: A Manual-Reading Database Tuning System via GPT-Guided Bayesian Optimization}, 
    author={Jiale Lao and Yibo Wang and Yufei Li and Jianping Wang and Yunjia Zhang and Zhiyuan Cheng and Wanghu Chen and Mingjie Tang and Jianguo Wang},
    year={2023},
    eprint={2311.03157},
    archivePrefix={arXiv},
    primaryClass={cs.DB}
}
```
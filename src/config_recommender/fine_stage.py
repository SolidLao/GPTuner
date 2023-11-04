from abc import ABC, abstractmethod
from space_optimizer.default_space import DefaultSpace
from dbms.mysql import MysqlDBMS
from dbms.postgres import PgDBMS
from space_optimizer.fine_space import FineSpace
import json
from smac import HyperparameterOptimizationFacade, Scenario, initial_design, intensifier
from ConfigSpace import (
    UniformIntegerHyperparameter,
    UniformFloatHyperparameter,
    CategoricalHyperparameter,
    Configuration,
)

class FineStage(FineSpace):

    def __init__(self, dbms, test, timeout, target_knobs_path, seed):
        super().__init__(dbms, test, timeout, target_knobs_path, seed)

    def optimize(self, name, trials_number):
        scenario = Scenario(
            configspace=self.search_space,
            name = name,
            deterministic=True,
            n_trials=trials_number,
            seed=self.seed,
        )
        init_design = initial_design.DefaultInitialDesign(
            scenario,
        )
        smac = HyperparameterOptimizationFacade(
            scenario=scenario,
            initial_design=init_design,
            target_function=self.set_and_replay,
            intensifier=intensifier.Intensifier(scenario, retries=30),
        )
        # how to be guided by coarse-grained tuning
        with open(self.coarse_path, "r") as json_file:
            data = json.load(json_file)
        costs = []
        for i in range(30):
            costs.append(data["data"][i][4])
        # the [:x] configurations with minimal costs
        index_min_pairs = sorted(enumerate(costs), key=lambda x: x[1])[:30]
        # no ordering
        # for index, value in enumerate(costs):
        for index, value in index_min_pairs:
            config_id = index + 1
            config_value_dict = data["configs"][str(config_id)]
            config_cost = data["data"][index][4]
            assert value == config_cost
            # make type transformation from coarse to fine 
            transfer_config_value_dict = {}
            for key, value in config_value_dict.items():
                if key.startswith("control_") or key.startswith("special_"):
                    transfer_config_value_dict[key] = value
                    continue
                hp = self.search_space[key]
                if isinstance(hp, CategoricalHyperparameter):
                    transfer_config_value_dict[key] = str(value)
                elif isinstance(hp, UniformIntegerHyperparameter):
                    transfer_config_value_dict[key] = int(value) 
                elif isinstance(hp, UniformFloatHyperparameter):
                    transfer_config_value_dict[key] = float(value)
                else:
                    transfer_config_value_dict[key] = value
            config = Configuration(self.search_space, transfer_config_value_dict)
            smac.runhistory.add(config, config_cost, seed=self.seed)
        smac.optimize()
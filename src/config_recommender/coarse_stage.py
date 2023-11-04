from space_optimizer.coarse_space import CoarseSpace
from smac import HyperparameterOptimizationFacade, Scenario, initial_design

class CoarseStage(CoarseSpace):

    def __init__(self, dbms, test, timeout, target_knobs_path, seed):
        super().__init__(dbms, test, timeout, target_knobs_path, seed)

    def optimize(self, name, trials_number, initial_config_number):
        scenario = Scenario(
            configspace=self.search_space,
            name=name,
            seed=self.seed,
            deterministic=True,
            n_trials=trials_number,
            use_default_config=True,

        )
        init_design = initial_design.LatinHypercubeInitialDesign(
            scenario,
            n_configs=initial_config_number,
            max_ratio=0.8,  # set this to a value close to 1 to get exact initial_configs as specified
        )
        smac = HyperparameterOptimizationFacade(
            scenario=scenario,
            initial_design=init_design,
            target_function=self.set_and_replay,
            overwrite=False,
        )
        
        smac.optimize()
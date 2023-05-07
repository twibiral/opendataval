import itertools
import time

import numpy as np
import pandas as pd
import torch
import tqdm
from numpy.random import RandomState
from sklearn.utils import check_random_state


def load_mediator_output(file_path: str):
    """Loads output of Pandas DataFrame csv generated by ExperimentMediator."""
    return pd.read_csv(file_path, index_col=[0, 1])


def set_random_state(random_state: RandomState = None) -> RandomState:
    """Set the random state of opendataval, useful for recreation of results."""
    print(f"Initial random seed is: {random_state}.")
    torch.manual_seed(check_random_state(random_state).tomaxint())
    random_state = check_random_state(random_state)
    return random_state


class MeanStdTime:
    def __init__(self, input_data: list[float], elapsed_time: float):
        self.mean = np.mean(input_data)
        self.std = np.std(input_data, ddof=1)
        self.avg_time = elapsed_time / len(input_data)

    def __repr__(self):
        return (
            f"mean={self.mean} | std={self.std} | "
            f"average_time={self.avg_time} | 1e5 in min {1e5*self.avg_time/60}"
        )


class ParamSweep:
    def __init__(self, pred_model, evaluator, fetcher, samples=10):
        self.model = pred_model
        self.x_train, self.y_train, self.x_valid, self.y_valid, *_ = fetcher.datapoints
        self.evaluator = evaluator
        self.samples = samples

    def sweep(self, **kwargs_list) -> dict[str, MeanStdTime]:
        self.result = {}
        for kwargs in self._param_product(**kwargs_list):
            perf_list = []
            start_time = time.perf_counter()
            for _ in tqdm.trange(self.samples):
                curr_model = self.model.clone()
                curr_model.fit(self.x_train, self.y_train, **kwargs)
                yhat = curr_model.predict(self.x_valid)
                perf = self.evaluator(yhat, self.y_valid)
                perf_list.append(perf)
            self.result[str(kwargs)] = MeanStdTime(
                perf_list, time.perf_counter() - start_time
            )
        return self.result

    @staticmethod
    def _param_product(**kwarg_list):
        keys = kwarg_list.keys()
        for instance in itertools.product(*kwarg_list.values()):
            yield dict(zip(keys, instance))

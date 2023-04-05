import os
from typing import Any, Callable, Self

import numpy as np
import opendatasets as od
import pandas as pd
import requests
import sklearn.datasets as ds
from sklearn.preprocessing import minmax_scale
from torch.utils.data import Dataset

DatasetCallable = Callable[..., Dataset | np.ndarray | tuple[np.ndarray, np.ndarray]]


def one_hot_encode(data: np.ndarray) -> np.ndarray:
    """One hot encodes a 1D numpy array."""
    num_values = np.max(data) + 1
    return np.eye(num_values)[data]


def cache(url: str, cache_dir: str, file_name: str, force_download: bool) -> str:
    """Download a file if it it is not present and returns the file_path.

    Parameters
    ----------
    url : str
        URL of the file to be downloaded
    cache_dir : str
        Directory to cache downloaded files
    file_name : str, optional
        File name within the cache directory of the downloaded file, by default ""
    force_download : bool, optional
        Forces a download regardless if file is present, by default False

    Returns
    -------
    str
        File path to the downloaded file
    """
    if file_name is None:
        file_name = os.path.basename(url)

    if not os.path.isdir(cache_dir):
        os.mkdir(cache_dir)

    filepath = os.path.join(cache_dir, file_name)

    if not os.path.isfile(filepath) or force_download:
        with requests.get(url, stream=True, timeout=60) as r, open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):  # In case file is large
                f.write(chunk)

    return filepath


def _read_csv(file_path: str, label_columns: str | list) -> DatasetCallable:
    """Create data set from csv file path, nested functions for api consistency."""
    return lambda: _from_pandas(pd.read_csv(file_path), label_columns)()


def _from_pandas(df: pd.DataFrame, label_columns: str | list) -> DatasetCallable:
    """Create data set from pandas dataframe, nested functions for api consistency."""
    if all(isinstance(col, int) for col in label_columns):
        label_columns = df.columns[label_columns]
    return lambda: (df.drop(label_columns, axis=1).values, df[label_columns].values)


def _from_numpy(array, label_columns: int | list[int]) -> DatasetCallable:
    """Create data set from numpy array, nested functions for api consistency."""
    if isinstance(label_columns, int):
        label_columns = [label_columns]
    return lambda: (np.delete(array, label_columns, axis=1), array[:, label_columns])


class Register:
    """Register a data set by defining its name and adding functions to retrieve data.

    Registers data sets to be loaded by the DataLoader. Also allows specific
    transformations to be applied on a data set. This gives the benefit of creating
    :py:class:`Register` objects to distinguish separate data sets

    Parameters
    ----------
    dataset_name : str
        Data set name
    categorical : bool, optional
        Whether the data set is categorically labeled, by default False
    cacheable : bool, optional
        Whether data set can be downloaded and cached, by default False
    dataset_kwargs : dict[str, Any], optional
        Keyword arguments to pass to the data set functions, by default None

    Raises
    ------
    KeyError
        :py:class:`Register` keeps track of all data set names registered and all must
        be unique. If there are any duplicates, raises KeyError.
    """

    CACHE_DIR = "data_files"

    Datasets: dict[str, Self] = {}
    """Creates a directory for all registered/downloadable data set functions."""

    def __init__(
        self,
        dataset_name: str,
        categorical: bool = False,
        cacheable: bool = False,
        dataset_kwargs: dict[str, Any] = None,
    ):
        if dataset_name in Register.Datasets:
            raise KeyError(f"{dataset_name} has been registered, names must be unique")

        self.dataset_name = dataset_name
        self.dataset_kwargs = dataset_kwargs if dataset_kwargs else {}
        self.categorical = categorical

        self.covar_transform = None
        self.label_transform = None
        if categorical:
            self.label_transform = one_hot_encode

        if cacheable:
            self.download_dir = os.path.join(
                os.getcwd(), f"{Register.CACHE_DIR}/{dataset_name}"
            )

        Register.Datasets[dataset_name] = self

    def from_csv(self, file_path: str, label_columns: str | list):
        """Register data set from csv file."""
        self.covar_label_func = _read_csv(file_path, label_columns)
        return self

    def from_pandas(self, df: pd.DataFrame, label_columns: str | list):
        """Register data set from pandas data frame."""
        self.covar_label_func = _from_pandas(df, label_columns)
        return self

    def from_numpy(self, df: pd.DataFrame, label_columns: int | list[int]):
        """Register data set from numpy array."""
        self.covar_label_func = _from_numpy(df, label_columns)
        return self

    def from_covar_label_func(self, func: DatasetCallable) -> DatasetCallable:
        """Register data set from Callable -> (covariates, labels)."""
        self.covar_label_func = func
        return Self

    def from_covar_func(self, func: DatasetCallable) -> DatasetCallable:
        """Register data set from 2 Callables, registers covariates Callable."""
        self.cov_func = func
        return func

    def from_label_func(self, func: DatasetCallable) -> DatasetCallable:
        """Register data set from 2 Callables, registers labels Callable."""
        self.label_func = func
        return func

    def add_covar_transform(self, transform: Callable[[np.ndarray], np.ndarray]):
        """Add covariate transform after data is loaded."""
        self.covar_transform = transform
        return self

    def add_label_transform(self, transform: Callable[[np.ndarray], np.ndarray]):
        """Add label transform after data is loaded."""
        self.label_transform = transform
        return self

    def load_data(self, force_download: bool = False) -> tuple[Dataset, np.ndarray]:
        """Retrieve data from specified data input functions.

        Loads the covariates and labels from the registered callables, applies
        transformations, and returns the covariates and labels.

        Parameters
        ----------
        force_download : bool, optional
            Forces download from source URL, by default False

        Returns
        -------
        (np.ndarray | Dataset, np.ndarray)
            Transformed covariates and labels of the data set
        """
        if hasattr(self, "download_dir"):
            self.dataset_kwargs["cache_dir"] = self.download_dir
            self.dataset_kwargs["force_download"] = force_download

        if hasattr(self, "covar_label_func"):
            covar, labels = self.covar_label_func(**self.dataset_kwargs)
        else:
            covar = self.cov_func(**self.dataset_kwargs)
            labels = self.label_func(**self.dataset_kwargs)

        if self.covar_transform:
            if isinstance(covar, Dataset):
                covar.transform = self.covar_transform
            else:
                covar = self.covar_transform(covar)

        if self.label_transform:
            labels = self.label_transform(labels)

        return covar, labels


@Register("gaussian_classifier", categorical=True).from_covar_label_func
def gaussian_classifier(n: int = 10000, input_dim: int = 10):
    covar = np.random.normal(size=(n, input_dim))

    beta_true = np.random.normal(size=input_dim).reshape(input_dim, 1)
    p_true = np.exp(covar.dot(beta_true)) / (1.0 + np.exp(covar.dot(beta_true)))

    labels = np.random.binomial(n=1, p=p_true).reshape(-1)

    return covar, labels


@Register("adult", categorical=True, cacheable=True).from_covar_label_func
def download_adult(cache_dir: str, force_download: bool = False):
    """Adult Income data set. Implementation from DVRL repository.

    References
    ----------
    DVRL paper: https://arxiv.org/abs/1909.11671.
    UCI Adult data link: https://archive.ics.uci.edu/ml/datasets/Adult
    """
    uci_url = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult"
    train_url = cache(uci_url + "/adult.data", cache_dir, "train.csv", force_download)
    test_url = cache(uci_url + "/adult.test", cache_dir, "test.csv", force_download)

    data_train = pd.read_csv(train_url, header=None)
    data_test = pd.read_csv(test_url, skiprows=1, header=None)

    df = pd.concat((data_train, data_test), axis=0)

    # Column names
    df.columns = [
        "Age",
        "WorkClass",
        "fnlwgt",
        "Education",
        "EducationNum",
        "MaritalStatus",
        "Occupation",
        "Relationship",
        "Race",
        "Gender",
        "CapitalGain",
        "CapitalLoss",
        "HoursPerWeek",
        "NativeCountry",
        "Income",
    ]

    # Creates binary labels
    df["Income"] = df["Income"].map(
        {" <=50K": 0, " >50K": 1, " <=50K.": 0, " >50K.": 1}
    )

    # Changes string to float
    df.Age = df.Age.astype(float)
    df.fnlwgt = df.fnlwgt.astype(float)
    df.EducationNum = df.EducationNum.astype(float)
    df.EducationNum = df.EducationNum.astype(float)
    df.CapitalGain = df.CapitalGain.astype(float)
    df.CapitalLoss = df.CapitalLoss.astype(float)

    # One-hot encoding
    df = pd.get_dummies(
        df,
        columns=[
            "WorkClass",
            "Education",
            "MaritalStatus",
            "Occupation",
            "Relationship",
            "Race",
            "Gender",
            "NativeCountry",
        ],
    )

    # Sets label name as Y
    df = df.rename(columns={"Income": "Income"})
    df["Income"] = df["Income"].astype(int)

    # Resets index
    df = df.reset_index()
    df = df.drop(columns=["index"])
    return df.drop("Income", axis=1).values, df["Income"].values


@Register("iris", categorical=True).from_covar_label_func
def download_iris():
    return ds.load_iris(return_X_y=True)


@Register("diabetes", categorical=True).from_covar_label_func
def download_diabetes():
    return ds.load_diabetes(return_X_y=True)


@Register("digits", categorical=True).from_covar_label_func
def download_digits():
    return ds.load_digits(return_X_y=True)


@Register("breast_cancer", True).add_covar_transform(minmax_scale).from_covar_label_func
def download_breast_cancer():
    return ds.load_breast_cancer(return_X_y=True)


@Register("election", categorical=True, cacheable=True).from_covar_label_func
def download_election(cache_dir: str, force_download: bool):
    """Presidential election results by state since 1976 courtesy of Bojan Tunguz.

    References
    ----------
    Kaggle source: https://www.kaggle.com/datasets/tunguz/us-elections-dataset
    """
    if not os.path.isdir(cache_dir):
        os.makedirs(cache_dir)

    dataset_url = "https://www.kaggle.com/tunguz/us-elections-dataset"
    od.download(dataset_url, data_dir=cache_dir, force=force_download)

    df = pd.read_csv(f"{cache_dir}/us-elections-dataset/1976-2020-president.csv")
    df = df.drop(
        ["notes", "party_detailed", "candidate", "state_po", "version", "office"],
        axis=1,
    )
    df = pd.get_dummies(df, columns=["state"])

    covar = df.drop("party_simplified", axis=1).astype("float").values
    labels = df["party_simplified"].astype("category").cat.codes.values
    return covar, labels


# Alternative registration methods, should only be used on ad-hoc basis
Register(
    "gaussian_classifier_high_dim", categorical=True, dataset_kwargs={"input_dim": 100}
).from_covar_label_func(gaussian_classifier)
"""Registers gaussian classifier, but the input_dim is changed."""

Register(
    "gaussian_only_zeroes", categorical=True, dataset_kwargs={"input_dim": 100}
).add_label_transform(np.zeros_like).from_covar_label_func(gaussian_classifier)
"""Adds a transform to gaussian classifier, such that the labels are all zero."""

Register("adult_csv", True).from_csv(Register.CACHE_DIR + "/adult/train.csv", [-1, -2])
"""NOTE below, data is not cleaned."""

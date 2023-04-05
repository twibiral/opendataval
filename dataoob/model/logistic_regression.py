import torch
import torch.nn as nn
import torch.nn.functional as F

from dataoob.model import BinaryClassifierNNMixin, ClassifierNNMixin


class LogisticRegression(ClassifierNNMixin):
    """Initialize LogisticRegression."""

    def __init__(self, input_dim: int, num_classes: int):
        super().__init__()

        self.input_dim = input_dim
        self.num_of_classes = num_classes

        self.linear = nn.Linear(self.input_dim, self.num_of_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass of Logistic Regression.

        Parameters
        ----------
        x : torch.Tensor
            Input tensor

        Returns
        -------
        torch.Tensor
            Output Tensor of logistic regression
        """
        x = self.linear(x)
        x = F.softmax(x, dim=1)
        return x


class BinaryLogisticRegression(BinaryClassifierNNMixin, LogisticRegression):
    """Initialize BinaryLogisticRegression. BinaryClassifierNNMixin defines `.fit()`."""

    def __init__(self, input_dim: int):
        super().__init__(input_dim, 2)

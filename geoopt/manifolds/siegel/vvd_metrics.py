from abc import ABC, abstractmethod
from enum import Enum
import torch


class SiegelMetricType(Enum):
    """Allowed types of metrics that Siegel manifolds support"""
    RIEMANNIAN = "riem"
    FINSLER_ONE = "fone"
    FINSLER_INFINITY = "finf"
    FINSLER_MINIMUM = "fmin"
    WEIGHTED_SUM = "wsum"

    @staticmethod
    def from_str(label):
        types = {t.value: t for t in list(SiegelMetricType)}
        return types[label]


class SiegelMetric(ABC):
    """
    Based on the vector-valued distance computed on Siegel spaces, different metric functions
    can be taken, which give raise to different distances that can be computed in the space.

    The vector-valued distance is given by :math:`v_i = log((1 + d_i) / (1 - d_i)), i = 1, ..., n`,
    with :math:`d_i` the eigenvalues of the crossratio matrix sorted in ascending order
    (d1 < d2 < ... < dn), and :math:`n = rank`.

    Parameters
    ----------
    rank : int
         Rank of the spaces. Only mandatory for Finsler distance of minimum entropy or weighted sum.
    """

    def __init__(self, rank: int = None):
        self.rank = rank

    @abstractmethod
    def compute_metric(self, v: torch.Tensor, keepdim=False) -> torch.Tensor:
        raise NotImplementedError

    @classmethod
    def get(cls, type_str: str, rank: int):
        metrics_map = {
            SiegelMetricType.RIEMANNIAN.value: RiemannianMetric,
            SiegelMetricType.FINSLER_ONE.value: FinslerOneMetric,
            SiegelMetricType.FINSLER_INFINITY.value: FinslerInfinityMetric,
            SiegelMetricType.FINSLER_MINIMUM.value: FinslerMinimumEntropyMetric,
            SiegelMetricType.WEIGHTED_SUM.value: FinslerWeightedSumMetric,
        }

        return metrics_map[type_str](rank)


class RiemannianMetric(SiegelMetric):

    def compute_metric(self, v: torch.Tensor, keepdim=False) -> torch.Tensor:
        r"""
        Riemannian distance: :math:`d(Z_1, Z_2) = \sqrt{\sum_{i=1}^n v_i^2}`

        Parameters
        ----------
        v : torch.Tensor
            Vector-valued distance
        keepdim : bool
            keep the last dim?

        Returns
        -------
        torch.Tensor
            Riemannian distance between the points
        """
        res = torch.norm(v, dim=-1, keepdim=keepdim)
        return res


class FinslerOneMetric(SiegelMetric):

    def compute_metric(self, v: torch.Tensor, keepdim=True) -> torch.Tensor:
        r"""
        Finsler One distance: :math:`d(Z_1, Z_2) = \sum_{i=1}^n v_i`

        Parameters
        ----------
        v : torch.Tensor
            Vector-valued distance
        keepdim : bool
            keep the last dim?

        Returns
        -------
        torch.Tensor
            Finsler One distance between the points
        """
        res = torch.sum(v, dim=-1, keepdim=keepdim)
        return res


class FinslerInfinityMetric(SiegelMetric):

    def compute_metric(self, v: torch.Tensor, keepdim=True) -> torch.Tensor:
        r"""
        Finsler Infinity distance: :math:`d(Z_1, Z_2) = \max \{v_i\}=v_n`

        Parameters
        ----------
        v : torch.Tensor
            Vector-valued distance
        keepdim : bool
            keep the last dim?

        Returns
        -------
        torch.Tensor
            Finsler Infinity distance between the points
        """
        res = v.select(dim=-1, index=-1)
        if keepdim:
            return res.unsqueeze(dim=-1)
        return res


class FinslerMinimumEntropyMetric(SiegelMetric):

    def __init__(self, rank: int):
        super().__init__(rank)
        if rank is None or rank < 2:
            raise ValueError("Parameter rank has to be >= 2")
        factor = 2
        self.weights = factor * (rank + 1 - torch.arange(start=rank + 1, end=1, step=-1).unsqueeze(0))

    def compute_metric(self, v: torch.Tensor, keepdim=True) -> torch.Tensor:
        r"""
        Finsler distance of minimum entropy: :math:`d(Z_1, Z_2) = \sum_{i=1}^n 2 * (n + 1 - i) * v_i`

        Parameters
        ----------
        v : torch.Tensor
            Vector-valued distance
        keepdim : bool
            keep the last dim?

        Returns
        -------
        torch.Tensor
            Finsler distance of minimum entropy between the points
        """
        res = torch.sum(self.weights * v, dim=-1, keepdim=keepdim)
        return res


class FinslerWeightedSumMetric(SiegelMetric, torch.nn.Module):

    def __init__(self, rank):
        torch.nn.Module.__init__(self)
        SiegelMetric.__init__(self, rank)
        if rank is None or rank < 2:
            raise ValueError("Parameter rank has to be >= 2")
        self.weights = torch.nn.parameter.Parameter(torch.ones((1, rank)))

    def compute_metric(self, v: torch.Tensor, keepdim=True) -> torch.Tensor:
        r"""
        Weighted sum of vector-valued distance: :math:`d(Z_1, Z_2) = \sum_{i=1}^n w_i * v_i`
        where :math:`w_i` is a learnable parameter

        Parameters
        ----------
        v : torch.Tensor
            Vector-valued distance
        keepdim : bool
            keep the last dim?

        Returns
        -------
        torch.Tensor
            Weighted sum of vector-valued distance between the points
        """
        weights = torch.relu(self.weights)    # 1 x n
        res = weights * v
        res = torch.sum(res, dim=-1, keepdim=keepdim)
        return res

"""Feature extraction module."""
import inspect

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.base import BaseEstimator
from sklearn.feature_selection import (
    RFE,
    SelectKBest,
    SequentialFeatureSelector,
    chi2,
    f_classif,
    mutual_info_classif,
)

EXTRACTION_DICT = {
    "chi2": chi2,
    "mutual_info": mutual_info_classif,
    "f_test": f_classif,
    "corr": lambda X_train, y_train: np.array(
        np.abs(pearsonr(X_train, y_train))[0]
    ),
}


class FeatureSelectionWrapper:
    """A class for performing feature selection on input datasets.

    The class allows for either filter-based or wrapper-based feature
    selection, depending on the specified method.

    Methods
    -------
    filter_feature_selection :
        Perform filter-based feature selection.
    wrapper_feature_selection :
        Perform wrapper-based feature selection.

    Parameters
    ----------
    method : str
        The method to use for feature selection.
        Currently supported methods are "chi2", "mutual_info", "f_test",
        "corr", "sequential", and "recursive".
    kwargs : dict
        Additional keyword arguments to pass to the selected feature selection
        method.

    Attributes
    ----------
    extractor : Callable
        The selected feature selection method.
    kwargs : dict
        Keyword arguments to pass to the selected feature selection method.

    Examples
    --------
    >>> estimator = RandomForestClassifier()
    >>> fs = FeatureSelectionWrapper(
            "sequential", estimator=estimator, num_features=2
        )
    >>> selected_features_train, _ = fs(X_train, X_test, y_train)
    >>> print("Selected features shape:", selected_features_train.shape)
    """

    def __init__(self, method: str, **kwargs) -> None:
        """Initialize the FE wrapper.

        Parameters
        ----------
        method : str
            FE method.
        kwargs
            FE kwargs.
        """
        if method.lower() in EXTRACTION_DICT.keys():
            self.extractor = self.filter_feature_selection
        elif method.lower() in ("sequential", "recursive"):
            self.method = method
            self.extractor = self.wrapper_feature_selection

        self.kwargs = kwargs

    def __call__(
        self,
        X_train: pd.DataFrame | np.ndarray,
        X_test: pd.DataFrame | np.ndarray,
        y_train: pd.Series | np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Call the FE wrapper.

        Parameters
        ----------
        X_train : pd.DataFrame | np.ndarray
            Training features.
        X_test : pd.DataFrame | np.ndarray
            Testing features.
        y_train : pd.Series | np.ndarray
            Training labels.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Extracted features.
        """
        extractor_params = inspect.signature(self.extractor).parameters
        extractor_kwargs = {
            k: v for k, v in self.kwargs.items() if k in extractor_params
        }
        return self.extractor(X_train, X_test, y_train, **extractor_kwargs)

    def filter_feature_selection(
        self,
        X_train: pd.DataFrame | np.ndarray,
        X_test: pd.DataFrame | np.ndarray,
        y_train: pd.Series | np.ndarray,
        method: str = "chi2",
        num_features: int | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Run filter-based feature selection on the training dataset.

        Evaluate features independent of the learning algorithm. Based on
        statistical tests, correlation, or information gain.

        Pros: Computationally efficient, independent of learning algorithm,
        easier to implement and understand.

        Cons: More suboptimal results, especially if features are highly
        correlated. Does not take into account interactions between features.

        Parameters
        ----------
        X_train : pd.DataFrame | np.ndarray
            Input training features.
        X_test : pd.DataFrame | np.ndarray
            Input testing features.
        y_train : pd.Series | np.ndarray
            Input training labels.
        method : str
            Statistical test to use.
        num_features : int, optional
            Number of features to select. If not specified, uses the square
            root of the number of training features.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            X_train and X_test containing only the selected features.
        """
        if not num_features:
            print(
                "`num_features` unspecified. Using sqrt(number of X_train"
                " features)."
            )
            num_features = int(np.sqrt(X_train.shape[1]))

        selector = SelectKBest(
            score_func=EXTRACTION_DICT[method], k=num_features
        )

        # try:
        selector.fit(X_train, y_train)
        # except ValueError:
        #     raise ValueError(
        #         "Input X must be non-negative. Are the data normalized "
        #         "correctly?"
        #     )
        selected_features_train = selector.transform(X_train)
        selected_features_test = selector.transform(X_test)
        return selected_features_train, selected_features_test

    def wrapper_feature_selection(
        self,
        X_train: pd.DataFrame | np.ndarray,
        X_test: pd.DataFrame | np.ndarray,
        y_train: pd.Series | np.ndarray,
        estimator: BaseEstimator,
        num_features: int,
        scoring: str | None = "f1",
    ) -> tuple[np.ndarray, np.ndarray]:
        """Run wrapper-based feature selection on the training dataset.

        Based on the performance of a learning algorithm. Train an algorithm
        on a different combination of features, and select the best-performing
        combination.

        Pros: Likely better performance, even if features are highly correlated
        or there is interaction between features.

        Cons: Learning algorithm dependent, so less versatile and more
        computationally expensive.

        Parameters
        ----------
        X_train : pd.DataFrame | np.ndarray
            Input training features.
        X_test : pd.DataFrame | np.ndarray
            Input testing features.
        y_train : pd.DataFrame | np.ndarray
            Input training labels.
        estimator : BaseEstimator
            The learning algorithm to use for feature selection.
        num_features : int
            The number of features to select.
        scoring : str, optional
            The scoring metric to use for feature selection, by default "f1".

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            X_train and X_test containing only the selected features.
        """
        if self.method == "sequential":
            selector = SequentialFeatureSelector(
                estimator=estimator,
                n_features_to_select=num_features,
                scoring=scoring,
                cv=None,
            )
        elif self.method == "recursive":
            selector = RFE(
                estimator=estimator,
                n_features_to_select=num_features,
                step=1,
            )
        else:
            raise ValueError(
                f"Unknown wrapper-based feature selection: {self.method}"
            )

        selector.fit(X_train, y_train)
        selected_features_train = selector.transform(X_train)
        selected_features_test = selector.transform(X_test)
        return selected_features_train, selected_features_test

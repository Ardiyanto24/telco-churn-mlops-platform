"""Versionable custom transformers for future Telco churn artifacts.

This module deliberately does not register classes in ``__main__``. Existing
legacy joblib artifacts still require their compatibility loader until the
artifact-contract milestone migrates them to this stable module path.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .constants import (
    ADDON_COLS,
    AUTO_PAYMENT_METHODS,
    BINARY_COLS,
    DROP_COLS,
    OHE_COLS,
    STRUCTURAL_COLS,
    TENURE_BINS,
    TENURE_LABELS,
)


class FeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.addon_cols = ADDON_COLS
        self.auto_methods = AUTO_PAYMENT_METHODS
        self.tenure_bins = TENURE_BINS
        self.tenure_labels = TENURE_LABELS

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        if "TotalCharges" in X.columns:
            total_charges = pd.to_numeric(X["TotalCharges"], errors="coerce")
            estimated_total = X["MonthlyCharges"] * X["tenure"]
            total_charges = total_charges.fillna(estimated_total)
            X["tc_residual"] = total_charges - estimated_total
            X["monthly_to_total_ratio"] = X["MonthlyCharges"] / (total_charges + 1e-6)

        if "tenure" in X.columns:
            X["tenure_group"] = pd.cut(
                X["tenure"],
                bins=self.tenure_bins,
                labels=self.tenure_labels,
                include_lowest=True,
            ).astype(str)

        if "PaymentMethod" in X.columns:
            X["is_auto_payment"] = X["PaymentMethod"].isin(self.auto_methods).astype(int)

        addon_present = [column for column in self.addon_cols if column in X.columns]
        if addon_present:
            X["service_count"] = X[addon_present].apply(
                lambda row: (row == "Yes").sum(), axis=1
            ).astype(int)

        if "service_count" in X.columns:
            X["has_any_addon"] = (X["service_count"] > 0).astype(int)
        return X


class ColumnDropper(BaseEstimator, TransformerMixin):
    def __init__(self, cols_to_drop=None):
        self.cols_to_drop = cols_to_drop or DROP_COLS

    def fit(self, X, y=None):
        self.cols_dropped_ = [column for column in self.cols_to_drop if column in X.columns]
        return self

    def transform(self, X):
        return X.drop(columns=self.cols_dropped_, errors="ignore")


class StructuralEncoder(BaseEstimator, TransformerMixin):
    STRUCTURAL_MAP = {"Yes": 1, "No": 0, "No internet service": -1, "No phone service": -1}

    def __init__(self, cols=None):
        self.cols = cols or STRUCTURAL_COLS

    def fit(self, X, y=None):
        self.cols_present_ = [column for column in self.cols if column in X.columns]
        return self

    def transform(self, X):
        X = X.copy()
        for column in self.cols_present_:
            X[column] = X[column].map(self.STRUCTURAL_MAP).fillna(X[column])
        return X


class BinaryEncoder(BaseEstimator, TransformerMixin):
    BINARY_MAP = {"Yes": 1, "No": 0}

    def __init__(self, cols=None):
        self.cols = cols or BINARY_COLS

    def fit(self, X, y=None):
        self.cols_present_ = [column for column in self.cols if column in X.columns]
        return self

    def transform(self, X):
        X = X.copy()
        for column in self.cols_present_:
            X[column] = X[column].map(self.BINARY_MAP).fillna(X[column])
        return X


class OHEWrapper(BaseEstimator, TransformerMixin):
    def __init__(self, cols=None):
        self.cols = cols or (OHE_COLS + ("tenure_group",))
        self._encoder = OneHotEncoder(
            drop="first", sparse_output=False, handle_unknown="ignore", dtype=np.float64
        )

    def fit(self, X, y=None):
        self.cols_present_ = [column for column in self.cols if column in X.columns]
        if self.cols_present_:
            self._encoder.fit(X[self.cols_present_])
            self.ohe_feature_names_ = self._encoder.get_feature_names_out(
                self.cols_present_
            ).tolist()
        return self

    def transform(self, X):
        X = X.copy()
        if not hasattr(self, "cols_present_") or not self.cols_present_:
            return X
        encoded = self._encoder.transform(X[self.cols_present_])
        encoded_frame = pd.DataFrame(
            encoded, columns=self.ohe_feature_names_, index=X.index
        )
        return pd.concat([X.drop(columns=self.cols_present_), encoded_frame], axis=1)


class ScalerWrapper(BaseEstimator, TransformerMixin):
    NUMERIC_TARGET_COLS = ("tenure", "MonthlyCharges", "tc_residual", "monthly_to_total_ratio")

    def __init__(self, cols=None):
        self.cols = cols or self.NUMERIC_TARGET_COLS
        self._scaler = StandardScaler()

    def fit(self, X, y=None):
        self.cols_present_ = [column for column in self.cols if column in X.columns]
        if self.cols_present_:
            self._scaler.fit(X[self.cols_present_])
        return self

    def transform(self, X):
        X = X.copy()
        if self.cols_present_:
            X[self.cols_present_] = self._scaler.transform(X[self.cols_present_])
        return X

    def get_feature_names_out(self, input_features=None):
        return input_features


class PreprocessingPipeline(BaseEstimator, TransformerMixin):
    def __init__(self):
        self.feature_engineer_ = FeatureEngineer()
        self.col_dropper_ = ColumnDropper()
        self.structural_encoder_ = StructuralEncoder(cols=STRUCTURAL_COLS)
        self.binary_encoder_ = BinaryEncoder()
        self.ohe_wrapper_ = OHEWrapper()
        self.scaler_wrapper_ = ScalerWrapper()
        self._steps = (
            self.feature_engineer_,
            self.col_dropper_,
            self.structural_encoder_,
            self.binary_encoder_,
            self.ohe_wrapper_,
            self.scaler_wrapper_,
        )

    def fit(self, X, y=None):
        transformed = X.copy()
        for step in self._steps:
            transformed = step.fit_transform(transformed, y)
        self._last_output_columns_ = transformed.columns.tolist()
        return self

    def transform(self, X):
        transformed = X.copy()
        for step in self._steps:
            transformed = step.transform(transformed)
        return transformed

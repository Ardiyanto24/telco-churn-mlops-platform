"""Feature metadata shared by training and serving code."""

ADDON_COLS = (
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
)
STRUCTURAL_COLS = ADDON_COLS + ("MultipleLines",)
BINARY_COLS = ("Partner", "Dependents", "PhoneService", "PaperlessBilling")
OHE_COLS = ("Contract", "InternetService", "PaymentMethod")
DROP_COLS = ("customerID", "id", "gender", "TotalCharges")
AUTO_PAYMENT_METHODS = ("Bank transfer (automatic)", "Credit card (automatic)")
TENURE_BINS = (0, 2, 18, 44, 72)
TENURE_LABELS = ("G1_0_2", "G2_2_18", "G3_18_44", "G4_44_72")

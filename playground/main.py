import mlflow
import mlflow.sklearn
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
import pandas as pd
import os 
os.environ["MLFLOW_TRACKING_URI"] = "http://localhost:5000"
EXPERIMENT_NAME="iris-random-forest-experiment"
mlflow.set_experiment(EXPERIMENT_NAME)
experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
print(f"Experiment ID: {experiment.experiment_id}")

mlflow.sklearn.autolog()

iris = load_iris()
X = pd.DataFrame(iris.data, columns=iris.feature_names)
y = pd.Series(iris.target, name="target")

# Split the dataset into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

# Define model hyperparameters
n_estimators = 100
max_depth = 5
random_state = 42

# Start an MLflow run
with mlflow.start_run(run_name="RandomForest_Iris") as run:
    # Log model parameters
    mlflow.log_param("n_estimators", n_estimators)
    mlflow.log_param("max_depth", max_depth)
    mlflow.log_param("random_state", random_state)

    # Initialize and train the Random Forest classifier
    clf = RandomForestClassifier(
        n_estimators=n_estimators, max_depth=max_depth, random_state=random_state
    )
    clf.fit(X_train, y_train)

    # Make predictions on the test set
    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)

    # Calculate evaluation metrics
    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_proba, multi_class='ovr')

    # Log metrics
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("roc_auc", roc_auc)

    # Log the trained model
    mlflow.sklearn.log_model(clf, "random_forest_model")

    print(f"Run ID: {run.info.run_id}")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"ROC AUC: {roc_auc:.4f}")

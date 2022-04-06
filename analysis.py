from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sn
import numpy as np
import pickle
import random

"""

"""

#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'

N_ESTIMATORS = 11  # The amount of trees (default 101 [keep at an odd number])
MAX_DEPTH = 9  # Depth of the decision trees (default 10)
RANDOM_STATE = 1  # Random seed (default 1)
random.seed(RANDOM_STATE)
TEST_SIZE = 0.2


def load_data(TEST_SIZE):
    X, y = None, None
    with open("/media/sf_Desktop/X_Undersampled.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("/media/sf_Desktop/y_Undersampled.pkl", "rb") as fp:
        y = pickle.load(fp)
    assert X is not None and y is not None
    assert len(X) == len(y)
    print("Dataset of " + str(len(X)) + " samples loaded from disk.")

    #  Split the data up traditionally into 80% training and 20% training
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, shuffle=True)
    print("Dataset split into training and testing.")
    return X_train, X_test, y_train, y_test


def random_forest(X_train, X_test, y_train, y_test):
    model = RandomForestClassifier(n_estimators=N_ESTIMATORS, max_depth=MAX_DEPTH, random_state=RANDOM_STATE)
    #  Train the model
    in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)
    print("\n" + GREEN + "Random Forest feature importance:" + END)
    important_features = {}
    for idx, importance in enumerate(model.feature_importances_, start=0):
        if importance >= 0.005:
            important_features[X_train.columns[idx]] = importance

    sorted_feat = sorted(important_features.items(), key=lambda x: x[1], reverse=True)
    for item in sorted_feat:
        print(GREEN + "{:83s} {:.5f}".format(item[0], item[1]) + END)

    print("\nIn Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)

    # Metrics
    y_predicted = model.predict(X_test)
    confusion_mtx(y_test, y_predicted)


def gradient_boosted(X_train, X_test, y_train, y_test):
    model = GradientBoostingClassifier(n_estimators=100, learning_rate=1.0, max_depth=1, random_state=RANDOM_STATE).fit(X_train, y_train)
    #  Train the model
    in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)
    print("\nIn Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)

    # Metrics
    y_predicted = model.predict(X_test)
    confusion_mtx(y_test, y_predicted)


def confusion_mtx(y_test, y_predicted):
    cm = confusion_matrix(y_test, y_predicted)
    print("\nConfusion Matrix for Test Set: \n" + str(cm))
    #  Heat map
    plt.figure(figsize=(10, 7))
    sn.heatmap(cm, annot=True)
    plt.xlabel('Predicted')
    plt.ylabel('Truth')
    plt.show()

    cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    #print("\nConfusion Matrix for Class Accuracy Probabilities: \n" + str(cm))
    #  Heat map
    plt.figure(figsize=(10, 7))
    sn.heatmap(cm, annot=True)
    plt.xlabel('Predicted')
    plt.ylabel('Truth')
    plt.show()


def main():
    X_train, X_test, y_train, y_test = load_data(0.2)
    print("Training random forest.")
    random_forest(X_train, X_test, y_train, y_test)
    print("Training gradient boosted classifier.")
    gradient_boosted(X_train, X_test, y_train, y_test)


if __name__ == '__main__':
    main()

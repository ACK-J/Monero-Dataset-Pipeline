from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import pickle

"""

"""

#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'

N_ESTIMATORS = 11  # The amount of trees (default 101 [keep at an odd number])
MAX_DEPTH = 7  # Depth of the decision trees (default 10)
RANDOM_STATE = 1  # Random seed (default 1)
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
    print("Model feature importance:")
    for idx, importance in enumerate(model.feature_importances_, start=0):
        if importance >= 0.005:
            print(GREEN + "{:20}\t{:.10f}".format(X_train.columns[idx], importance) + END)
        # else:
        #     print("{:20}\t{:.10f}".format(X_train.columns[idx], importance))
    print("In Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)


def main():
    X_train, X_test, y_train, y_test = load_data(0.2)
    print("Training random forest.")
    random_forest(X_train, X_test, y_train, y_test)


if __name__ == '__main__':
    main()

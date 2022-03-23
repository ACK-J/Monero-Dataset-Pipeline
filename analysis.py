from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import pickle
from collections import Counter


#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'

N_ESTIMATORS = 3  # The amount of trees (default 101 [keep at an odd number])
MAX_DEPTH = 5  # Depth of the decision trees (default 10)
RANDOM_STATE = 1  # Random seed (default 1)
TEST_SIZE = 0.2


def undersample(X, y):
    labels_distribution = Counter(y)
    min_occurrences = None
    for label in labels_distribution:
        num_occurrences = labels_distribution[label]
        if min_occurrences is None:
            min_occurrences = num_occurrences
        elif num_occurrences < min_occurrences:
            min_occurrences = num_occurrences



def load_data(TEST_SIZE):
    with open("X.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("y.pkl", "rb") as fp:
        y = pickle.load(fp)

    #  Only get the label we need
    true_spend = []
    for record in y:
        true_spend.append(int(record['Ring_no/Ring_size'].split("/")[0]))

    #  Split the data up traditionally into 80% training and 20% training
    X_train, X_test, y_train, y_test = train_test_split(X, true_spend, test_size=TEST_SIZE)
    return X_train, X_test, y_train, y_test


def main():
    X_train, X_test, y_train, y_test = load_data(0.2)
    model = RandomForestClassifier(n_estimators=N_ESTIMATORS, max_depth=MAX_DEPTH, random_state=RANDOM_STATE)
    #  Train the model
    in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)
    print("In Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)


    print("Model feature importance:")
    for idx, importance in enumerate(model.feature_importances_, start=0):
        if importance >= 0.05:
            print(GREEN + "{:20}\t{:.10f}".format(X_train.columns[idx], importance) + END)
        else:
            print("{:20}\t{:.10f}".format(X_train.columns[idx], importance))


if __name__ == '__main__':
    main()

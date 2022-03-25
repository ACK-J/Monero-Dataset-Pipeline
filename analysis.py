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
    X.reset_index(drop=True, inplace=True)
    labels_distribution = Counter(y)
    min_occurrences = labels_distribution.most_common()[len(labels_distribution)-1][1]
    #max_occurrences = labels_distribution.most_common(1)[0][1]
    occurrences = {}
    need_to_delete_y = []
    for i in range(len(labels_distribution)):
        occurrences[i+1] = 0
    for idx, val in enumerate(y):
        if occurrences[val] < min_occurrences:
            occurrences[val] = occurrences[val] + 1
        else:
            X.drop(idx, inplace=True)
            need_to_delete_y.append(idx)
    labels = [i for j, i in enumerate(y) if j not in need_to_delete_y]
    X.reset_index(drop=True, inplace=True)
    return X, labels


def load_data(TEST_SIZE):
    with open("X.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("y.pkl", "rb") as fp:
        y = pickle.load(fp)

    #  Only get the label we need
    true_spend = []
    for record in y:
        true_spend.append(int(record['Ring_no/Ring_size'].split("/")[0]))

    X.drop(['Time_Of_Enrichment'], axis='columns', inplace=True)
    X.drop(['Block_Number'], axis='columns', inplace=True)
    X.drop(['Block_Timestamp_Epoch'], axis='columns', inplace=True)
    X, y = undersample(X, true_spend)

    #  Split the data up traditionally into 80% training and 20% training
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE)
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
        if importance >= 0.01:
            print(GREEN + "{:20}\t{:.10f}".format(X_train.columns[idx], importance) + END)
        else:
            print("{:20}\t{:.10f}".format(X_train.columns[idx], importance))


if __name__ == '__main__':
    main()

from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sn
import numpy as np
import pickle
import random
from DataScience import NeuralNetwork
from DataScience import GradientBoostedClassifier
from DataScience import RandomForest
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


def load_data(TEST_SIZE, X_FILE, Y_FILE):
    X, y = None, None
    with open(X_FILE, "rb") as fp:
        X = pickle.load(fp)
    with open(Y_FILE, "rb") as fp:
        y = pickle.load(fp)
    assert X is not None and y is not None
    assert len(X) == len(y)
    print("Dataset of " + str(len(X)) + " samples loaded from disk.")
    #feature_dist_per_label(X,y)

    if TEST_SIZE != 0:
        #  Split the data up traditionally into 80% training and 20% training
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, shuffle=True)
        print("Dataset split into training and testing.")
        return X_train, X_test, y_train, y_test
    else:
        return X, None, y, None


def confusion_mtx(y_test, y_pred):
    cm = confusion_matrix(y_test, y_pred)
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

    # https://towardsdatascience.com/confusion-matrix-for-your-multi-class-machine-learning-model-ff9aa3bf7826
    # importing accuracy_score, precision_score, recall_score, f1_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    print('\nAccuracy: {:.2f}\n'.format(accuracy_score(y_test, y_pred)))

    print('Micro Precision: {:.2f}'.format(precision_score(y_test, y_pred, average='micro')))
    print('Micro Recall: {:.2f}'.format(recall_score(y_test, y_pred, average='micro')))
    print('Micro F1-score: {:.2f}\n'.format(f1_score(y_test, y_pred, average='micro')))

    print('Macro Precision: {:.2f}'.format(precision_score(y_test, y_pred, average='macro')))
    print('Macro Recall: {:.2f}'.format(recall_score(y_test, y_pred, average='macro')))
    print('Macro F1-score: {:.2f}\n'.format(f1_score(y_test, y_pred, average='macro')))

    print('Weighted Precision: {:.2f}'.format(precision_score(y_test, y_pred, average='weighted')))
    print('Weighted Recall: {:.2f}'.format(recall_score(y_test, y_pred, average='weighted')))
    print('Weighted F1-score: {:.2f}'.format(f1_score(y_test, y_pred, average='weighted')))

    from sklearn.metrics import classification_report
    print('\nClassification Report\n')
    print(classification_report(y_test, y_pred))


def main():
    X_train, X_test, y_train, y_test = load_data(0.2, "../StagenetDataset/X_Undersampled.pkl", "../StagenetDataset/y_Undersampled.pkl")
    X_train_mainnet, _, y_train_mainnet, _ = load_data(0, "../MainnetDataset/X_Undersampled.pkl", "../MainnetDataset/y_Undersampled.pkl")

    GradientBoostedClassifier.gradient_boosted(X_train, X_test, y_train, y_test, RANDOM_STATE, X_train_mainnet, y_train_mainnet)
    NeuralNetwork.MLP(X_train, X_test, y_train, y_test, X_train_mainnet, y_train_mainnet)


    # print("Training random forest.")
    # random_forest(X_train, X_test, y_train, y_test)
    # print("Training gradient boosted classifier.")
    # gradient_boosted(X_train, X_test, y_train, y_test)
    #MLP(X_train, X_test, y_train, y_test)

    #xgboost_classifier(X_train, X_test, y_train, y_test)


if __name__ == '__main__':
    main()

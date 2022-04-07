from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import confusion_matrix
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import seaborn as sn
from xgboost import XGBClassifier
import xgboost as xgb
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
    # lr_list = [0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1]
    #
    # for learning_rate in lr_list:
    #     gb_clf = GradientBoostingClassifier(n_estimators=20, learning_rate=learning_rate, max_features=2, max_depth=2, random_state=0)
    #     gb_clf.fit(X_train, y_train)
    #
    #     print("Learning rate: ", learning_rate)
    #     print("Accuracy score (training): {0:.3f}".format(gb_clf.score(X_train, y_train)))
    #     print("Accuracy score (validation): {0:.3f}".format(gb_clf.score(X_test, y_test)))


    # model = GradientBoostingClassifier(n_estimators=100, learning_rate=.3, max_depth=2, random_state=RANDOM_STATE).fit(X_train, y_train)
    # #  Train the model
    # in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)

    with open("gradient_boosted.pkl", "rb") as fp:
        model = pickle.load(fp)

    in_sample_accuracy = model.score(X_train, y_train)
    print("\nIn Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)

    # Metrics
    y_predicted = model.predict(X_test)
    confusion_mtx(y_test, y_predicted)


def xgboost_classifier(X_train, X_test, y_train, y_test):
    # print("Normalizing data...")
    # scaler = MinMaxScaler()
    # X_train = scaler.fit_transform(X_train)
    # X_test = scaler.transform(X_test)
    X_train =  X_train.drop(['Tx_Version'], axis=1)
    X_test =  X_test.drop(['Tx_Version'], axis=1)
    #
    # dtrain = xgb.DMatrix(X_train, label=y_train)
    # dtest = xgb.DMatrix(X_test, label=y_test)
    # param = {'nthread': 4}
    # num_round = 10
    # bst = xgb.train(param, dtrain, num_round)
    #
    # import numpy as np
    #
    # xgb.plot_importance(bst)
    # xgb.plot_tree(bst, num_trees=2)
    # ypred = np.rint(bst.predict(dtest))
    # confusion_mtx(y_test, ypred)

    xgb_clf = XGBClassifier(n_estimators=100, learning_rate=0.3, n_jobs=4, random_state=RANDOM_STATE)
    xgb_clf.fit(X_train, y_train, eval_set=[(X_train, y_train), (X_test, y_test)], eval_metric='logloss', verbose=True)
    evals_result = xgb_clf.evals_result()
    print(evals_result)

    score = xgb_clf.score(y_train, y_test)
    predictions = xgb_clf.predict(X_test)
    xgb.plot_importance(xgb_clf)

    print(score)


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
    X_train, X_test, y_train, y_test = load_data(0.2)
    print("Training random forest.")
    random_forest(X_train, X_test, y_train, y_test)
    # print("Training gradient boosted classifier.")
    # gradient_boosted(X_train, X_test, y_train, y_test)

    #xgboost_classifier(X_train, X_test, y_train, y_test)


if __name__ == '__main__':
    main()

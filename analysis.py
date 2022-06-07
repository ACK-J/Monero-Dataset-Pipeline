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
    with open("./X_Undersampled.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("./y_Undersampled.pkl", "rb") as fp:
        y = pickle.load(fp)
    assert X is not None and y is not None
    assert len(X) == len(y)
    print("Dataset of " + str(len(X)) + " samples loaded from disk.")
    #feature_dist_per_label(X,y)

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

    #  Train the model
    X_test = X_test.drop(['Tx_Version'], axis=1)
    X_test = X_test.drop(['xmr2csv_Data_Collection_Time'], axis=1)
    X_test = X_test.drop(['Block_To_xmr2csv_Time_Delta'], axis=1)
    X_test = X_test.drop(['Num_Confirmations'], axis=1)

    X_train = X_train.drop(['Tx_Version'], axis=1)
    X_train = X_train.drop(['xmr2csv_Data_Collection_Time'], axis=1)
    X_train = X_train.drop(['Block_To_xmr2csv_Time_Delta'], axis=1)
    X_train = X_train.drop(['Num_Confirmations'], axis=1)

    # for n in [10,50,100,200,300,500]:
    #     for lr in [.01, .1, .3, .5]:
    #             model = GradientBoostingClassifier(n_estimators=n, learning_rate=lr, random_state=RANDOM_STATE).fit(X_train, y_train)
    #             print("\n\n\nLR = ", lr, " Num Est = ", n)
    #             in_sample_accuracy = model.score(X_train, y_train)
    #             print("In Sample Accuracy:", in_sample_accuracy)
    #             test_accuracy = model.score(X_test, y_test)
    #             print("Test Accuracy:", test_accuracy)
    # exit()

    model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.1, random_state=RANDOM_STATE).fit(X_train, y_train)
    in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)

    with open("gradient_boosted_new.pkl", "wb") as fp:
        pickle.dump(model, fp)

    # with open("gradient_boosted.pkl", "rb") as fp:
    #     model = pickle.load(fp)

    in_sample_accuracy = model.score(X_train, y_train)
    print("\nIn Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)

    print("\n" + GREEN + "Gradient Boosted Classifier feature importance:" + END)
    important_features = {}
    for idx, importance in enumerate(model.feature_importances_):
        if importance >= 0.005:
            important_features[X_train.columns[idx]] = importance

    sorted_feat = sorted(important_features.items(), key=lambda x: x[1], reverse=True)
    for item in sorted_feat:
        print(GREEN + "{:83s} {:.5f}".format(item[0], item[1]) + END)

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


def feature_dist_per_label(X, y):
    decoys = {
        0:0,
        1:0,
        2:0,
        3:0,
        4:0,
        5:0,
        6:0,
        7:0,
        8:0,
        9:0,
        10:0
    }
    decoys_counts = {
        0:0,
        1:0,
        2:0,
        3:0,
        4:0,
        5:0,
        6:0,
        7:0,
        8:0,
        9:0,
        10:0
    }
    true = {
        0:0,
        1:0,
        2:0,
        3:0,
        4:0,
        5:0,
        6:0,
        7:0,
        8:0,
        9:0,
        10:0
    }
    true_counts = {
        0:0,
        1:0,
        2:0,
        3:0,
        4:0,
        5:0,
        6:0,
        7:0,
        8:0,
        9:0,
        10:0
    }
    new_X = X.to_dict('index')
    del X
    for y_idx in range(len(new_X)):
        tx = new_X[y_idx]
        true_spend = y[y_idx]
        base = tx["Inputs.0.Time_Delta_From_Newest_Ring_To_Block"]
        zero_to_one = tx["Inputs.0.Time_Deltas_Between_Ring_Members.0_1"]
        one_to_two = tx["Inputs.0.Time_Deltas_Between_Ring_Members.1_2"]
        two_to_three = tx["Inputs.0.Time_Deltas_Between_Ring_Members.2_3"]
        three_to_four = tx["Inputs.0.Time_Deltas_Between_Ring_Members.3_4"]
        four_to_five = tx["Inputs.0.Time_Deltas_Between_Ring_Members.4_5"]
        five_to_six = tx["Inputs.0.Time_Deltas_Between_Ring_Members.5_6"]
        six_to_seven = tx["Inputs.0.Time_Deltas_Between_Ring_Members.6_7"]
        seven_to_eight = tx["Inputs.0.Time_Deltas_Between_Ring_Members.7_8"]
        eight_to_nine = tx["Inputs.0.Time_Deltas_Between_Ring_Members.8_9"]
        nine_to_ten = tx["Inputs.0.Time_Deltas_Between_Ring_Members.9_10"]
        if true_spend == 1:
            true[0] += base
            true_counts[0] += 1
        elif true_spend != 1:
            decoys[0] += base
            decoys_counts[0] += 1

        if true_spend == 2:
            true[1] += base + zero_to_one
            true_counts[1] += 1
        elif true_spend != 2:
            decoys[1] += base + zero_to_one
            decoys_counts[1] += 1

        if true_spend == 3:
            true[2] += base + zero_to_one + one_to_two
            true_counts[2] += 1
        elif true_spend != 3:
            decoys[2] += base + zero_to_one + one_to_two
            decoys_counts[2] += 1

        if true_spend == 4:
            true[3] += base + zero_to_one + one_to_two + two_to_three
            true_counts[3] += 1
        elif true_spend != 4:
            decoys[3] += base + zero_to_one + one_to_two + two_to_three
            decoys_counts[3] += 1

        if true_spend == 5:
            true[4] += base + zero_to_one + one_to_two + two_to_three + three_to_four
            true_counts[4] += 1
        elif true_spend != 5:
            decoys[4] += base + zero_to_one + one_to_two + two_to_three + three_to_four
            decoys_counts[4] += 1

        if true_spend == 6:
            true[5] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five
            true_counts[5] += 1
        elif true_spend != 6:
            decoys[5] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five
            decoys_counts[5] += 1

        if true_spend == 7:
            true[6] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six
            true_counts[6] += 1
        elif true_spend != 7:
            decoys[6] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six
            decoys_counts[6] += 1

        if true_spend == 8:
            true[7] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven
            true_counts[7] += 1
        elif true_spend != 8:
            decoys[7] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven
            decoys_counts[7] += 1

        if true_spend == 9:
            true[8] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven + seven_to_eight
            true_counts[8] += 1
        elif true_spend != 9:
            decoys[8] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven + seven_to_eight
            decoys_counts[8] += 1

        if true_spend == 10:
            true[9] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven + seven_to_eight + eight_to_nine
            true_counts[9] += 1
        elif true_spend != 10:
            decoys[9] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven + seven_to_eight + eight_to_nine
            decoys_counts[9] += 1

        if true_spend == 11:
            true[10] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven + seven_to_eight + eight_to_nine + nine_to_ten
            true_counts[10] += 1
        elif true_spend != 11:
            decoys[10] += base + zero_to_one + one_to_two + two_to_three + three_to_four + four_to_five + five_to_six + six_to_seven + seven_to_eight + eight_to_nine + nine_to_ten
            decoys_counts[10] += 1
    print(true)
    print(true_counts)
    print(decoys)
    print(decoys_counts)

def MLP(X_train, X_test, y_train, y_test):
    import tensorflow as tf
    from keras.models import Sequential
    from keras.layers import Dense, Activation, Dropout
    from sklearn.preprocessing import StandardScaler
    from keras.utils import np_utils
    from sklearn.model_selection import cross_val_score
    from sklearn.model_selection import KFold

    y_test = np.asarray(y_test)
    y_train = np.asarray(y_train)
    y_test = np_utils.to_categorical(y_test)
    y_train = np_utils.to_categorical(y_train)
    y_test = np.delete(y_test, 0, 1)
    y_train = np.delete(y_train, 0, 1)

    scaler = StandardScaler().fit(X_train)
    X_train = scaler.transform(X_train)
    X_test = scaler.transform(X_test)

    from keras_visualizer import visualizer
    model = Sequential()
    model.add(Dense(11, input_shape=(X_train.shape[1],), activation='relu'))
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(.1))
    model.add(Dense(64, activation='relu'))
    model.add(Dense(128, activation='relu'))
    model.add(Dense(64, activation='relu'))
    model.add(Dropout(.3))
    model.add(Dense(32, activation='relu'))
    model.add(Dropout(.2))
    model.add(Dense(11))
    model.add(Activation('softmax'))
    model.summary()
    # https://towardsdatascience.com/visualizing-keras-models-4d0063c8805e
    visualizer(model, format='png', view=True)

    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    model.fit(X_train, y_train, epochs=100, batch_size=1)
    y_pred = model.predict(X_test)
    score = model.evaluate(X_test, y_test, verbose=1)
    print(score[1])
    kfold = KFold(n_splits=10, shuffle=True)
    results = cross_val_score(model, X_test, y_test, cv=kfold)
    print("Baseline: %.2f%% (%.2f%%)" % (results.mean() * 100, results.std() * 100))

def main():
    X_train, X_test, y_train, y_test = load_data(0.2)
    # print("Training random forest.")
    # random_forest(X_train, X_test, y_train, y_test)
    # print("Training gradient boosted classifier.")
    # gradient_boosted(X_train, X_test, y_train, y_test)
    MLP(X_train, X_test, y_train, y_test)

    #xgboost_classifier(X_train, X_test, y_train, y_test)


if __name__ == '__main__':
    main()

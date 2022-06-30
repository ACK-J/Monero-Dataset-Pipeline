from xgboost import XGBClassifier
import xgboost as xgb
from sklearn.ensemble import GradientBoostingClassifier
from DataScience.analysis import confusion_mtx
import pickle

#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'


def gradient_boosted(X_train, X_test, y_train, y_test, RANDOM_STATE, X_Validation, y_Validation):

    # for n in [10,50,100,200,300,500]:
    #     for lr in [.01, .1, .3, .5]:
    #             model = GradientBoostingClassifier(n_estimators=n, learning_rate=lr, random_state=RANDOM_STATE).fit(X_train, y_train)
    #             print("\n\n\nLR = ", lr, " Num Est = ", n)
    #             in_sample_accuracy = model.score(X_train, y_train)
    #             print("In Sample Accuracy:", in_sample_accuracy)
    #             test_accuracy = model.score(X_test, y_test)
    #             print("Test Accuracy:", test_accuracy)
    # exit()

    # model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.1, random_state=RANDOM_STATE).fit(X_train, y_train)
    # in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)
    #
    # with open("gradient_boosted.pkl", "wb") as fp:
    #     pickle.dump(model, fp)

    with open("gradient_boosted.pkl", "rb") as fp:
        model = pickle.load(fp)
    in_sample_accuracy = model.score(X_train, y_train)

    out_sample_accuracy = model.score(X_Validation, y_Validation)
    print("\nIn Sample Accuracy:", in_sample_accuracy)
    test_accuracy = model.score(X_test, y_test)
    print("Test Accuracy:", test_accuracy)
    print("Mainnet Validation Accuracy:", out_sample_accuracy)

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

    y_main_predict = model.predict(X_Validation)
    print(y_main_predict)
    from collections import Counter
    print(Counter(y_main_predict))
    print(y_Validation)
    print(Counter(y_Validation))
    confusion_mtx(y_Validation, y_main_predict)


def xgboost_classifier(X_train, X_test, y_train, y_test, RANDOM_STATE):
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
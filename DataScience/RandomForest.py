from sklearn.ensemble import AdaBoostClassifier
from analysis import confusion_mtx
from sklearn.metrics import f1_score
from statistics import stdev
#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'


def random_forest(X_train, X_test, y_train, y_test, N_ESTIMATORS, MAX_DEPTH, RANDOM_STATE, X_Validation, y_Validation):
    out_of_sample_f1 = []
    mainnet_f1 = []
    for i in range(10):
        RANDOM_STATE += 1
        model = AdaBoostClassifier(n_estimators=N_ESTIMATORS, random_state=RANDOM_STATE)
        #  Train the model
        in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)

        # Feature Importance
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

        # # Metrics
        # y_predicted = model.predict(X_test)
        # confusion_mtx(y_test, y_predicted)
        #
        # y_predicted = model.predict(X_val_mainnet)
        # confusion_mtx(y_val_mainnet, y_predicted)

        # Metrics
        print("GBC Metrics ")
        y_pred = model.predict(X_test)
        weighted_f1 = f1_score(y_test, y_pred, average='weighted')
        print('Weighted F1-score: {:.2f}'.format(weighted_f1))
        out_of_sample_f1.append(weighted_f1)

        y_main_predict = model.predict(X_Validation)
        weighted_f1_mainnet = f1_score(y_Validation, y_main_predict, average='weighted')
        print('Mainnet Weighted F1-score: {:.2f}'.format(weighted_f1_mainnet))
        mainnet_f1.append(weighted_f1_mainnet)

    # Stats
    mean = sum(out_of_sample_f1) / len(out_of_sample_f1)
    standard_dev = stdev(out_of_sample_f1)

    main_mean = sum(mainnet_f1) / len(mainnet_f1)
    main_standard_dev = stdev(mainnet_f1)
    print(out_of_sample_f1)
    print(mainnet_f1)

    return mean*100, standard_dev*100, main_mean*100, main_standard_dev*100
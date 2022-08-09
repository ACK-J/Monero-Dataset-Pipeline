from sklearn.ensemble import GradientBoostingClassifier
import pickle
from statistics import stdev
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sn
from sklearn.metrics import f1_score

#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'


def gradient_boosted(X_train, X_test, y_train, y_test, RANDOM_STATE, X_Validation, y_Validation, stagenet=True):
    print("GRADIENT BOOSTED CLASSIFIER:")
    NUM_ESTIMATORS = 100
    LR = 0.1
    depth = 5
    out_of_sample_f1 = []
    mainnet_f1 = []
    #  Train the model 10 times to get the std dev
    for i in range(10):
        RANDOM_STATE += 1
        model = GradientBoostingClassifier(n_estimators=NUM_ESTIMATORS, learning_rate=LR, random_state=RANDOM_STATE, max_depth=depth).fit(X_train, y_train)
        model.fit(X_train, y_train)

        if stagenet:
            with open("./models/GBC/stagenet/num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_i_" + str(i) + "_seed_" + str(RANDOM_STATE) + ".pkl", "wb") as fp:
                pickle.dump(model, fp)
        else:
            with open("./models/GBC/testnet/num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_i_" + str(i) + "_seed_" + str(RANDOM_STATE) + ".pkl", "wb") as fp:
                pickle.dump(model, fp)
        print("num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_depth_" + str(depth) + "_RANDOM_" + str(RANDOM_STATE))
        in_sample_accuracy = model.score(X_train, y_train)
        print("\nIn Sample Accuracy:", in_sample_accuracy)
        test_accuracy = model.score(X_test, y_test)
        print("Test Accuracy:", test_accuracy)
        mainnet_accuracy = model.score(X_Validation, y_Validation)
        print("Mainnet Validation Accuracy:", mainnet_accuracy)

        # Feature Importance
        print("\n" + GREEN + "Gradient Boosted Classifier feature importance:" + END)
        important_features = {}
        for idx, importance in enumerate(model.feature_importances_):
            if importance >= 0.005:
                important_features[X_train.columns[idx]] = importance
        sorted_feat = sorted(important_features.items(), key=lambda x: x[1], reverse=True)
        for item in sorted_feat:
            print(GREEN + "{:83s} {:.5f}".format(item[0], item[1]) + END)

        # Metrics
        print("GBC Metrics ")
        y_pred = model.predict(X_test)
        weighted_f1 = f1_score(y_test, y_pred, average='weighted')
        print('Weighted F1-score: {:.2f}'.format(weighted_f1))
        out_of_sample_f1.append(weighted_f1)

        if stagenet:
            cm = confusion_matrix(y_test, y_pred)
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/GBC/stagenet/CM_num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_i_" + str(i) + "_seed_" + str(RANDOM_STATE) + ".png")
        else:
            cm = confusion_matrix(y_test, y_pred)
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/GBC/testnet/CM_num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_i_" + str(i) + "_seed_" + str(RANDOM_STATE) + ".png")

        y_main_predict = model.predict(X_Validation)
        weighted_f1_mainnet = f1_score(y_Validation, y_main_predict, average='weighted')
        print('Mainnet Weighted F1-score: {:.2f}'.format(weighted_f1_mainnet))
        mainnet_f1.append(weighted_f1_mainnet)

        if stagenet:
            cm = confusion_matrix(y_Validation, y_main_predict)
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/GBC/stagenet/Main_CM_num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_i_" + str(i) + "_seed_" + str(RANDOM_STATE) + ".png")
        else:
            cm = confusion_matrix(y_Validation, y_main_predict)
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/GBC/testnet/Main_CM_num_estimators_" + str(NUM_ESTIMATORS) + "_lr_" + str(LR) + "_i_" + str(i) + "_seed_" + str(RANDOM_STATE) + ".png")

    # Stats
    mean = sum(out_of_sample_f1) / len(out_of_sample_f1)
    standard_dev = stdev(out_of_sample_f1)

    main_mean = sum(mainnet_f1) / len(mainnet_f1)
    main_standard_dev = stdev(mainnet_f1)
    print(out_of_sample_f1)
    print(mainnet_f1)

    return mean*100, standard_dev*100, main_mean*100, main_standard_dev*100


def gradient_boosted_hyper_param_tuning(X_train, X_test, y_train, y_test, RANDOM_STATE):
    print("GRADIENT BOOSTED CLASSIFIER:")
    NUM_ESTIMATORS = 10#100
    LR = 0.1
    out_of_sample_f1 = []
    mainnet_f1 = []
    #  Train the model 10 times to get the std dev
    for estimator in (11, 33, 101):
        for lr in (.25, 0.1, 0.05):
            for depth in (3,11):
                model = GradientBoostingClassifier(n_estimators=estimator, learning_rate=lr, random_state=RANDOM_STATE, max_depth=depth).fit(X_train, y_train)
                model.fit(X_train, y_train)

                with open("./models/GBC/hyper_param_tuning/num_estimators_" + str(estimator) + "_lr_" + str(lr) + "_depth_" + str(depth) + ".pkl", "wb") as fp:
                    pickle.dump(model, fp)
                print("num_estimators_" + str(estimator) + "_lr_" + str(lr) + "_depth_" + str(depth))
                in_sample_accuracy = model.score(X_train, y_train)
                print("\nIn Sample Accuracy:", in_sample_accuracy)
                test_accuracy = model.score(X_test, y_test)
                print("Test Accuracy:", test_accuracy)

                # Metrics
                print("GBC Metrics")
                y_pred = model.predict(X_test)
                weighted_f1 = f1_score(y_test, y_pred, average='weighted')
                print('Weighted F1-score: {:.2f}'.format(weighted_f1))
                out_of_sample_f1.append(weighted_f1)
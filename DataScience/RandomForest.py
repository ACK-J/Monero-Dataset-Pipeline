from sklearn.ensemble import AdaBoostClassifier
from analysis import confusion_mtx
from sklearn.metrics import f1_score
from sklearn.metrics import confusion_matrix
from statistics import stdev
import seaborn as sn
from tqdm import tqdm
from multiprocessing import cpu_count, Manager
import pickle
from itertools import repeat
import matplotlib.pyplot as plt
import numpy as np
#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'

stagenet=True
LR = .25
N_ESTIMATORS = 700


def run_model_rf(X_train, X_test, y_train, y_test, RANDOM_STATE, X_Validation, y_Validation):
    global stagenet
    model = AdaBoostClassifier(n_estimators=N_ESTIMATORS, random_state=RANDOM_STATE, learning_rate=LR)
    #  Train the model
    in_sample_accuracy = model.fit(X_train, y_train).score(X_train, y_train)

    if stagenet:
        with open("./models/RF/stagenet/num_estimators_" + str(N_ESTIMATORS)  + "_seed_" + str(RANDOM_STATE) + ".pkl", "wb") as fp:
            pickle.dump(model, fp)
    else:
        with open("./models/RF/testnet/num_estimators_" + str(N_ESTIMATORS)  + "_seed_" + str(RANDOM_STATE) + ".pkl", "wb") as fp:
            pickle.dump(model, fp)

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

    # Metrics
    print("Random Forest Metrics ")
    y_pred = model.predict(X_test)
    weighted_f1 = f1_score(y_test, y_pred, average='micro')
    print('macro F1-score: {:.2f}'.format(weighted_f1))
    #out_of_sample_f1.append(weighted_f1)

    if stagenet:
        cm = confusion_matrix(y_test, y_pred)
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        #  Heat map
        plt.figure(figsize=(10, 7))
        sn.heatmap(cm, annot=True)
        plt.xlabel('Predicted')
        plt.ylabel('Truth')
        plt.savefig("./models/RF/stagenet/CM_num_estimators_" + str(N_ESTIMATORS) + "_seed_" + str(RANDOM_STATE) + "_accuracy_" + '{:.2f}'.format(weighted_f1) + ".png")
    else:
        cm = confusion_matrix(y_test, y_pred)
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        #  Heat map
        plt.figure(figsize=(10, 7))
        sn.heatmap(cm, annot=True)
        plt.xlabel('Predicted')
        plt.ylabel('Truth')
        plt.savefig("./models/RF/testnet/CM_num_estimators_" + str(N_ESTIMATORS) + "_seed_" + str(RANDOM_STATE) + "_accuracy_" + '{:.2f}'.format(weighted_f1) + ".png")

    y_main_predict = model.predict(X_Validation)
    weighted_f1_mainnet = f1_score(y_Validation, y_main_predict, average='macro')
    print('Mainnet macro F1-score: {:.2f}'.format(weighted_f1_mainnet))
    #mainnet_f1.append(weighted_f1_mainnet)

    if stagenet:
        cm = confusion_matrix(y_Validation, y_main_predict)
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        #  Heat map
        plt.figure(figsize=(10, 7))
        sn.heatmap(cm, annot=True)
        plt.xlabel('Predicted')
        plt.ylabel('Truth')
        plt.savefig("./models/RF/stagenet/MAIN_CM_num_estimators_" + str(N_ESTIMATORS) + "_seed_" + str(RANDOM_STATE) + "_accuracy_" + '{:.2f}'.format(weighted_f1_mainnet) + ".png")
    else:
        cm = confusion_matrix(y_Validation, y_main_predict)
        cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
        #  Heat map
        plt.figure(figsize=(10, 7))
        sn.heatmap(cm, annot=True)
        plt.xlabel('Predicted')
        plt.ylabel('Truth')
        plt.savefig("./models/RF/testnet/MAIN_CM_num_estimators_" + str(N_ESTIMATORS) + "_seed_" + str(RANDOM_STATE) + "_accuracy_" + '{:.2f}'.format(weighted_f1_mainnet) + ".png")
    return weighted_f1, weighted_f1_mainnet


def run_model_wrapper_rf(data):
    return run_model_rf(*data)


def random_forest(X_train, X_test, y_train, y_test, N_ESTIMATORS, MAX_DEPTH, RANDOM_STATE, X_Validation, y_Validation, stagenet_val=True):
    global stagenet
    stagenet = stagenet_val
    out_of_sample_f1 = []
    mainnet_f1 = []

    NUM_PROCESSES = cpu_count()
    Num_Iterations = 10

    if NUM_PROCESSES > Num_Iterations:
        NUM_PROCESSES = Num_Iterations

    with Manager() as manager:
        with manager.Pool(processes=NUM_PROCESSES) as pool:
            for returned_data in tqdm(pool.imap_unordered(func=run_model_wrapper_rf, iterable=zip(repeat(X_train, Num_Iterations), repeat(X_test, Num_Iterations), repeat(y_train, Num_Iterations), repeat(y_test, Num_Iterations), list(range(Num_Iterations)), repeat(X_Validation, Num_Iterations), repeat(y_Validation, Num_Iterations))), desc="(Multiprocessing) Training RF", total=Num_Iterations, colour='blue'):
                weighted_f1, weighted_f1_mainnet = returned_data
                out_of_sample_f1.append(weighted_f1)
                mainnet_f1.append(weighted_f1_mainnet)

    # Stats
    mean = sum(out_of_sample_f1) / len(out_of_sample_f1)
    standard_dev = stdev(out_of_sample_f1)

    main_mean = sum(mainnet_f1) / len(mainnet_f1)
    main_standard_dev = stdev(mainnet_f1)
    print(out_of_sample_f1)
    print(mainnet_f1)

    return mean*100, standard_dev*100, main_mean*100, main_standard_dev*100


def random_forest_hyperparam_tune(X, y, testnet_X_val_mainnet, testnet_y_val_mainnet):
    RANDOM_STATE = 1
    from sklearn.model_selection import GridSearchCV
    from hypopt import GridSearch
    import numpy as np
    from tune_sklearn import TuneGridSearchCV
    rfc = AdaBoostClassifier(random_state=RANDOM_STATE)
    param_grid = {
        'n_estimators': [100, 150, 200, 350, 500],
        'learning_rate': [.25,.5,.01]
    }

    # CV_rfc = GridSearchCV(estimator=rfc, param_grid=param_grid, cv=5)
    # CV_rfc.fit(X_train, y_train)
    # print(CV_rfc.best_params_)

    # # Grid-search all parameter combinations using a validation set.
    # opt = GridSearch(model=AdaBoostClassifier(), param_grid=param_grid)
    # opt.fit(X_train, y_train, X_Validation, y_Validation)
    # print('Test Score for Optimized Parameters:', opt.score(X_test, y_test))

    tune_search = TuneGridSearchCV(
        AdaBoostClassifier(random_state=RANDOM_STATE),
        param_grid,
        max_iters=10,
        n_jobs=-1
    )

    import time  # Just to compare fit times
    start = time.time()
    tune_search.fit(X, y)
    print("BEST PARAMS: " + str(tune_search.best_params_))
    end = time.time()
    print("Tune Fit Time:", end - start)
    pred = tune_search.predict(testnet_X_val_mainnet)
    accuracy = np.count_nonzero(np.array(pred) == np.array(testnet_y_val_mainnet)) / len(pred)
    print("Tune Accuracy:", accuracy)




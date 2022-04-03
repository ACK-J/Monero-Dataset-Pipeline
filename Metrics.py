from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_curve, auc
from sklearn.ensemble import RandomForestClassifier
from matplotlib.legend_handler import HandlerLine2D
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sn

"""
"""

def plot_confusion_matrix(model, X_test, y_test):
    #  Colors
    GREEN = '\033[92m'
    RED = '\033[91m'
    END = '\033[0m'
    y_predicted = model.predict(X_test)
    false_positive_rate, true_positive_rate, thresholds = roc_curve(y_test, y_predicted) # This willl break
    #  roc Area Under Curve is a good way to evaluate binary classification
    roc_auc = auc(false_positive_rate, true_positive_rate)

    print("False Positive Rate: ", RED + "{:.5}%".format(false_positive_rate[1] * 100) + END)
    print("True Positive Rate: ", GREEN + "{:.5}%".format(true_positive_rate[1] * 100) + END)
    print()
    print("Area Under the Receiver Operating Characteristics: " + GREEN + "{:.5}%".format(roc_auc * 100) + END)
    print()
    cm = confusion_matrix(y_test, y_predicted)
    print("Confusion Matrix for Test Set: \n" + str(cm))
    #  Heat map
    plt.figure(figsize=(10, 7))
    sn.heatmap(cm, annot=True)
    plt.xlabel('Predicted')
    plt.ylabel('Truth')
    plt.show()


def plot_n_estimators(X_train, y_train, X_test, y_test):
    # Identifying the ideal number of N_estimators
    n_estimators = [16, 18, 20, 25, 28, 30, 32, 35, 40, 43]
    train_results = []
    test_results = []
    for estimator in n_estimators:
        rf = RandomForestClassifier(n_estimators=estimator, n_jobs=-1)
        rf.fit(X_train, y_train)
        train_pred = rf.predict(X_train)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_train, train_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        train_results.append(roc_auc)

        y_pred = rf.predict(X_test)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_test, y_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        test_results.append(roc_auc)
    line1, = plt.plot(n_estimators, train_results, 'b', label="Train AUC")

    line2, = plt.plot(n_estimators, test_results, 'r', label="Test AUC")
    plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
    plt.ylabel('AUC score')
    plt.xlabel('n_estimators')
    plt.show()


def plot_max_depth(X_train, y_train, X_test, y_test):
    max_depths = np.linspace(1, 32, 32, endpoint=True)
    train_results = []
    test_results = []
    for max_depth in max_depths:
        rf = RandomForestClassifier(max_depth=max_depth, n_jobs=-1, n_estimators=10)
        rf.fit(X_train, y_train)
        train_pred = rf.predict(X_train)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_train, train_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)

        train_results.append(roc_auc)
        y_pred = rf.predict(X_test)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_test, y_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        test_results.append(roc_auc)

    line1, = plt.plot(max_depths, train_results, 'b', label="Train AUC")
    line2, = plt.plot(max_depths, test_results, 'r', label="Test AUC")
    plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
    plt.ylabel('AUC score')
    plt.xlabel('Tree depth')
    plt.show()


def plot_min_samples_splits(X_train, y_train, X_test, y_test):
    min_samples_splits = np.linspace(0.1, 1.0, 10, endpoint=True)
    train_results = []
    test_results = []
    for min_samples_split in min_samples_splits:
        rf = RandomForestClassifier(min_samples_split=min_samples_split, n_estimators=10)
        rf.fit(X_train, y_train)
        train_pred = rf.predict(X_train)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_train, train_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        train_results.append(roc_auc)
        y_pred = rf.predict(X_test)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_test, y_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        test_results.append(roc_auc)


    line1, = plt.plot(min_samples_splits, train_results, 'b', label="Train AUC")
    line2, = plt.plot(min_samples_splits, test_results, 'r', label="Test AUC")
    plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
    plt.ylabel('AUC score')
    plt.xlabel('min samples split')
    plt.show()


def plot_min_samples_leafs(X_train, y_train, X_test, y_test):
    min_samples_leafs = np.linspace(0.1, 0.5, 5, endpoint=True)
    train_results = []
    test_results = []
    for min_samples_leaf in min_samples_leafs:
        rf = RandomForestClassifier(min_samples_leaf=min_samples_leaf, n_estimators=10)
        rf.fit(X_train, y_train)
        train_pred = rf.predict(X_train)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_train, train_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        train_results.append(roc_auc)
        y_pred = rf.predict(X_test)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_test, y_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        test_results.append(roc_auc)

    line1, = plt.plot(min_samples_leafs, train_results, 'b', label="Train AUC")
    line2, = plt.plot(min_samples_leafs, test_results, 'r', label="Test AUC")
    plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
    plt.ylabel('AUC score')
    plt.xlabel('min samples leaf')
    plt.show()


def plot_max_features(X_train, y_train, X_test, y_test, X):
    max_features = list(range(1, X.shape[1]))
    train_results = []
    test_results = []
    for max_feature in max_features:
        rf = RandomForestClassifier(max_features=max_feature, n_estimators=10)
        rf.fit(X_train, y_train)
        train_pred = rf.predict(X_train)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_train, train_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        train_results.append(roc_auc)
        y_pred = rf.predict(X_test)
        false_positive_rate, true_positive_rate, thresholds = roc_curve(y_test, y_pred)
        roc_auc = auc(false_positive_rate, true_positive_rate)
        test_results.append(roc_auc)

    line1, = plt.plot(max_features, train_results, 'b', label="Train AUC")
    line2, = plt.plot(max_features, test_results, 'r', label="Test AUC")
    plt.legend(handler_map={line1: HandlerLine2D(numpoints=2)})
    plt.ylabel('AUC score')
    plt.xlabel('max features')
    plt.show()


def run_metrics(model, X_train, X_test, y_train, y_test, in_sample_accuracy, test_accuracy, totalPackets, total_stop_time, total_start_time):

    #  Colors
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

    print()

    #  18 features
    features = ["payload_length", "packet_len", "ip_ttl", "DNS_query_type", "DNS_ttl", "DNS_answer_type",
                "tcp_src_port", "tcp_dst_port", "udp_src_port", "udp_dst_port", "time", "top_1_million",
                "first_time_delta", "second_time_delta", "third_time_delta", "fourth_time_delta",
                "fifth_time_delta", "sixth_time_delta"]

    #  Metrics
    print("Model Hyper-parameters:\n", model)
    print()

    print("Model feature importance:")
    for idx, importance in enumerate(model.feature_importances_, start=0):
        if importance >= 0.1:
            print(GREEN + "{:20}\t{:.10f}".format(features[idx], importance) + END)
        else:
            print("{:20}\t{:.10f}".format(features[idx], importance))
    print()

    print("Overall In-Sample Accuracy: \t\t" + BLUE + "{:.5}%".format(in_sample_accuracy*100) + END)
    print("Overall Test Accuracy: \t\t\t\t" + BLUE + "{:.5}%".format(test_accuracy*100) + END)
    print("Total number of packets analyzed:\t" + BLUE + "{:,}".format(totalPackets) + END)
    print("Time to create datasets and train model (mins): " + GREEN + "{:.3}".format((total_stop_time - total_start_time) / 60) + END)
    print()
    print("Number of packets in X_train:\t{:,}".format(len(X_train)))
    print("Number of packets in y_train:\t{:,}".format(len(y_train)))
    print("Number of packets in X_test:\t{:,}".format(len(X_test)))
    print("Number of packets in y_test:\t{:,}".format(len(y_test)))
    print()
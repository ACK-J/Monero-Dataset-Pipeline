from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sn
import numpy as np
import pickle
from DataScience import NeuralNetwork
from DataScience import GradientBoostedClassifier
from DataScience import RandomForest
"""

"""

#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'

N_ESTIMATORS = 101  # The amount of trees (default 101 [keep at an odd number])
MAX_DEPTH = 9  # Depth of the decision trees (default 10)
RANDOM_STATE = 1  # Random seed (default 1)
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
    print("Dataset includes", len(X.columns), "features.")

    if TEST_SIZE != 0:
        #  Split the data up traditionally into 80% training and 20% training
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, shuffle=False)
        print("Dataset split into training and testing.\n")
        return X_train, X_test, y_train, y_test
    else:
        print()
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
    plt.imsave

    cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    #  Heat map
    plt.figure(figsize=(10, 7))
    sn.heatmap(cm, annot=True)
    plt.xlabel('Predicted')
    plt.ylabel('Truth')
    plt.show()

    # https://towardsdatascience.com/confusion-matrix-for-your-multi-class-machine-learning-model-ff9aa3bf7826
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


def Diff(li1, li2):
    return list(set(li1) - set(li2)) + list(set(li2) - set(li1))


def main():
    # Preliminary Testnet Dataset
    testnet_X_train, testnet_X_test, testnet_y_train, testnet_y_test = load_data(0.2, "../TestnetDataset/X_Undersampled.pkl", "../TestnetDataset/y_Undersampled.pkl")
    testnet_X_val_mainnet, _, testnet_y_val_mainnet, _ = load_data(0, "../MainnetDatasetTestnet/X_Undersampled.pkl", "../MainnetDatasetTestnet/y_Undersampled.pkl")

    # Stagenet Dataset
    X_train, X_test, y_train, y_test = load_data(0.2, "../StagenetDataset/X_Undersampled.pkl", "../StagenetDataset/y_Undersampled.pkl")
    X_val_mainnet, _, y_val_mainnet, _ = load_data(0, "../MainnetDatasetStagenet/X_Undersampled.pkl", "../MainnetDatasetStagenet/y_Undersampled.pkl")
    # Fill in any missing columns for the mainnet stagenet dataset
    missing_df_cols = Diff(X_test.columns.to_list(), X_val_mainnet.columns.to_list())
    X_val_mainnet = X_val_mainnet.reindex(columns=X_val_mainnet.columns.tolist() + missing_df_cols, fill_value=-1)

    # print("STAGENET GBC TRAINING")
    # print(GradientBoostedClassifier.gradient_boosted(X_train, X_test, y_train, y_test, RANDOM_STATE, X_val_mainnet, y_val_mainnet))
    # print("\n\n\n\nTESTNET GBC TRAINING")
    # print(GradientBoostedClassifier.gradient_boosted(testnet_X_train, testnet_X_test, testnet_y_train, testnet_y_test, RANDOM_STATE, testnet_X_val_mainnet, testnet_y_val_mainnet, stagenet=False))
    # # GradientBoostedClassifier.gradient_boosted_hyper_param_tuning(X_train, X_test, y_train, y_test, RANDOM_STATE)
    # RandomForest.random_forest_hyperparam_tune(testnet_X_train, testnet_y_train, testnet_X_val_mainnet, testnet_y_val_mainnet)
    # exit()

    # Stagenet
    GBC_stagenet_mean, GBC_stagenet_standard_dev, GBC_stagenet_main_mean, GBC_stagenet_main_standard_dev = GradientBoostedClassifier.gradient_boosted(X_train, X_test, y_train, y_test, RANDOM_STATE, X_val_mainnet, y_val_mainnet)
    NN_stagenet_mean, NN_stagenet_standard_dev, NN_stagenet_main_mean, NN_stagenet_main_standard_dev = NeuralNetwork.MLP(X_train, X_test, y_train, y_test, X_val_mainnet, y_val_mainnet)
    RF_stagenet_mean, RF_stagenet_standard_dev, RF_stagenet_main_mean, RF_stagenet_main_standard_dev = RandomForest.random_forest(X_train, X_test, y_train, y_test, N_ESTIMATORS, MAX_DEPTH, RANDOM_STATE, X_val_mainnet, y_val_mainnet)

    # Preliminary Testnet
    GBC_testnet_mean, GBC_testnet_standard_dev, GBC_testnet_main_mean, GBC_testnet_main_standard_dev = GradientBoostedClassifier.gradient_boosted(testnet_X_train, testnet_X_test, testnet_y_train, testnet_y_test, RANDOM_STATE, testnet_X_val_mainnet, testnet_y_val_mainnet, stagenet=False)
    NN_testnet_mean, NN_testnet_standard_dev, NN_testnet_main_mean, NN_testnet_main_standard_dev = NeuralNetwork.MLP(testnet_X_train, testnet_X_test, testnet_y_train, testnet_y_test, testnet_X_val_mainnet, testnet_y_val_mainnet, stagenet=False)
    RF_testnet_mean, RF_testnet_standard_dev, RF_testnet_main_mean, RF_testnet_main_standard_dev = RandomForest.random_forest(testnet_X_train, testnet_X_test, testnet_y_train, testnet_y_test, N_ESTIMATORS, MAX_DEPTH, RANDOM_STATE, testnet_X_val_mainnet, testnet_y_val_mainnet, stagenet=False)

    # Print Results
    from prettytable import PrettyTable
    table = [['Dataset Name', 'GCB Accuracy', 'GCB Accuracy std', 'Neural Network Accuracy', 'Neural Network Accuracy std', 'Random Forest Accuracy',
              'Random Forest Accuracy std', 'GCB Mainnet Accuracy', 'GCB Mainnet Accuracy std', 'Neural Network Mainnet Accuracy',
              'Neural Network Mainnet Accuracy std', 'Random Forest Mainnet Accuracy', 'Random Forest Mainnet Accuracy std'],
             ["Stagenet", GBC_stagenet_mean, GBC_stagenet_standard_dev, NN_stagenet_mean, NN_stagenet_standard_dev, RF_stagenet_mean, RF_stagenet_standard_dev, GBC_stagenet_main_mean, GBC_stagenet_main_standard_dev, NN_stagenet_main_mean, NN_stagenet_main_standard_dev, RF_stagenet_main_mean, RF_stagenet_main_standard_dev],
             ["Testnet", GBC_testnet_mean, GBC_testnet_standard_dev, NN_testnet_mean, NN_testnet_standard_dev, RF_testnet_mean, RF_testnet_standard_dev, GBC_testnet_main_mean, GBC_testnet_main_standard_dev, NN_testnet_main_mean, NN_testnet_main_standard_dev, RF_testnet_main_mean, RF_testnet_main_standard_dev]]
    tab = PrettyTable(table[0])
    tab.add_rows(table[1:])
    print(tab)


if __name__ == '__main__':
    main()

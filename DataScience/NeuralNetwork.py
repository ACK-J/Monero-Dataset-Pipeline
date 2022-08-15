import numpy as np
import pickle
from sklearn.metrics import f1_score
from statistics import stdev
from sklearn.metrics import confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sn


def confusion_mtx(y_test, y_pred):
    from sklearn.metrics import confusion_matrix
    import matplotlib.pyplot as plt
    import seaborn as sn
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


def MLP(X_train, X_test, y_train, y_test, X_Validation, y_Validation, stagenet=True):
    from keras.models import Sequential
    from keras.layers import Dense, Activation, Dropout, BatchNormalization
    from sklearn.preprocessing import StandardScaler
    from keras.utils import np_utils
    from sklearn.model_selection import cross_val_score
    from sklearn.model_selection import KFold

    out_of_sample_f1 = []
    mainnet_f1 = []

    EPOCHS = 100
    BATCH_SIZE = 512

    y_test_copy = y_test.copy()
    y_test = np.asarray(y_test)
    y_test = np_utils.to_categorical(y_test)
    y_test = np.delete(y_test, 0, 1)

    y_train = np.asarray(y_train)
    y_train = np_utils.to_categorical(y_train)
    y_train = np.delete(y_train, 0, 1)

    y_val_copy = y_Validation.copy()
    y_val = np.asarray(y_Validation)
    y_val = np_utils.to_categorical(y_val)
    y_val = np.delete(y_val, 0, 1)


    scaler = StandardScaler().fit(X_train)
    X_train = scaler.transform(X_train)

    scaler = StandardScaler().fit(X_test)
    X_test = scaler.transform(X_test)

    scaler = StandardScaler().fit(X_Validation)
    X_Validation = scaler.transform(X_Validation)

    # fix off by one error
    for i in range(len(y_test_copy)):
        y_test_copy[i] = y_test_copy[i] - 1
    for i in range(len(y_val_copy)):
        y_val_copy[i] = y_val_copy[i] - 1

    for i in range(10):
        from keras_visualizer import visualizer
        model = Sequential()
        model.add(Dense(11, input_shape=(X_train.shape[1],), activation='relu'))
        model.add(Dense(64, activation='relu'))
        model.add(Dropout(.1))
        model.add(Dense(64, activation='relu'))
        model.add(Dense(32, activation='relu'))
        model.add(Dense(11))
        model.add(BatchNormalization())
        model.add(Activation('softmax'))
        model.summary()
        # https://towardsdatascience.com/visualizing-keras-models-4d0063c8805e
        # visualizer(model, format='png', view=True)

        # class_weight = {0: 1.,
        #                 1: 50.,
        #                 2: 50.,
        #                 3: 50.,
        #                 4: 50.,
        #                 5: 50.,
        #                 6: 50.,
        #                 7: 50.,
        #                 8: 50.,
        #                 9: 50.,
        #                 10: 1.}

        model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
        model.fit(X_train, y_train, epochs=EPOCHS, batch_size=BATCH_SIZE, validation_data=(X_Validation, y_val))#, class_weight=class_weight)
        if stagenet:
            with open("./models/NN/stagenet/epochs_" + str(EPOCHS) + "_batch_size_" + str(BATCH_SIZE) + "_i_" + str(i) + ".pkl", "wb") as fp:
                pickle.dump(model, fp)
        else:
            with open("./models/NN/testnet/epochs_" + str(EPOCHS) + "_batch_size_" + str(BATCH_SIZE) + "_i_" + str(i) + ".pkl", "wb") as fp:
                pickle.dump(model, fp)
        score = model.evaluate(X_test, y_test, verbose=1)
        print(score[1])

        # y_pred = list(model.predict(X_Validation).argmax(axis=1))
        #confusion_mtx(y_Validation, y_pred)

        # Metrics
        print("NN Metrics ")
        y_pred = model.predict(X_test)
        y_pred = np.argmax(y_pred, axis=1).tolist()
        micro_f1 = f1_score(y_test_copy, y_pred, average='samples')
        print('Avg F1-score: {:.2f}'.format(micro_f1))
        out_of_sample_f1.append(micro_f1)
        if stagenet:
            cm = confusion_matrix(y_test_copy, y_pred)
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/NN/stagenet/CM_epochs_" + str(EPOCHS) + "_batch_size_" + str(BATCH_SIZE) + "_i_" + str(i) + "_accuracy_" + str(micro_f1) + ".png")
        else:
            cm = confusion_matrix(y_test_copy, y_pred)
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/NN/testnet/CM_epochs_" + str(EPOCHS) + "_batch_size_" + str(BATCH_SIZE) + "_i_" + str(i) + "_accuracy_" + str(micro_f1) + ".png")

        y_main_predict = model.predict(X_Validation)
        y_main_predict = np.argmax(y_main_predict, axis=1).tolist()
        macro_f1_mainnet = f1_score(y_val_copy, y_main_predict, average='macro')
        print('Mainnet Weighted F1-score: {:.2f}'.format(macro_f1_mainnet))
        mainnet_f1.append(macro_f1_mainnet)

        if stagenet:
            cm = confusion_matrix(y_val_copy, y_main_predict)
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/NN/stagenet/MAIN_CM_epochs_" + str(EPOCHS) + "_batch_size_" + str(BATCH_SIZE) + "_i_" + str(i) + "_accuracy_" + str(macro_f1_mainnet) + ".png")
        else:
            cm = confusion_matrix(y_val_copy, y_main_predict)
            cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
            #  Heat map
            plt.figure(figsize=(10, 7))
            sn.heatmap(cm, annot=True)
            plt.xlabel('Predicted')
            plt.ylabel('Truth')
            plt.savefig("./models/NN/testnet/MAIN_CM_epochs_" + str(EPOCHS) + "_batch_size_" + str(BATCH_SIZE) + "_i_" + str(i) + "_accuracy_" + str(macro_f1_mainnet) + ".png")

    # kfold = KFold(n_splits=10, shuffle=True)
    # results = cross_val_score(model, X_test, y_test, cv=kfold)
    # print("Baseline: %.2f%% (%.2f%%)" % (results.mean() * 100, results.std() * 100))

    # Stats
    mean = sum(out_of_sample_f1) / len(out_of_sample_f1)
    standard_dev = stdev(out_of_sample_f1)

    main_mean = sum(mainnet_f1) / len(mainnet_f1)
    main_standard_dev = stdev(mainnet_f1)
    print(out_of_sample_f1)
    print(mainnet_f1)

    return mean*100, standard_dev*100, main_mean*100, main_standard_dev*100
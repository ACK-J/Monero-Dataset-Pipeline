import numpy as np
import pickle

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


def MLP(X_train, X_test, y_train, y_test, X_Validation, y_Validation):
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
    scaler = StandardScaler().fit(X_Validation)
    X_Validation = scaler.transform(X_Validation)

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
    model.fit(X_train, y_train, epochs=100, batch_size=128)
    with open("neural_network.pkl", "wb") as fp:
        pickle.dump(model, fp)
    with open("neural_network.pkl", "rb") as fp:
        model = pickle.load(fp)
    score = model.evaluate(X_test, y_test, verbose=1)
    print(score[1])

    y_pred = list(model.predict(X_Validation).argmax(axis=1))
    for i in range(len(y_pred)):
        y_pred[i] = y_pred[i] + 1
    confusion_mtx(y_Validation, y_pred)


    kfold = KFold(n_splits=10, shuffle=True)
    results = cross_val_score(model, X_test, y_test, cv=kfold)
    print("Baseline: %.2f%% (%.2f%%)" % (results.mean() * 100, results.std() * 100))
from sklearn.ensemble import RandomForestClassifier
from analysis import confusion_mtx
#  Colors
GREEN = '\033[92m'
RED = '\033[91m'
END = '\033[0m'

def random_forest(X_train, X_test, y_train, y_test, N_ESTIMATORS, MAX_DEPTH, RANDOM_STATE):
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
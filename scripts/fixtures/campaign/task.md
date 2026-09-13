# Toy task: fit y = f(x) on an integer grid

`$LAB_TRAIN/inputs.json` and `$LAB_TRAIN/labels.json` are lists of numbers. Predict the
label for every x in `$LAB_SPLIT_INPUTS/inputs.json` and write the list of predictions to
`$LAB_PREDICTIONS_OUT`. Score is negative mean squared error (higher is better).
The trivial baseline predicts 0 everywhere.

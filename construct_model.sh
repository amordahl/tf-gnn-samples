#!/bin/zsh
set -x

if [ "$#" -ne 4 ]; then
    echo "Usage: ./construct_model.sh PROCESSING_SCRIPT PROCESSING_PARAMS TARGET_DIR MASTER_FOLDER"
    exit 1
fi

# 1. Make new model folder
PROCESSING_SCRIPT=$1
PROCESSING_PARAMS=$2
TARGET_DIR=$3
MASTER_FOLDER=$4
DATASET_DIR="datasets/$TARGET_DIR"
RESULTS_DIR="results/$TARGET_DIR"

# 1a. If the dataset folder exists, remove it
if [ -d "$RESULTS_DIR" ]; then
    echo "Results folder already exists. Refusing to overwrite."
    exit 1
fi
    
if [ ! -d "$DATASET_DIR" ]; then
    echo 'Creating dataset directory.'
    mkdir -p "$DATASET_DIR"
    echo 'Removing all json files in the master folder.'
    find "$MASTER_FOLDER" -type f -name '*.json' | parallel rm
    echo 'Creating new json files.'
    find "$MASTER_FOLDER" -type f | parallel --progress python "$PROCESSING_SCRIPT" --params "$PROCESSING_PARAMS" {} {}.json
    echo 'Transferring to dataset folder.'
    for i in {0..9}; do
	# Create the directory
	mkdir -p "$DATASET_DIR/$i"
	mkdir "$DATASET_DIR/$i/graphs-valid"
	find "$MASTER_FOLDER" -type f -name '*.json' | grep "split_$i" | parallel cp -t "$DATASET_DIR/$i/graphs-valid"
	mkdir "$DATASET_DIR/$i/graphs-train" 
	find "$MASTER_FOLDER" -type f -name '*.json' | grep -v "split_$i" | grep split | parallel cp -t "$DATASET_DIR/$i/graphs-train"
    done
    mkdir "$DATASET_DIR/graphs-test"
    find "$MASTER_FOLDER/test" -type f -name '*.json' | parallel cp -t "$DATASET_DIR/graphs-test"
    echo 'Zipping up.'
    find "$DATASET_DIR" -type f -name '*.json' | parallel gzip
    echo 'Cleaning up json files.'
    find "$MASTER_FOLDER" -type f -name '*.json' | parallel rm
else
    echo 'Dataset directory already exists. Using it....'
fi

# Perform training.
echo 'Now training.'
parallel -j 1 --progress python train.py --data-path "$DATASET_DIR"/{2} --result-dir "$RESULTS_DIR"/{1}/{2} --model-param-overrides ''\''{"random_seed": {1}}'\''' GGNN varmisuse ::: 1591 8340 2137 9914 3407 ::: 0 1 2 3 4 5 6 7 8 9
echo 'Training done. Now testing.'
find "$RESULTS_DIR" -type f -name '*.pickle' | parallel "python test.py {} $DATASET_DIR/graphs-test > {}.test"

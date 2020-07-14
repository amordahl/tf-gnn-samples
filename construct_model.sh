#!/bin/zsh

# 1. Make new model folder
$MODEL_DIR = './automatic_dataset'

# 1a. If the model folder exists, remove it
if [ -d '$MODEL_DIR' ]; then
    echo 'Removing existing data directory.\n'
    rm -rf '$MODEL_DIR'
fi

# 2. Create new model folder.
echo 'Creating new data directory.\n'
mkdir '$MODEL_DIR'
cd '$MODEL_DIR'
mkdir graphs-test
mkdir graphs-train
mkdir graphs-valid
cd ..

# 3. Construct new json
echo 'Removing existing json files.\n'
find ./ast_json -type f -name "*.json" | parallel rm {}
echo 'Now creating new json files.\n'
source ~/.virtualenvs/gnn/bin/activate
find ./ast_json -type f -name "*.ast" | parallel python ../sv-comp-ml/scripts/ast-dump.py {} {}.json
echo 'Json files created.\nMoving the json files to the new model directory.'
find ./ast_json/train -type f -name "*.json" | parallel mv -t ./'$MODEL_DIR'/train
find ./ast_json/valid -type f -name "*.json" | parallel mv -t ./'$MODEL_DIR'/valid
find ./ast_json/test -type f -name "*.json" | parallel mv -t ./'$MODEL_DIR'/test

# 4. Train model
echo 'Now training.'
python train.py GGNN varmisuse --data-path '$MODEL_DIR'

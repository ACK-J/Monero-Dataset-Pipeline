# Monero Dataset Pipeline
A pipeline that automates the creation and transaction of monero wallets used to collect a dataset suitable for supervised learning applications. 

# Installation
```
sudo apt update
sudo apt install vim git jq expect tmux parallel python3 python3-tk bc curl python3-pip -y
pip3 install numpy
cd ~ && wget https://downloads.getmonero.org/cli/monero-linux-x64-v0.17.3.0.tar.bz2
tar -xvf monero-linux-x64-v0.17.3.0.tar.bz2 && cd monero-x86_64-linux-gnu-v0.17.3.0 && sudo cp monero* /usr/bin/ && cd ..
git clone git@github.com:ACK-J/Monero-Dataset-Pipeline.git && cd XMR-Transaction-Automation
chmod +x ./run.sh && chmod 777 -R Funding_Wallets/
# Make sure global variables are set
./run.sh
```

# Stagenet Dataset
| File | Size | Serialized | Description |
|:---:|:---:|:---:|:-----|
| `dataset.csv` | 1.4GB |  | The exhaustive dataset including all metadata for each transaction in csv format. |
| `dataset.json` | 1.5GB | :white_check_mark: | The exhaustive dataset including all metadata for each transaction in json format. |
| `X.csv` | 4.1GB |  | A modified version of dataset.csv with all features irrelevant to machine learning removed, in csv format. |
| `X.pkl` | 6.5GB | :white_check_mark: | A modified version of dataset.json with all features irrelevant to machine learning removed, as a pickled pandas dataframe. |
| `y.pkl` | 9.5MB | :white_check_mark: | A pickled list of python dictionaries which contain private information regarding the coresponding index of X.pkl. |
| `X_Undersampled.csv` | 1.4GB |  | A modified version of X.csv with all data points shuffled and undersampled. |
| `X_Undersampled.pkl` | 2.3GB | :white_check_mark: | A modified version of X.pkl with all data points shuffled and undersampled. |
| `y_Undersampled.pkl` | 325kB | :white_check_mark: | A pickled list containing the labels coresponding to the index of X_Undersampled.pkl. |

# How to load the dataset using Python and pickle
```python
import pickle

with open("./Dataset_Files/dataset.json", "r") as fp:
    data = json.load(fp)
    
with open("./Dataset_Files/X.pkl", "rb") as fp:
    X = pickle.load(fp)
    
with open("./Dataset_Files/y.pkl", "rb") as fp:
    y = pickle.load(fp)
    
with open("./Dataset_Files/X_Undersampled.pkl", "rb") as fp:
    X_Undersampled = pickle.load(fp)
    
with open("./Dataset_Files/y_Undersampled.pkl", "rb") as fp:
    y_Undersampled = pickle.load(fp)
```


# Problem Solving and Useful Commands
```
#  If collect.sh throws the error: Failed to create a read transaction for the db: MDB_READERS_FULL: Environment maxreaders limit reached
/home/user/monero/external/db_drivers/liblmdb/mdb_stat -rr ~/.bitmonero/testnet/lmdb/
```
### Check progress of collect.sh While it is Running
`find ./ -iname *.csv | cut -d '/' -f 2 | sort -u`
### After Running collect.sh Gather the Ring Positions
`find . -name "*outgoing*" | xargs cat | cut -f 6 -d ',' | grep -v Ring_no/Ring_size | cut -f 1 -d '/'`





# Data Collection Pipeline Flowcharts
## Run.sh
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663123-2d0fb9c9-8787-42c8-8ec7-24b45c201bc5.png"/>
</p>

## Collect.sh
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663094-ff823283-cf74-420a-b5db-f517489b9f31.png"/>
</p>

## Create_Dataset.py
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663063-2c34dbc3-ce99-49c5-9807-b952c7f4fd68.png"/>
</p>




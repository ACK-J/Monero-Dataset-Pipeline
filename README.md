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

# Dataset Files
| File | Stagenet Size | Testnet Size | Serialized | Description |
|:---:|:---:|:---:|:---:|:-----|
| `dataset.csv` | 1.4GB | 13.4GB |  | The exhaustive dataset including all metadata for each transaction in csv format. |
| `dataset.json` | 1.5GB | N/A | :white_check_mark: | The exhaustive dataset including all metadata for each transaction in json format. |
| `dataset.pkl` | N/A | 71.GB | :white_check_mark: | The exhaustive dataset including all metadata for each transaction in pickle format. |
| `X.csv` | 4.1GB | 32.5GB |  | A modified version of dataset.csv with all features irrelevant to machine learning removed, in csv format. |
| `X.pkl` | 6.5GB | 51.9GB | :white_check_mark: | A modified version of dataset.json with all features irrelevant to machine learning removed, as a pickled pandas dataframe. |
| `y.pkl` | 9.5MB | 42.6MB | :white_check_mark: | A pickled list of python dictionaries which contain private information regarding the coresponding index of X.pkl. |
| `X_Undersampled.csv` | 1.4GB | 75.5MB |  | A modified version of X.csv with all data points shuffled and undersampled. |
| `X_Undersampled.pkl` | 2.3GB | 101MB | :white_check_mark: | A modified version of X.pkl with all data points shuffled and undersampled. |
| `y_Undersampled.pkl` | 325kB | 312.1kB | :white_check_mark: | A pickled list containing the labels coresponding to the index of X_Undersampled.pkl. |

## Dataset Download Links
`Stagenet_Dataset_7_2_2022.7z` 837 MB

- Includes all files mentioned above in the dataset table, compressed using 7-zip

- SHA-256 Hash: `bf1b87f83a5c220263071e75c453d3886f9190856c71411be164f3328be38b79`

- [https://drive.google.com/file/d/1cmkb_7_cVe_waLdVJ9USdK07SPWgdgva/view](https://drive.google.com/file/d/1cmkb_7_cVe_waLdVJ9USdK07SPWgdgva/view)

`Testnet_Dataset_6_7_2022.7z` 4.7 GB

- Includes all files mentioned above in the dataset table, compressed using 7-zip

- SHA-256 Hash: `396c25083a8a08432df58c88cb94137850004bee3236b21cb628a8786fac15d3`

- [https://drive.google.com/file/d/13Jw3J8yyKiZ9J5WsIRTUX0GDzbqBI-R5/view?usp=sharing](https://drive.google.com/file/d/13Jw3J8yyKiZ9J5WsIRTUX0GDzbqBI-R5/view?usp=sharing)

## How to load the dataset using Python and Pickle
```python
import pickle
import json

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
### If Collect.sh throws the error: `Failed to create a read transaction for the db: MDB_READERS_FULL: Environment maxreaders limit reached`
```
/home/user/monero/external/db_drivers/liblmdb/mdb_stat -rr ~/.bitmonero/testnet/lmdb/
```
### Check progress of collect.sh while its running
```
find ./ -iname *.csv | cut -d '/' -f 2 | sort -u
```
### After running collect.sh gather the ring positions
```
find . -name "*outgoing*" | xargs cat | cut -f 6 -d ',' | grep -v Ring_no/Ring_size | cut -f 1 -d '/'
```



# Data Collection Pipeline Flowcharts
### Run.sh
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663123-2d0fb9c9-8787-42c8-8ec7-24b45c201bc5.png"/>
</p>

### Collect.sh
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663094-ff823283-cf74-420a-b5db-f517489b9f31.png"/>
</p>

### Create_Dataset.py
<p align="center">
  <img src="https://user-images.githubusercontent.com/60232273/181663063-2c34dbc3-ce99-49c5-9807-b952c7f4fd68.png"/>
</p>




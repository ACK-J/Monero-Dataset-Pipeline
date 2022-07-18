import json
import pickle
import psycopg2
from sys import argv
from glob import glob
from time import time
from tqdm import tqdm
from gc import collect
from requests import get
from os.path import exists
from numpy import intersect1d
from statistics import median
from datetime import datetime
from collections import Counter
from sklearn.utils import shuffle
from cherrypicker import CherryPicker  # https://pypi.org/project/cherrypicker/
from pandas import DataFrame, options
from multiprocessing import cpu_count, Manager
from requests.exceptions import ConnectionError
from os import walk, getcwd, chdir, listdir, fsync, system, remove
options.mode.chained_assignment = None  # default='warn'

'''
Description: 
Usage: ./create_dataset.py < Wallets Directory Path >
Date: 7/8/2022
Author: ACK-J

Warning: DO NOT run this with a remote node, there are a lot of blockchain lookups and it will be slow!
Warning: Run your own monerod process and block explorer, it is very easy!
To run your own block explorer:
    monerod --stagenet                        https://github.com/monero-project/monero
    xmrblocks --stagenet --enable-json-api    https://github.com/moneroexamples/onion-monero-blockchain-explorer
    
'''

######################
#  Global Variables  #
######################
data = {}                               # Key = tx hash, val = dict(transaction metadata)
NUM_PROCESSES = cpu_count()             # Set the number of processes for multiprocessing
NETWORK = "stagenet"                    # testnet, stagenet, mainnet
API_URL = "https://community.rino.io/explorer/" + NETWORK + "/api"  # Remote Monero Block Explorer
API_URL = "http://127.0.0.1:8081/api"   # Local Monero Block Explorer
NUM_RING_MEMBERS = 11                   # DL models depend on a discrete number of rings

POSTGRES_SQL_HOST = "127.0.0.1"
POSTGRES_SQL_PORT = "18333"
POSTGRES_SQL_USERNAME = "xmrack"
POSTGRES_SQL_PASSWORD = "xmrack"
POSTGRES_SQL_DB_NAME = "xmrstagedb"

###################################################################################
#     You shouldn't need to edit anything below this line unless things break     #
###################################################################################

# Terminal ANSI Color Codes
red = '\033[31m'
blue = "\033[0;34m"
green = "\033[92m"
yellow = "\033[1;33m"
reset = '\033[0m'


def get_xmr_block(block_num):
    return get(API_URL + "/block/" + str(block_num)).json()["data"]


def get_xmr_tx(tx_hash):
    return get(API_URL + "/transaction/" + tx_hash).json()["data"]


def enrich_data(tx_dict_item):
    tx_hash = tx_dict_item[0]
    transaction_entry = tx_dict_item[1]

    tx_response = get_xmr_tx(str(tx_hash))
    block_response = get_xmr_block(str(tx_response["block_height"]))
    previous_block_response = get_xmr_block(str(int(tx_response["block_height"]) - 1))
    transaction_entry['Tx_Size'] = tx_response["tx_size"]
    # Check if the fee is missing
    if 'Tx_Fee' not in transaction_entry.keys():
        transaction_entry['Tx_Fee'] = float(tx_response['tx_fee'] * 0.000000000001)  # Converted from piconero to monero
    transaction_entry['Tx_Fee_Per_Byte'] = float(transaction_entry['Tx_Fee']) / int(transaction_entry['Tx_Size'])
    transaction_entry['Num_Confirmations'] = tx_response["confirmations"]
    transaction_entry['Time_Of_Enrichment'] = int(time())
    if tx_response["coinbase"] == "false":
        transaction_entry['Is_Coinbase_Tx'] = False
    elif tx_response["coinbase"] == "true":
        transaction_entry['Is_Coinbase_Tx'] = True
    transaction_entry['Tx_Extra'] = tx_response["extra"]
    transaction_entry['Tx_Extra_Length'] = len(tx_response["extra"])
    transaction_entry['Ring_CT_Type'] = tx_response["rct_type"]
    transaction_entry['Payment_ID'] = tx_response["payment_id"]
    transaction_entry['Payment_ID8'] = tx_response["payment_id8"]

    Total_Block_Tx_Fees = 0
    for tx in block_response["txs"]:
        Total_Block_Tx_Fees += int(tx["tx_fee"])
    transaction_entry['Total_Block_Tx_Fees'] = float(Total_Block_Tx_Fees * 0.000000000001)  # Converted from piconero to monero
    transaction_entry['Block_Size'] = block_response["size"]
    transaction_entry['Time_Since_Last_Block'] = int((datetime.fromtimestamp(int(block_response["timestamp"])) - datetime.fromtimestamp(int(previous_block_response["timestamp"]))).total_seconds())

    #  Add Input Information
    for input_idx, input in enumerate(tx_response['inputs']):
        transaction_entry['Inputs'].append(
            {
                'Amount': input['amount'],
                'Key_Image': input['key_image'],
                'Ring_Members': input['mixins']
            }
        )
        #  Create dictionaries for each of the previous
        transaction_entry['Inputs'][input_idx]['Previous_Tx_Num_Outputs'] = {}
        transaction_entry['Inputs'][input_idx]['Previous_Tx_Num_Inputs'] = {}
        transaction_entry['Inputs'][input_idx]['Previous_Tx_Time_Deltas'] = {}
        transaction_entry['Inputs'][input_idx]['Previous_Tx_Block_Num_Delta'] = {}
        transaction_entry['Inputs'][input_idx]['Previous_Tx_TxExtra_Len'] = {}
        transaction_entry['Inputs'][input_idx]['Decoys'] = {}

        # Iterate over each mixin in the input
        for ring_mem_num, ring in enumerate(input['mixins']):
            prev_tx = get_xmr_tx(ring['tx_hash'])
            #  Get the number of inputs and outputs from the previous transaction involving the mixin
            try:
                num_mixin_outputs = len(prev_tx["outputs"])
            except TypeError as e:  # Edge case where there are no outputs
                num_mixin_outputs = 0
            try:
                num_mixin_inputs = len(prev_tx["inputs"])
            except TypeError as e:  # Edge case where there are no inputs
                num_mixin_inputs = 0
            #  Add the number of outputs to the specific mixin
            transaction_entry['Inputs'][input_idx]['Previous_Tx_Num_Outputs'][str(ring_mem_num)] = num_mixin_outputs
            #  Add the number of inputs to the specific mixin
            transaction_entry['Inputs'][input_idx]['Previous_Tx_Num_Inputs'][str(ring_mem_num)] = num_mixin_inputs
            #  Find how long it has been from this block to the previous mixin transaction
            transaction_entry['Inputs'][input_idx]['Previous_Tx_Time_Deltas'][str(ring_mem_num)] = int((datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch']) - datetime.fromtimestamp(prev_tx['timestamp'])).total_seconds())
            #  Find how many blocks are in between this block and the mixin transaction
            transaction_entry['Inputs'][input_idx]['Previous_Tx_Block_Num_Delta'][str(ring_mem_num)] = int(transaction_entry['Block_Number']) - int(prev_tx['block_height'])
            #  Get the length of the tx_extra from each mixin transaction
            transaction_entry['Inputs'][input_idx]['Previous_Tx_TxExtra_Len'][str(ring_mem_num)] = len(prev_tx['extra'])

    try:
        conn = psycopg2.connect("host=" + POSTGRES_SQL_HOST + " port=" + POSTGRES_SQL_PORT + " dbname=" + POSTGRES_SQL_DB_NAME + " user=" + POSTGRES_SQL_USERNAME + " password=" + POSTGRES_SQL_PASSWORD)
    except psycopg2.OperationalError as e:
        print(red + "ERROR: Connection to PostgresSQL Database Failed!" + reset)
        exit(1)
    with conn.cursor() as cur:
        query = """
WITH txinfo AS (
    SELECT 
        X.tx_block_height AS height_B,
        X.tx_vin_index AS input_pos,
        X.ringmember_block_height AS height_A,
        X.ringmember_txo_key AS stealth_addr_A,
        X.tx_vin_ringmember_index AS input_mem_idx
    FROM tx_ringmember_list X
    WHERE X.tx_hash = %s
)
SELECT DISTINCT  
    height_A,
    Y.ringtx_block_height AS height_B,
    input_pos,
    input_mem_idx
FROM ringmember_tx_list Y
JOIN txinfo T ON T.stealth_addr_A = Y.txo_key
WHERE Y.ringtx_block_height >= height_A AND Y.ringtx_block_height <= height_B
ORDER BY input_pos, input_mem_idx, height_B ASC
"""
        cur.execute(query, ('\\x' + tx_hash,))
        results = cur.fetchall()

        previous_input_mem = None
        num_decoys_found = 0
        #  Iterate over the list of results
        for result_idx, occurrence in enumerate(results):
            num_decoys_found += 1
            #  unzip the list into variables
            Block_A, Block_B, Input_Pos, Input_Member_Idx = occurrence
            #  Input position and member index start at 1 instead of 0. To keep
            #  things consistent, subtract one from each.
            Input_Pos -= 1
            Input_Member_Idx -= 1
            #  If this is the first time running
            if previous_input_mem is None:
                #  Set the input pos and member index
                previous_input_mem = (Input_Pos, Input_Member_Idx)
            #  Check if the current input pos and member index is different from the previous
            elif previous_input_mem != (Input_Pos, Input_Member_Idx):
                #  Get the length of the previous amount of on chain decoys found
                transaction_entry['Inputs'][previous_input_mem[0]]['Decoys'][previous_input_mem[1]]['Number_Of_On_Chain_Decoys'] = len(transaction_entry['Inputs'][previous_input_mem[0]]['Decoys'][previous_input_mem[1]]['On_Chain_Decoy_Block_Deltas'])
                #assert transaction_entry['Inputs'][previous_input_mem[0]]['Decoys'][previous_input_mem[1]]['On_Chain_Decoy_Block_Deltas']["0_" + str(num_decoys_found-1)] == transaction_entry['Block_Number'] - transaction_entry['Inputs'][previous_input_mem[0]]['Ring_Members'][previous_input_mem[1]]['block_no']
                previous_input_mem = (Input_Pos, Input_Member_Idx)
                num_decoys_found = 1
            #  Edge case where the last result would get skipped
            elif result_idx+1 == len(results):
                transaction_entry['Inputs'][previous_input_mem[0]]['Decoys'][previous_input_mem[1]]['Number_Of_On_Chain_Decoys'] = len(transaction_entry['Inputs'][previous_input_mem[0]]['Decoys'][previous_input_mem[1]]['On_Chain_Decoy_Block_Deltas'])
            #  If the input key does not exist in the dictionary, add it
            if Input_Member_Idx not in transaction_entry['Inputs'][Input_Pos]['Decoys'].keys():
                transaction_entry['Inputs'][Input_Pos]['Decoys'][Input_Member_Idx] = {}
                transaction_entry['Inputs'][Input_Pos]['Decoys'][Input_Member_Idx]['On_Chain_Decoy_Block_Deltas'] = {}
            #  Calculate the block difference between the first occurrence and the decoy found on chain
            transaction_entry['Inputs'][Input_Pos]['Decoys'][Input_Member_Idx]['On_Chain_Decoy_Block_Deltas']["0_" + str(num_decoys_found)] = Block_B - Block_A


    # Calculate lengths
    transaction_entry['Num_Inputs'] = len(transaction_entry['Inputs'])
    transaction_entry['Num_Outputs'] = len(transaction_entry['Outputs']['Output_Data'])
    transaction_entry['Block_To_xmr2csv_Time_Delta'] = int((datetime.fromtimestamp(transaction_entry['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch'])).total_seconds())

    # Temporal Features
    if len(transaction_entry['Inputs']) != 0:
        for input_idx, each_input in enumerate(transaction_entry['Inputs']):
            transaction_entry['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'] = {}
            #  A place to store the block times of each ring member
            ring_mem_times = []
            if len(each_input['Ring_Members']) != 0:
                for ring_num, ring_mem in enumerate(each_input['Ring_Members']):
                    ring_mem_times.append(get_xmr_block(str(ring_mem['block_no']))['timestamp'])
                    #  If the list has at least 2 items
                    if len(ring_mem_times) > 1:
                        time_delta = int((datetime.fromtimestamp(ring_mem_times[ring_num]) - datetime.fromtimestamp(ring_mem_times[ring_num - 1])).total_seconds())
                        transaction_entry['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'][str(ring_num-1) + '_' + str(ring_num)] = time_delta
            if len(ring_mem_times) > 1:
                # Add temporal features
                #  Calculate the total time span of the ring signature ( the newest ring on chain block time - oldest ring on chain block time )
                transaction_entry['Inputs'][input_idx]['Total_Ring_Time_Span'] = int((datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1]) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                #  Calculate the time between the newest ring in the signature to the block time of the transaction
                transaction_entry['Inputs'][input_idx]['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1])).total_seconds())
                #  Calculate the time between the oldest ring in the signature to the block time of the transaction
                transaction_entry['Inputs'][input_idx]['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                #  Calculate the mean of the ring time
                transaction_entry['Inputs'][input_idx]['Mean_Ring_Time'] = int(sum(ring_mem_times) / len(ring_mem_times)) - ring_mem_times[0]
                #  Calculate the median of the ring time
                transaction_entry['Inputs'][input_idx]['Median_Ring_Time'] = int(median(ring_mem_times)) - ring_mem_times[0]

    # Move labels to Input dictionary (This is kinda jank but it's the best way I can think of)
    for input_key_image, true_ring_position in transaction_entry['Input_True_Rings'].items():
        #  Match the true spent ring's key image to one of the inputs
        for each_input in range(len(transaction_entry['Inputs'])):
            if transaction_entry['Inputs'][each_input]['Key_Image'] == input_key_image:
                #  add a field for the input for the true ring spent
                transaction_entry['Inputs'][each_input]['Ring_no/Ring_size'] = true_ring_position
    #  Delete the temporary dict() holding the true ring positions
    del transaction_entry['Input_True_Rings']
    return tx_hash, transaction_entry


def combine_files(Wallet_info):
    """

    :param Wallet_info:
    :return:
    """
    Wallet_addr = Wallet_info[0]
    Wallet_dir = Wallet_info[1]
    wallet_tx_data = {}

    #  Do some error checking, make sure the file exists
    if exists(Wallet_dir + "/cli_export_" + Wallet_addr + ".csv"):
        #  Open the file and get the number of lines
        with open(Wallet_dir + "/cli_export_" + Wallet_addr + ".csv", "r") as f:
            #  If the file only has 1 line than it's just the csv header and the wallet had no transactions
            if len(f.readlines()) > 1:
                # If there is transactions open the file and start parsing
                #  CSV HEADER -> "block, direction, unlocked, timestamp, amount, running balance, hash, payment ID, fee, destination, amount, index, note"
                #                   0        1          2         3         4           5           6        7       8         9        10      11    12
                with open(Wallet_dir + "/cli_export_" + Wallet_addr + ".csv", "r") as fp:
                    next(fp)  # Skip header of csv
                    for line in fp:
                        cli_csv_values = line.split(",")
                        if cli_csv_values[1].strip() == "out":  # Only add outgoing transactions to the dataset
                            #  Check if the hash is a key in the dataset
                            if cli_csv_values[6].strip() not in wallet_tx_data.keys():
                                transaction = {}
                                transaction['Block_Number'] = int(cli_csv_values[0].strip())
                                transaction['Direction'] = cli_csv_values[1].strip()
                                transaction['Block_Timestamp'] = cli_csv_values[3].strip()
                                # Convert timestamp to epoch time
                                p = "%Y-%m-%d %H:%M:%S"
                                epoch = datetime(1970, 1, 1)
                                transaction['Block_Timestamp_Epoch'] = int((datetime.strptime(transaction['Block_Timestamp'].strip(), p) - epoch).total_seconds())

                                transaction['Amount'] = float(cli_csv_values[4].strip())
                                transaction['Wallet_Balance'] = float(cli_csv_values[5].strip())
                                transaction['Tx_Fee'] = float(cli_csv_values[8].strip())
                                transaction['Destination_Address'] = cli_csv_values[9].strip()
                                transaction['Sender_Address'] = Wallet_addr
                                transaction['Network'] = NETWORK

                                transaction['Outputs'] = {}
                                transaction['Outputs']['Output_Data'] = list()
                                transaction['Inputs'] = []

                                #  Add the time that xmr2csv was run
                                with open(Wallet_dir + "/xmr2csv_start_time_" + Wallet_addr + ".csv", "r") as fp2:
                                    for line2 in fp2:
                                        transaction['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                                        break
                                #  Add the transaction
                                wallet_tx_data[cli_csv_values[6].strip()] = transaction

                #  CSV HEADER -> "Timestamp,Block_no,Tx_hash,Tx_public_key,Tx_version,Payment_id,Out_idx,Amount,Output_pub_key,Output_key_img,Output_spend"
                #                    0         1        2           3           4          5        6       7         8               9             10
                with open(Wallet_dir + "/xmr_report_" + Wallet_addr + ".csv", "r") as fp:
                    next(fp)  # Skip header of csv
                    for line in fp:
                        xmr2csv_report_csv_values = line.split(",")
                        tx_hash = xmr2csv_report_csv_values[2].strip()
                        #  Check if the tx hash is in the dataset yet
                        if tx_hash in wallet_tx_data.keys():
                            wallet_tx_data[tx_hash]['Tx_Version'] = float(xmr2csv_report_csv_values[4].strip())
                            wallet_tx_data[tx_hash]['Tx_Public_Key'] = xmr2csv_report_csv_values[3].strip()
                            wallet_tx_data[tx_hash]['Output_Pub_Key'] = xmr2csv_report_csv_values[8].strip()
                            wallet_tx_data[tx_hash]['Output_Key_Img'] = xmr2csv_report_csv_values[9].strip()
                            wallet_tx_data[tx_hash]['Out_idx'] = int(xmr2csv_report_csv_values[6].strip())
                            wallet_tx_data[tx_hash]['Wallet_Output_Number_Spent'] = int(xmr2csv_report_csv_values[10].strip())
                            #  Add Output Information
                            out_tx = get(API_URL + "/transaction/" + str(tx_hash)).json()
                            try:
                                assert out_tx['status'] != "fail"
                            except AssertionError as e:
                                print(red + "Error: Transaction lookup failed" + reset)
                                exit(1)
                            output_info = out_tx["data"]['outputs']
                            for output_idx, output in enumerate(output_info):
                                wallet_tx_data[tx_hash]['Outputs']['Output_Data'].append({'Amount': output['amount'], 'Stealth_Address': output['public_key']})

                            #  Open the file that has the timestamp from when the data was collected
                            with open(Wallet_dir + "/xmr2csv_start_time_" + Wallet_addr + ".csv", "r") as fp2:
                                for line2 in fp2:
                                    wallet_tx_data[tx_hash]['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                                    break

                            #  Search through the export of all ring member occurrences on chain to see if our output public key was used
                            #  CSV HEADERS -> "Timestamp, Block_no, Decoy_Tx_hash, Output_pub_key, Key_image, ring_no/ring_size"
                            #                      0          1            2               3            4            5
                            # with open(Wallet_dir + "/xmr_report_ring_members_" + Wallet_addr + ".csv", "r") as fp2:
                            #     next(fp2)  # Skip header of csv

                #  CSV HEADERS -> "Timestamp, Block_no, Tx_hash, Output_pub_key, Key_image, Ring_no/Ring_size"
                #                      0          1        2            3            4              5
                with open(Wallet_dir + "/xmr_report_outgoing_txs_" + Wallet_addr + ".csv", "r") as fp:
                    next(fp)  # Skip header of csv
                    for line in fp:
                        xmr2csv_outgoing_csv_values = line.split(",")
                        #  Make sure the hash exists in the dataset
                        if xmr2csv_outgoing_csv_values[2].strip() in wallet_tx_data.keys():
                            #  Check if there is a dictionary to keep track of input true spends (labels)
                            if 'Input_True_Rings' not in wallet_tx_data[xmr2csv_outgoing_csv_values[2].strip()].keys():
                                wallet_tx_data[xmr2csv_outgoing_csv_values[2].strip()]['Input_True_Rings'] = {}
                            #  Set the key image as the dictionary key and 'Ring_no/Ring_size' as the value
                            wallet_tx_data[xmr2csv_outgoing_csv_values[2].strip()]['Input_True_Rings'][xmr2csv_outgoing_csv_values[4].strip()] = xmr2csv_outgoing_csv_values[5].strip()
            else:
                print(yellow + "Warning: " + reset + str(Wallet_dir) + " did not contain any transactions!")
    return wallet_tx_data


def discover_wallet_directories(dir_to_search):
    """

    :param dir_to_search:
    :return:
    """
    # ERROR Checking if the directory is empty or not
    try:
        if len(listdir(dir_to_search)) == 0:
            print(red + "Error: {} is an empty directory!".format(dir_to_search) + reset)
            exit(1)
    except FileNotFoundError as e:
        print(red + "Error: {} is a non-existent directory!".format(dir_to_search) + reset)
        exit(1)

    #  Make sure the user ran collect.sh before create_dataset.py
    pathname = dir_to_search + "/**/*.csv"
    files = glob(pathname, recursive=True)
    if len(files) == 0:
        print(red + "Error: No CSV files detected. Make sure you run collect.sh first!" + reset)
        exit(1)

    # traverse root directory, and list directories as dirs and files as files
    unique_directories = []
    for root, dirs, files in walk(dir_to_search):
        for name in files:
            #  Find all csv files
            if name.lower().endswith(".csv"):
                #  Find all the unique folders holding csv files
                if root not in unique_directories:
                    unique_directories.append(root)
    cwd = getcwd()  # Set a starting directory

    Wallet_addrs = []
    Wallet_info = []
    #  Go through each directory that has csv files in it
    for idx, dir in tqdm(enumerate(unique_directories), desc="Enumerating Wallet Folders", total=len(unique_directories), colour='blue'):
        chdir(dir)
        #  Iterate over the files in the directory
        for root, dirs, files in walk("."):
            for name in files:  # Get the file name
                #  Get each csv file
                if name.lower().endswith(".csv"):
                    #  Extract the 2 unique wallet addresses from the name of the files
                    addr = name[::-1].split(".")[1].split("_")[0][::-1]
                    if addr not in Wallet_addrs:
                        Wallet_info.append([addr, dir])
                        Wallet_addrs.append(addr)
                    #  Dont keep looking if the two wallet addresses are already found
                    if len(Wallet_addrs) == 2:
                        break
        chdir(cwd)
    chdir(cwd)

    del Wallet_addrs  # Not needed anymore
    collect()  # Garbage Collector

    global data  # Import the global database
    total_txs = 0
    num_bad_txs = 0
    with Manager() as manager:
        with manager.Pool(processes=NUM_PROCESSES) as pool:
            # Multiprocess combining the 6 csv files for each wallet
            for wallet_tx_data in tqdm(pool.imap_unordered(func=combine_files, iterable=Wallet_info), desc="(Multiprocessing) Combining Exported Wallet Files", total=len(Wallet_info), colour='blue'):
                #  Make sure there are transactions in the data before adding it to the dataset
                for tx_hash, tx_data in wallet_tx_data.items():
                    if "Input_True_Rings" in tx_data.keys() and len(tx_data["Input_True_Rings"]) > 0:
                        data[tx_hash] = tx_data
                        total_txs += 1
                    else:
                        num_bad_txs += 1
    print("There were " + str(num_bad_txs) + " bad transactions that were deleted out of a total " + str(total_txs+num_bad_txs) + " transactions!")
    print("The dataset now includes " + str(len(data)) + " transactions.")


def clean_transaction(transaction):
    """
    A transaction from the original dataset contains information not
    necessarily useful for training a machine learning model. This
    information includes cryptographically random strings ( wallet
    addresses, and private keys ) as well as human-readable strings.
    This function will also strip any "deanonymized" features and
    return them in a separate dictionary to be added to the labels.
    :param transaction: A dictionary of transaction information
    :return: A dictionary of labels associated to the inputted transaction
    """
    private_info = {}
    del transaction['Tx_Version']
    del transaction['Block_Number']
    del transaction['Block_Timestamp_Epoch']
    del transaction['Num_Confirmations']
    private_info['True_Ring_Pos'] = {}
    del transaction['Direction']
    del transaction['Block_Timestamp']
    private_info['Tx_Amount'] = transaction['Amount']
    del transaction['Amount']
    private_info['Wallet_Balance'] = transaction['Wallet_Balance']
    del transaction['Wallet_Balance']
    del transaction['Destination_Address']
    del transaction['Sender_Address']
    del transaction['Network']
    del transaction['Outputs']
    for idx, input in enumerate(transaction['Inputs']):
        del input['Key_Image']
        del input['Amount']
        del input['Ring_Members']
        private_info['True_Ring_Pos'][idx] = input['Ring_no/Ring_size']
        del input['Ring_no/Ring_size']
    del transaction['xmr2csv_Data_Collection_Time']
    del transaction['Tx_Public_Key']
    del transaction['Output_Pub_Key']
    del transaction['Output_Key_Img']
    private_info['Out_idx'] = transaction['Out_idx']
    del transaction['Out_idx']
    private_info['Wallet_Output_Number_Spent'] = transaction['Wallet_Output_Number_Spent']
    del transaction['Wallet_Output_Number_Spent']
    del transaction['Payment_ID']
    del transaction['Payment_ID8']
    del transaction['Time_Of_Enrichment']
    del transaction['Tx_Extra']
    del transaction['Block_To_xmr2csv_Time_Delta']
    return private_info


def create_feature_set(database):
    """

    :param database: Nested dictionary of Monero transaction metadata
    :return: A pandas dataframe of the input data and a list of labels
    """
    labels = []
    num_errors = 0
    feature_set = dict()
    num_of_valid_txs = 0  # Incrementer which doesn't count invalid txs
    #  Iterate through each tx hash in the database dict
    for idx, tx_hash in tqdm(enumerate(database.keys()), total=len(database), colour='blue', desc="Cleaning Transactions"):
        #  Pass the transaction ( by reference ) to be stripped of non-features and receive the labels back
        try:
            private_info = clean_transaction(database[tx_hash])
        except Exception as e:
            num_errors += 1
            continue  # Don't process the tx and loop
        assert len(database[tx_hash]['Inputs']) == len(private_info['True_Ring_Pos'])
        num_of_valid_txs += 1
        #  Flatten each transaction and iterate over each feature
        for feature_name, feature_value in CherryPicker(database[tx_hash]).flatten(delim='.').get().items():
            #  Check if the feature name is not already in the feature set
            if feature_name not in feature_set.keys():
                feature_set[feature_name] = []
                #  add any missing values
                for i in range(num_of_valid_txs-1):
                    feature_set[feature_name].append(-1)
                #  Add it as a new feature
                feature_set[feature_name].append(feature_value)
            else:  # If the feature is already in the feature set
                #  Check if there are any transactions that did not have this feature
                if len(feature_set[feature_name]) < num_of_valid_txs:
                    #  Add -1 for those occurrences
                    for i in range(num_of_valid_txs-len(feature_set[feature_name])-1):
                        feature_set[feature_name].append(-1)
                #  Append the feature
                feature_set[feature_name].append(feature_value)
        #  add the labels to the list
        labels.append(private_info)

    print("Number of skipped transactions: " + blue + str(num_errors) + reset)
    assert len(labels) != 0
    del database
    collect()  # Garbage Collector
    feature_set_df = DataFrame.from_dict(feature_set, orient='index').transpose()
    feature_set_df.fillna(-1, inplace=True)

    del feature_set
    collect()  # Garbage collector

    #  Sanity check
    assert len(labels) == len(feature_set_df)

    # Combine dataframes together
    # https://www.confessionsofadataguy.com/solving-the-memory-hungry-pandas-concat-problem/
    #feature_set = concat(Valid_Transactions, axis=0).fillna(-1)

    #  Shuffle the data
    feature_set_df, labels = shuffle(feature_set_df, labels, random_state=101)
    #  Reset the indexing after the shuffles
    feature_set_df.reset_index(drop=True, inplace=True)
    return feature_set_df, labels


def undersample_processing(y, series, min_occurrences, occurrences, predicting):
    new_y = []
    new_X = []
    y_idx, ring_array = y

    #  For each array of ring members iterate over each index
    for ring_array_idx in range(len(ring_array["True_Ring_Pos"])):
        #  Make a copy of the data since we need to delete portions of it
        temp_series = series.copy(deep=True)
        #  Get the true ring position (label) for the current iteration
        ring_pos = int(ring_array["True_Ring_Pos"][ring_array_idx].split("/")[0])
        total_rings = int(ring_array["True_Ring_Pos"][ring_array_idx].split("/")[1])
        #  Check to see if we hit the maximum number of labels for this position and that the number of ring members is what we expect.
        if predicting or (occurrences[ring_pos] < min_occurrences and total_rings == NUM_RING_MEMBERS):
            occurrences[ring_pos] = occurrences[ring_pos] + 1
            #  https://stackoverflow.com/questions/57392878/how-to-speed-up-pandas-drop-method
            #  Check if the column name has data relating to irrelevant ring signatures and Delete the columns
            temp_series.drop([column for column in temp_series.index if column.startswith("Inputs.") and not column.startswith("Inputs." + str(ring_array_idx) + ".")], inplace=True)
            #  Check if the column name is for the current ring signature
            #  Rename the column such that it doesn't have the .0. or .1. positioning information
            temp_series.rename({column: column.replace("Inputs." + str(ring_array_idx) + ".", "Input.", 1) for column in temp_series.index if column.startswith("Inputs." + str(ring_array_idx) + ".")}, inplace=True)
            #  Add to the new X and y dataframes
            new_X.append(temp_series)
            new_y.append(ring_pos)

    return new_X, new_y


def undersample(X, y, predicting):
    """

    :param X:
    :param y:
    :return:
    """
    #  Flatten the ring signature labels into a list
    flattened_true_spend = []
    for ring_array in y:
        for idx, true_ring_pos in ring_array["True_Ring_Pos"].items():
            flattened_true_spend.append(int(true_ring_pos.split("/")[0]))
    #  Count the amount of true labels at each position in the ring signature
    labels_distribution = Counter(flattened_true_spend)
    print("Total number of ring signatures in the dataset: " + blue + str(len(flattened_true_spend)) + reset)
    del flattened_true_spend, true_ring_pos # Free up RAM

    # Error checking
    try:
        #  Make sure that there are no classes with 0 labels
        assert len(labels_distribution) == NUM_RING_MEMBERS
    except AssertionError as e:
        print(red + "Error: The dataset contains at least one class which has 0 labels! Undersampling not possible.")
        print(labels_distribution)
        print(reset)
        exit(1)

    #  Find the smallest number of occurrences
    min_occurrences = labels_distribution.most_common()[len(labels_distribution)-1][1]
    print("Undersampling to " + blue + str(min_occurrences) + reset + " transactions per class. A total of " + blue + str(min_occurrences*NUM_RING_MEMBERS) + reset + " transactions.\n")
    #max_occurrences = labels_distribution.most_common(1)[0][1]
    del labels_distribution  # Free up RAM

    #  Get an enumerated list of tuples of the labels
    enumerated_y = list(enumerate(y))
    collect()  # Garbage collector
    enumerated_X = []  # List of pandas series objects
    num_splits = 10  # To reduce ram, partition the dataset into this many sections

    #  Check if the partitioned files do not exist on disk
    if not exists("./Dataset_Files/partitioned_X_1.pkl"):
        #  Iterate over the number of rows in the dataset
        for _ in tqdm(range(len(enumerated_y)), desc="Convert Dataset into List of Pandas Series", total=len(enumerated_y), colour='blue'):
            enumerated_X.append(X.iloc[0])  # Grab the first record in the dataset -> returned as Series -> append to list
            X = X[1:]  # Delete the first row from the dataset to reduce ram
        del X  # Remove the old dataset to save RAM
        collect()  # Garbage collector
        #  Calculate the number of files to add to each partition
        split = len(enumerated_X)//num_splits
        #  Iterate over the number of splits
        for i in range(1, num_splits+1):
            #  Save the partitioned number of X values
            with open("./Dataset_Files/partitioned_X_" + str(i) + ".pkl", "wb") as fp:
                if i == 1:  # if it is the first partition
                    pickle.dump(enumerated_X[:split], fp)
                elif i == num_splits:  # if it is the last partition
                    pickle.dump(enumerated_X[split * (i-1):], fp)
                else:  # if it is a middle partition
                    pickle.dump(enumerated_X[split * (i-1):split*i], fp)
            #  Save the paritioned number of y values
            with open("./Dataset_Files/partitioned_y_" + str(i) + ".pkl", "wb") as fp:
                if i == 1:  # if it is the first partition
                    pickle.dump(enumerated_y[:split], fp)
                elif i == num_splits:  # if it is the last partition
                    pickle.dump(enumerated_y[split * (i-1):], fp)
                else:  # if it is a middle partition
                    pickle.dump(enumerated_y[split * (i-1):split*i], fp)
            print(blue + "./Dataset_Files/partitioned_X_" + str(i) + ".pkl" + reset + " and " + blue + "./Dataset_Files/partitioned_y_" + str(i) + ".pkl" + reset + " written to disk!")
    else:
        del X  # Remove the old dataset to save RAM
        collect()  # Garbage collector
    print()

    new_y = []  # List of final labels
    new_X = []  # Undersampled list of Pandas Series
    #  Create a dictionary for all 11 spots in a ring signature
    occurrences = {}
    for i in range(NUM_RING_MEMBERS):  # Populate an entry for each possible label
        occurrences[i + 1] = 0
    file_idx = 1
    tx_count = 0
    #  While the number of samples added is less than the number of total needed undersampled values...
    while (predicting and file_idx <= num_splits) or (sum(list(occurrences.values())) < (min_occurrences * NUM_RING_MEMBERS) and file_idx <= num_splits):
        #  Open the next partitioned X and y files
        with open("./Dataset_Files/partitioned_X_" + str(file_idx) + ".pkl", "rb") as fp:
            enumerated_X = pickle.load(fp)
        with open("./Dataset_Files/partitioned_y_" + str(file_idx) + ".pkl", "rb") as fp:
            enumerated_y = pickle.load(fp)
        assert len(enumerated_X) == len(enumerated_y)  # Error check
        file_idx += 1
        for idx in tqdm(
                    iterable=range(len(enumerated_y)),
                    desc="Undersampling Dataset (Part " + str(file_idx - 1) + ")",
                    total=len(enumerated_y),
                    colour='blue'
                    ):
            #  Error checking to make sure the partitioned X and y data matches the original
            for i, ring_pos in enumerated_y[idx][1]['True_Ring_Pos'].items():
                assert ring_pos == y[tx_count]['True_Ring_Pos'][i]
            result = undersample_processing(enumerated_y[idx], enumerated_X[idx], min_occurrences, occurrences, predicting)
            assert len(result[0]) == len(result[1])
            if result[0] and result[1]:
                #  Add to the new X and y dataframes
                new_X = new_X + result[0]
                new_y = new_y + result[1]
            tx_count += 1
        del enumerated_X
        del enumerated_y
        collect()
        if sum(list(occurrences.values())) != 0:
            print("Number of Undersampled Ring Signatures: " + blue + str(sum(list(occurrences.values()))) + reset)
    # Combine the list of series together into a single DF
    undersampled_X = DataFrame(new_X)
    del new_X, y  # Free up RAM
    collect()  # Garbage collector
    #  Fill Nan values to be -1 and reset indexing
    undersampled_X.fillna(-1, inplace=True)
    undersampled_X.reset_index(drop=True, inplace=True)

    #  Error Checking
    if not predicting:
        assert len(undersampled_X) == len(new_y) == (min_occurrences * NUM_RING_MEMBERS)
        for _, class_occurrences in Counter(new_y).items():
            try:
                assert class_occurrences == min_occurrences
            except AssertionError as e:
                print("A class had a number of samples which did not equal the undersampled number of occurrences.")
                print(Counter(new_y).items())
                exit(1)
    else:
        assert len(undersampled_X) == len(new_y)

    # Shuffle the data one last time and reset the indexing
    undersampled_X, undersampled_y = shuffle(undersampled_X, new_y, random_state=101)
    undersampled_X.reset_index(drop=True, inplace=True)
    return undersampled_X, undersampled_y


def write_dict_to_csv(data_dict):
    """

    :param data_dict:
    :return:
    """
    #  Keep track of all column names for the CSV
    column_names = []
    with open("./Dataset_Files/dataset.csv", "a") as fp:
        fp.write("HEADERS"+"\n")  # Keep a temp placeholder for the column names
        first_tx = True
        #  Iterate over each tx hash
        for tx_hash in tqdm(iterable=data_dict.keys(), total=len(data_dict.keys()), colour='blue', desc="Writing Dataset to Disk as a CSV"):
            #  Flatten the transaction dictionary
            tx_metadata = CherryPicker(data_dict[tx_hash]).flatten(delim='.').get()
            column_values = []
            #  For the first tx add the entire transaction
            if first_tx:
                column_names = column_names + list(tx_metadata.keys())
                column_values = column_values + [str(element) for element in list(tx_metadata.values())]
                fp.write(','.join(column_values) + "\n")
                first_tx = False
                continue
            #  Iterate over each name of the transaction
            for name in tx_metadata.keys():
                #  Check if the name is already in column names
                if name not in column_names:
                    column_names.append(name)
            value_orders = []
            #  Iterate over the names of the transaction
            for idx, name in enumerate(list(tx_metadata.keys())):
                #  Find the index of the name in column_names and add it to value_orders
                value_orders.append(column_names.index(name))
            #  Sort the transaction values by the order of the indexes in value_orders
            sorted_values = sorted(zip(value_orders, list(tx_metadata.values())))
            max_sorted_val = max(sorted_values)[0]
            sorted_val_idx = 0
            #  Iterate over the length of the column_names to add the sorted values
            for column_idx in range(len(column_names)):
                #  If the column number is greater than the max, add a placeholder
                if column_idx > max_sorted_val:
                    fp.write(',')
                    continue
                #  Check if the sorted idx is not the column name index
                if sorted_values[sorted_val_idx][0] != column_idx:
                    fp.write(',')
                    continue
                else:
                    fp.write(str(sorted_values[sorted_val_idx][1]) + ",")  # Add the value
                    sorted_val_idx += 1
            assert sorted_val_idx == len(sorted_values)
            fp.write("\n")
            fp.flush()  # https://stackoverflow.com/questions/3167494/how-often-does-python-flush-to-a-file
            fsync(fp.fileno())
    #  I looked everywhere and there is no way to replace the top line of a
    #  file in python without loading the entire file into RAM. So syscall it is...
    system("sed -i '1,2s|HEADERS|" + ", ".join(column_names) + "|g' ./Dataset_Files/dataset.csv")


def validate_data_integrity(X, y, undersampled=False):
    print(blue + "\nData Integrity Check" + reset)
    if undersampled:
        #  We assume that the dataset.json contains identical data to X.pkl
        with open("./Dataset_Files/X.pkl", "rb") as fp:
            original_data = pickle.load(fp)
        with open("./Dataset_Files/y.pkl", "rb") as fp:
            original_labels = pickle.load(fp)
        X_Undersampled = X
        y_Undersampled = y
        bad = 0
        good = 0
        total = 0
        not_found = 0
        #  Make sure there are no duplicate rows
        ring_member_columns = [name for name in original_data.columns if "Mean_Ring_Time" in name]
        for each_idx in tqdm(range(len(X_Undersampled)), total=len(X_Undersampled), colour='blue', desc="Validating Undersampled Dataset"):
            find_undersampled_mean_idx = X_Undersampled['Input.Mean_Ring_Time'][each_idx]
            find_undersampled_tx_delta_idx = X_Undersampled['Input.Previous_Tx_Time_Deltas.0'][each_idx]
            find_undersampled_tx_delta_idx_1 = X_Undersampled['Tx_Fee'][each_idx]
            for column_idx, column_name in enumerate(ring_member_columns):
                input_num = int(column_name.split(".")[1])
                list_of_matched_mean_idx = original_data.index[(original_data[column_name] == find_undersampled_mean_idx)].to_numpy()
                list_of_matched_mean_idx2 = original_data.index[(original_data['Inputs.' + str(input_num) + '.Previous_Tx_Time_Deltas.0'] == find_undersampled_tx_delta_idx)].to_numpy()
                list_of_matched_mean_idx3 = original_data.index[(original_data['Tx_Fee'] == find_undersampled_tx_delta_idx_1)].to_numpy()
                list_of_matches = intersect1d(list_of_matched_mean_idx, list_of_matched_mean_idx2, assume_unique=True)
                final_matches = list(intersect1d(list_of_matches, list_of_matched_mean_idx3, assume_unique=True))
                if final_matches and len(final_matches) == 1:
                        total += 1

                        if int(original_labels[final_matches[0]]['True_Ring_Pos'][input_num].split("/")[0]) == y_Undersampled[each_idx]:
                            good += 1
                        else:
                            bad += 1
                            print(each_idx)
                            print(final_matches[0])
                            print(original_labels[final_matches[0]]['True_Ring_Pos'])
                            print(y_Undersampled[each_idx])
                        break
                else:
                    if column_idx+1 == len(ring_member_columns):
                        not_found += 1
        print("=============================")
        print("|| Total Dataset Ring Signatures: " + blue + str(total) + reset)
        print("|| Total Undersampled Samples: " + blue + str(len(X_Undersampled)) + reset)
        print("|| Undersampled Validated Samples: " + blue + str(good) + reset)
        print("|| Undersampled Bad Samples: " + red + str(bad) + reset)
        print("|| Undersampled Samples Not Found: " + red + str(not_found) + reset)
        if (total / good * 100) == 100 and total == len(X_Undersampled):
            print("|| " + green + "100% data integrity!" + reset)
        else:
            print("|| " + red + "ERROR: " + str(round((total/good*100)-100, 2)) + "% data corruption!" + reset)
            if total != len(X_Undersampled):
                print("|| " + red + "ERROR: Only checked " + str(total) + " of " + str(len(X_Undersampled)) + " total samples!" + reset)
    else:
        with open("./Dataset_Files/dataset.json", "r") as fp:
            original_data = json.load(fp)
        bad = 0
        good = 0
        skip = 0
        total = 0
        checked_samples = 0
        #  Make sure there are no duplicate rows
        assert len(X[X.duplicated()]) == 0
        #  Get each dict of data values
        for i, val in tqdm(enumerate(original_data.values()), total=len(original_data), colour='blue', desc="Validating Dataset"):
            #  Iterate over each ring signature
            for input_num in range(len(val['Inputs'])):
                total += 1
                #  check if the median ring time is not null
                mean_ring_time = val['Inputs'][input_num]['Mean_Ring_Time']
                med_ring_time = val['Inputs'][input_num]['Median_Ring_Time']
                #  Find all occurrences of the median ring time in the undersampled dataset
                find_undersampled_mean_idx = X.index[X['Inputs.' + str(input_num) + '.Mean_Ring_Time'] == mean_ring_time].tolist()
                find_undersampled_med_idx = X.index[X['Inputs.' + str(input_num) + '.Median_Ring_Time'] == med_ring_time].tolist()
                #  Check if there were occurrences
                if find_undersampled_mean_idx and find_undersampled_med_idx:
                    if len(find_undersampled_mean_idx) == 1 and len(find_undersampled_med_idx) == 1 and find_undersampled_mean_idx[0] == find_undersampled_med_idx[0]:
                        checked_samples += 1
                        undersample_index = find_undersampled_mean_idx[0]
                        ground_truth = int(val['Inputs'][input_num]['Ring_no/Ring_size'].split("/")[0])
                        if input_num >= len(y[undersample_index]['True_Ring_Pos']):
                            bad += 1
                            print(input_num)
                        elif ground_truth == int(y[undersample_index]['True_Ring_Pos'][input_num].split('/')[0]):
                            good += 1
                        elif ground_truth != int(y[undersample_index]['True_Ring_Pos'][input_num].split('/')[0]):
                            bad += 1
                else:
                    skip += 1
        print("=============================")
        print("|| Total Dataset Ring Signatures: " + blue + str(total) + reset)
        print("|| Total Checked Samples: " + blue + str(checked_samples) + reset)
        print("|| Validated Samples: " + blue + str(good) + reset)
        print("|| Bad Samples: " + red + str(bad) + reset)
        print("|| Dataset Skipped Samples: " + red + str(skip) + reset)
        if (checked_samples / good * 100) == 100:
            print("|| " + green + "100% data integrity!" + reset)
        else:
            print("|| " + red + "ERROR: " + str(round((checked_samples / good * 100)-100, 2)) + "% data corruption!" + reset)
            exit(1)
    print()
    del original_data  # Free up RAM


def delete_file(list_of_paths):
    for path in list_of_paths:
        if exists(path):
            remove(path)


def main():
    ############################
    #      Error Checking      #
    ############################
    # Error Checking for command line args
    if len(argv) != 2:
        print("Usage Error: ./create_dataset.py < Wallets Directory Path >")
        exit(1)
    try:  # Check to see if the API URL given can be connected
        assert get(API_URL + "/block/1").status_code == 200
    except ConnectionError as e:
        print("Error: " + red + NETWORK + reset + " block explorer located at " + API_URL + " refused connection!")
        exit(1)

    # Check if the user set up the block explorer correctly
    try:
        get(API_URL + "/networkinfo")  # For some reason the first request fails sometimes but the second request doesnt
        assert get(API_URL + "/networkinfo").json()["data"] is not None and get(API_URL + "/networkinfo").json()["data"][NETWORK]
    except AssertionError as e:
        print(red + "Error: The block explorer is not configured for " + NETWORK + "!" + reset)
        exit(1)

    #  Check if the postgres database is set up
    try:
        _ = psycopg2.connect("host=" + POSTGRES_SQL_HOST + " port=" + POSTGRES_SQL_PORT + " dbname=" + POSTGRES_SQL_DB_NAME + " user=" + POSTGRES_SQL_USERNAME + " password=" + POSTGRES_SQL_PASSWORD)
    except psycopg2.OperationalError as e:
        print(red + "ERROR: Connection to PostgresSQL Database Failed!" + reset)
        exit(1)

    # Configuration alert
    print("The dataset is being collected for the " + blue + NETWORK + reset + " network using " + API_URL + " as a block explorer!")

    if len(glob("./Dataset_Files/*")) > 0:
        while True:
            answer = input(blue + "Dataset files exists already. Delete all of them? (y/n) " + reset)
            if answer.lower()[0] == "y":
                delete_file(glob("./Dataset_Files/*"))
                break
            elif answer.lower()[0] == "n":
                break

    ###########################################
    #  Create the dataset from files on disk  #
    ###########################################
    global data
    print(blue + "Opening " + str(argv[1]) + reset)
    #  Find where the wallets are stored and combine the exported csv files
    discover_wallet_directories(argv[1])

    #  Multiprocessing References
    #  https://leimao.github.io/blog/Python-tqdm-Multiprocessing/
    #  https://thebinarynotes.com/python-multiprocessing/
    #  https://docs.python.org/3/library/multiprocessing.html
    #  https://stackoverflow.com/questions/6832554/multiprocessing-how-do-i-share-a-dict-among-multiple-processes
    with Manager() as manager:
        #  Multiprocessing enriching each transaction
        with manager.Pool(processes=NUM_PROCESSES) as pool:
            for result in tqdm(pool.imap_unordered(func=enrich_data, iterable=list(data.items())), desc="(Multiprocessing) Enriching Transaction Data", total=len(data), colour='blue'):
                tx_hash, transaction_entry = result[0], result[1]  # Unpack the values returned
                data[tx_hash] = transaction_entry  # Set the enriched version of the tx
    with open("./Dataset_Files/dataset.json", "w") as fp:
        json.dump(data, fp)
    print("./Dataset_Files/dataset.json written to disk!")

    #################################
    #  Remove Unnecessary Features  #
    #################################
    with open("./Dataset_Files/dataset.json", "r") as fp:
        data = json.load(fp)

    #  Write the dictionary to disk as a CSV
    write_dict_to_csv(data)

    #  Feature selection on raw dataset
    X, y = create_feature_set(data)
    del data
    collect()  # Garbage collector
    validate_data_integrity(X, y, undersampled=False)

    #  Save data and labels to disk for future AI training
    with open("./Dataset_Files/X.pkl", "wb") as fp:
        pickle.dump(X, fp)
    X.to_csv('./Dataset_Files/X.csv', index=False, header=True)
    with open("./Dataset_Files/y.pkl", "wb") as fp:
        pickle.dump(y, fp)
    #  Error checking; labels and data should be the same length
    assert len(X) == len(y)
    print(blue + "./Dataset_Files/X.pkl" + reset + ", " + blue + "./Dataset_Files/X.csv" + reset + ", and " + blue + "./Dataset_Files/y.pkl" + reset + " were written to disk!")

    ###################
    #  Undersampling  #
    ###################
    with open("./Dataset_Files/X.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("./Dataset_Files/y.pkl", "rb") as fp:
        y = pickle.load(fp)

    X_Undersampled, y_Undersampled = undersample(X, y, predicting=False)
    #  Remove any columns which have the same value for every record ( not useful for ML )
    X_Undersampled.drop(list(X_Undersampled.columns[X_Undersampled.nunique() == 1]), axis=1, inplace=True)
    del X, y
    collect()  # Garbage collector

    with open("./Dataset_Files/X_Undersampled.pkl", "wb") as fp:
        pickle.dump(X_Undersampled, fp)
    X_Undersampled.to_csv('./Dataset_Files/X_Undersampled.csv', index=False, header=True)
    with open("./Dataset_Files/y_Undersampled.pkl", "wb") as fp:
        pickle.dump(y_Undersampled, fp)

    validate_data_integrity(X_Undersampled, y_Undersampled, undersampled=True)
    print(blue + "./Dataset_Files/X_Undersampled.pkl" + reset + " and " + blue + "./Dataset_Files/y_Undersampled.pkl" + reset + " written to disk!\nFinished")


if __name__ == '__main__':
    try:
        main()
    # Gracefully exits if user hits CTRL + C
    except KeyboardInterrupt as e:
        print("Error: User stopped the script's execution!")
        exit(1)
    #  All other raised errors, print the stack trace
    except Exception as e:
        import traceback
        print(e)
        print(traceback.print_exc())
        exit(1)

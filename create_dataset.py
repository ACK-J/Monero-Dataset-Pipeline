import json
import pickle
from sys import argv
from time import time
from tqdm import tqdm
from gc import collect
from requests import get
from os.path import exists
from itertools import repeat
from statistics import median
from datetime import datetime
from collections import Counter
from sklearn.utils import shuffle
from cherrypicker import CherryPicker  # https://pypi.org/project/cherrypicker/
from pandas import DataFrame, concat, options
from requests.exceptions import ConnectionError
from multiprocessing import Pool, cpu_count, Manager
from os import walk, getcwd, chdir, listdir, fsync, system, remove
options.mode.chained_assignment = None  # default='warn'

'''
Description: 
Usage: ./create_dataset.py < Wallets Directory Path >
Date: 6/8/2022
Author: ACK-J

Warning: DO NOT run this with a remote node, there are a lot of blockchain lookups and it will be slow!
Warning: Run your own monerod process and block explorer
To run your own block explorer:
    monerod --stagenet                        https://github.com/monero-project/monero
    xmrblocks --stagenet --enable-json-api    https://github.com/moneroexamples/onion-monero-blockchain-explorer
    
'''

######################
#  Global Variables  #
######################
data = {}  # Key = tx hash, val = dict(transaction metadata)
NUM_PROCESSES = cpu_count()  # Set the number of processes for multiprocessing
NETWORK = "testnet"
API_URL = "https://community.rino.io/explorer/" + NETWORK + "/api"  # Remote Monero Block Explorer
API_URL = "http://127.0.0.1:8081/api"  # Local Monero Block Explorer
NUM_RING_MEMBERS = 11  # DL models depend on a fixed number

# Terminal Colors
red = '\033[31m'
blue = "\033[0;34m"
yellow = "\033[1;33m"
reset = '\033[0m'


def get_xmr_block(block_num):
    return get(API_URL + "/block/" + str(block_num)).json()["data"]


def get_xmr_tx(tx_hash):
    return get(API_URL + "/transaction/" + tx_hash).json()["data"]


def enrich_data(tx_dict_item):
    """

    :param tx_dict_item:
    :return:
    """
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

    #  Output info
    for Decoy in transaction_entry['Outputs']['Decoys_On_Chain']:
        #  Add Temporal Features for the decoy ( This takes up a ton of time )
        #  Retrieve the transaction information about the decoy ring signatures
        decoy_tx_response = get_xmr_tx(str(Decoy['Tx_Hash']))
        #  Iterate through each input
        for decoy_input in decoy_tx_response['inputs']:
            #  Create an entry for the temporal data
            Decoy['Time_Deltas_Between_Ring_Members'] = {}
            #  Make sure there is at least 1 mixin
            if len(decoy_input['mixins']) != 0:
                #  A place to store the block times of each ring member
                Ring_Member_Times = []
                #  Iterate through each mixin, add it to the list and calculate the time deltas
                for member_idx, each_member in enumerate(decoy_input['mixins']):
                    Ring_Member_Times.append(get_xmr_block(str(each_member['block_no']))['timestamp'])
                    #  If the list has at least 2 items
                    if len(Ring_Member_Times) > 1:
                        time_delta = int((datetime.fromtimestamp(Ring_Member_Times[member_idx]) - datetime.fromtimestamp(Ring_Member_Times[member_idx - 1])).total_seconds())
                        Decoy['Time_Deltas_Between_Ring_Members'][str(member_idx - 1) + '_' + str(member_idx)] = time_delta
                        # Add temporal features
                        #  Calculate the total time span of the ring signature ( newest ring on chain block time - oldest ring on chain block time )
                        Decoy['Time_Deltas_Between_Ring_Members']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(Ring_Member_Times[len(Ring_Member_Times) - 1]) - datetime.fromtimestamp(Ring_Member_Times[0])).total_seconds())
                        #  Calculate the time between the newest ring in the signature to the block time of the transaction
                        Decoy['Time_Deltas_Between_Ring_Members']['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch']) - datetime.fromtimestamp(Ring_Member_Times[len(Ring_Member_Times) - 1])).total_seconds())
                        #  Calculate the time between the oldest ring in the signature to the block time of the transaction
                        Decoy['Time_Deltas_Between_Ring_Members']['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch']) - datetime.fromtimestamp(Ring_Member_Times[0])).total_seconds())
                        #  Calculate the mean of the ring time
                        Decoy['Time_Deltas_Between_Ring_Members']['Mean_Ring_Time'] = int(sum(Ring_Member_Times) / len(Ring_Member_Times)) - Ring_Member_Times[0]
                        #  Calculate the median of the ring time
                        Decoy['Time_Deltas_Between_Ring_Members']['Median_Ring_Time'] = int(median(Ring_Member_Times)) - Ring_Member_Times[0]

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
        # transaction_entry['Inputs'][input_idx]['Previous_Tx_Decoy_Occurrences'] = {}
        # transaction_entry['Inputs'][input_idx]['Previous_Tx_Decoy_Times'] = {}
        # #  Initialize the occurrences with 0's
        # for each in range(len(input['mixins'])):
        #     transaction_entry['Inputs'][input_idx]['Previous_Tx_Decoy_Occurrences'][str(each)] = 0
        #     transaction_entry['Inputs'][input_idx]['Previous_Tx_Decoy_Times'][str(each)] = []

        # Iterate over each ring in the output
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

            # #  Iterate through each block between where the ring member was created and now
            # for block in range((ring['block_no']+1), transaction_entry['Block_Number']):
            #     #  Get the data for the entire block
            #     temp_block = get_xmr_block(block_cache, str(block))
            #     #  Iterate over each transaction in the block
            #     for tx in temp_block["txs"]:
            #         try:
            #             #  Get the data for each transaction and iterate over the inputs
            #             for each_input in get_xmr_tx(tx_cache, str(tx['tx_hash']))["inputs"]:
            #                 #  For each input iterate over each ring member
            #                 for ring_member in each_input['mixins']:
            #                     #  Check to see if the ring members stealth address matches the current rings
            #                     if ring_member['public_key'] == ring['public_key']:
            #                         transaction_entry['Inputs'][input_idx]['Previous_Tx_Decoy_Occurrences'][str(ring_mem_num)] += 1
            #                         transaction_entry['Inputs'][input_idx]['Previous_Tx_Decoy_Times'][str(ring_mem_num)].append(temp_block['timestamp'])
            #         except TypeError as e:  # If there are no inputs
            #             pass

    # Calculate lengths
    transaction_entry['Num_Inputs'] = len(transaction_entry['Inputs'])
    transaction_entry['Num_Outputs'] = len(transaction_entry['Outputs']['Output_Data'])
    transaction_entry['Num_Output_Decoys'] = len(transaction_entry['Outputs']['Decoys_On_Chain'])
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
        for each_input in transaction_entry['Inputs']:
            if each_input['Key_Image'] == input_key_image:
                #  add a field for the input for the true ring spent
                each_input['Ring_no/Ring_size'] = true_ring_position
    #  Delete the temporary dict() holding the true ring positions
    del transaction_entry['Input_True_Rings']

    #  Temporal features for decoys on chain
    transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain'] = {}
    if len(transaction_entry['Outputs']['Decoys_On_Chain']) != 0:
        #  A place to store the block times of each ring member
        decoys_on_chain_times = []
        for member_idx, each_member in enumerate(transaction_entry['Outputs']['Decoys_On_Chain']):
            decoys_on_chain_times.append(get_xmr_block(str(each_member['Block_Number']))['timestamp'])
            #  If the list has at least 2 items
            if len(decoys_on_chain_times) > 1:
                time_delta = int((datetime.fromtimestamp(decoys_on_chain_times[member_idx]) - datetime.fromtimestamp(decoys_on_chain_times[member_idx - 1])).total_seconds())
                transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain'][str(member_idx-1) + '_' + str(member_idx)] = time_delta
                # Add temporal features
                #  Calculate the total time span of the ring signature ( newest ring on chain block time - oldest ring on chain block time )
                transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(decoys_on_chain_times[0])).total_seconds())
                #  Calculate the time between the newest ring in the signature to the block time of the transaction
                transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Newest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch'])).total_seconds())
                #  Calculate the time between the oldest ring in the signature to the block time of the transaction
                transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Oldest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[0]) - datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch'])).total_seconds())
                #  Calculate the mean of the ring time
                transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Mean_Decoy_Time'] = sum(decoys_on_chain_times) / len(decoys_on_chain_times) - decoys_on_chain_times[0]
                #  Calculate the median of the ring time
                transaction_entry['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Median_Decoy_Time'] = int(median(decoys_on_chain_times)) - decoys_on_chain_times[0]
    return tx_hash, transaction_entry


def combine_files(Wallet_info):
    """

    :param Wallet_info:
    :return:
    """
    Wallet_addr = Wallet_info[0]
    Wallet_dir = Wallet_info[1]
    #  CSV HEADER -> "block, direction, unlocked, timestamp, amount, running balance, hash, payment ID, fee, destination, amount, index, note"
    #                   0        1          2         3         4           5           6        7       8         9        10      11    12
    wallet_tx_data = {}

    #  Do some error checking, make sure the file exists
    if exists(Wallet_dir + "/cli_export_" + Wallet_addr + ".csv"):
        #  Open the file and get the number of lines
        with open(Wallet_dir + "/cli_export_" + Wallet_addr + ".csv", "r") as f:
            #  If the file only has 1 line than it's just the csv header and the wallet had no transactions
            if len(f.readlines()) > 1:
                # If there is transactions open the file and start parsing
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
                                transaction['Outputs']['Decoys_On_Chain'] = []
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
                            output_info = get(API_URL + "/transaction/" + str(tx_hash)).json()["data"]['outputs']
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
                            with open(Wallet_dir + "/xmr_report_ring_members_" + Wallet_addr + ".csv", "r") as fp2:
                                next(fp2)  # Skip header of csv
                                for line2 in fp2:
                                    ring_members_csv_values = line2.split(",")
                                    Ring_Member = {}
                                    #  Iterate through each output from the transaction
                                    for tx_output in wallet_tx_data[tx_hash]['Outputs']['Output_Data']:
                                        #  Check if the ring members public key matches an output in this transaction
                                        if tx_output['Stealth_Address'] == ring_members_csv_values[3].strip():
                                            Ring_Member['Output_Pub_Key'] = ring_members_csv_values[3].strip()
                                            Ring_Member['Block_Number'] = int(ring_members_csv_values[1].strip())
                                            # Convert timestamp to epoch time before saving
                                            #  https://stackoverflow.com/questions/30468371/how-to-convert-python-timestamp-string-to-epoch
                                            p = "%Y-%m-%d %H:%M:%S"
                                            epoch = datetime(1970, 1, 1)
                                            ring_member_epoch_time = int((datetime.strptime(ring_members_csv_values[0].strip(), p) - epoch).total_seconds())
                                            Ring_Member['Block_Timestamp'] = ring_member_epoch_time
                                            Ring_Member['Key_image'] = ring_members_csv_values[4].strip()
                                            Ring_Member['Tx_Hash'] = ring_members_csv_values[2].strip()
                                            Ring_Member['Ring_no/Ring_size'] = ring_members_csv_values[5].strip()
                                            #  Find the relative age of the outputs public key on the chain compared to when xmr2csv was ran
                                            #  The time from when the data was collected minus the decoy block timestamp
                                            Ring_Member['Ring_Member_Relative_Age'] = int((datetime.fromtimestamp(wallet_tx_data[tx_hash]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(Ring_Member['Block_Timestamp'])).total_seconds())

                                            #  CSV HEADERS -> "Output_pub_key, Frequency, Ring_size"
                                            #                         0            1           2
                                            with open(Wallet_dir + "/xmr_report_ring_members_freq_" + Wallet_addr + ".csv", "r") as fp3:
                                                next(fp3)  # Skip header of csv
                                                for line3 in fp3:
                                                    ring_member_freq_csv_values = line3.split(",")
                                                    #  Check if the ring members public key matches the current public key
                                                    if wallet_tx_data[tx_hash]['Output_Pub_Key'] == ring_member_freq_csv_values[0].strip():
                                                        #  Add the amount of times it has been seen on chain
                                                        Ring_Member['Ring_Member_Freq'] = int(ring_member_freq_csv_values[1].strip())
                                            wallet_tx_data[tx_hash]['Outputs']['Decoys_On_Chain'].append(Ring_Member)
                                    #  Only collect 10 decoys found on chain because it gets too resource intensive when
                                    #  calculating all the temporal features for every decoy's ring signatures
                                    if len(wallet_tx_data[tx_hash]['Outputs']['Decoys_On_Chain']) >= 10:
                                        break

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
                    #  Extract the 2 unique wallet addr from the name of the files
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
    pool = Pool(processes=NUM_PROCESSES)  # Multiprocessing pool
    # Multiprocess combining the 6 csv files for each wallet
    for wallet_tx_data in tqdm(pool.imap_unordered(func=combine_files, iterable=Wallet_info), desc="(Multiprocessing) Combining Exported Wallet Files", total=len(Wallet_info), colour='blue'):
        #  Make sure there are transactions in the data before adding it to the dataset
        for tx_hash, tx_data in wallet_tx_data.items():
            if "Input_True_Rings" in tx_data.keys():
                data[tx_hash] = tx_data
                total_txs += 1
            else:
                num_bad_txs += 1
    print("There were " + str(num_bad_txs) + " bad transactions that were deleted out of a total " + str(total_txs) + " transactions!")
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
    # del transaction['Outputs']['Output_Data']
    # del transaction['Outputs']['Decoys_On_Chain']  # TODO NEED TO EXPAND UPON THIS
    for idx, input in enumerate(transaction['Inputs']):
        del input['Key_Image']
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
    del transaction['Tx_Extra']  # TODO NEED TO USE THIS LATER ON
    del transaction['Num_Output_Decoys']  # TODO
    del transaction['Block_To_xmr2csv_Time_Delta']
    return private_info


def create_feature_set(database):
    """
    This function takes in a nested python dictionary dataset, removes
    any entries that would not be a useful feature to a machine learning
    model, flattens the dictionary and converts it to a dataframe. An
    accompanying labels list is also returned.
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
            continue  # Dont process the tx and loop
        #  Flatten each transaction and iterate over each feature
        for k, v in CherryPicker(database[tx_hash]).flatten(delim='.').get().items():
            #  Check if the feature name is not already in the feature set
            if k not in feature_set.keys():
                feature_set[k] = []
                #  add any missing values
                for i in range(num_of_valid_txs-1):
                    feature_set[k].append(-1)
                #  Add it as a new feature
                feature_set[k].append(v)
            else:  # If the feature is already in the feature set
                #  Check if there are any transactions that did not have this feature
                if len(feature_set[k]) < num_of_valid_txs:
                    #  Add -1 for those occurrences
                    for i in range(num_of_valid_txs-len(feature_set[k])-1):
                        feature_set[k].append(-1)
                #  Append the feature
                feature_set[k].append(v)
        num_of_valid_txs += 1
        #  add the labels to the list
        labels.append(private_info)

    print("Number of skipped transactions:", num_errors)
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
    feature_set_df, labels = shuffle(feature_set_df, labels)

    #  Reset the indexing after the shuffles
    feature_set_df.reset_index(drop=True, inplace=True)

    #  Replace any Null values with -1
    return feature_set_df, labels


def undersample_processing(y, temp_df, min_occurrences, occurrences):
    """

    :param y:
    :param ns:
    :param min_occurrences:
    :param occurrences:
    :return:
    """
    undersampled_y = []
    new_X = []
    y_idx, ring_array = y
    #  For each array of ring members iterate over each index
    for ring_array_idx in range(len(ring_array["True_Ring_Pos"])):
        #  Get the true ring position (label) for the current iteration
        ring_pos = int(ring_array["True_Ring_Pos"][ring_array_idx].split("/")[0])
        total_rings = int(ring_array["True_Ring_Pos"][ring_array_idx].split("/")[1])
        #  Check to see if we hit the maximum number of labels for this position and that the
        #  number of ring members is what we expect.
        if occurrences[ring_pos] < min_occurrences and total_rings == NUM_RING_MEMBERS:
            occurrences[ring_pos] = occurrences[ring_pos] + 1
            #  https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.iloc.html#pandas.DataFrame.iloc
            #  Slice out the row from the dataframe but keep it as a dataframe
            #temp_df = ns.X.iloc[[y_idx]]
            #  https://stackoverflow.com/questions/57392878/how-to-speed-up-pandas-drop-method
            #  Check if the column name has data relating to irrelevant ring signatures and Delete the columns
            temp_df.drop([column for column in temp_df.columns if "Inputs." in column and "." + str(ring_array_idx) + "." not in column], axis=1, inplace=True)
            #  Check if the column name is for the current ring signature
            #  Rename the column such that it doesn't have the .0. or .1. positioning information
            temp_df.rename(columns={column: column.replace("Inputs." + str(ring_array_idx) + ".", "Input.") for column in temp_df.columns if "Inputs." in column and "." + str(ring_array_idx) + "." in column}, inplace=True)
            #  Add to the new X and y dataframes
            new_X.append(temp_df)
            undersampled_y.append(ring_pos)
    return new_X, undersampled_y


def undersample_processing_wrapper(y_X_min_occurrences_Occurrences):
    """

    :param y_X_min_occurrences_Occurrences:
    :return:
    """
    # from line_profiler import LineProfiler
    # lp = LineProfiler()
    # lp_wrapper = lp(undersample_processing)
    # X_Undersampled, y_Undersampled = lp_wrapper(*y_X_min_occurrences_Occurrences)
    # lp.print_stats()
    # return X_Undersampled, y_Undersampled
    return undersample_processing(*y_X_min_occurrences_Occurrences)


def undersample(X, y):
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
    #  Reset pandas indexing just incase
    X.reset_index(drop=True, inplace=True)
    #  Count the amount of true labels at each position in the ring signature
    labels_distribution = Counter(flattened_true_spend)

    # Error checking
    try:
        #  Make sure that there are no classes with 0 labels
        assert len(labels_distribution) == NUM_RING_MEMBERS
    except AssertionError as e:
        print(red + "Error: The dataset contains at least one class which has 0 labels!" + reset)
        exit(1)

    #  Find the smallest number of occurrences
    min_occurrences = labels_distribution.most_common()[len(labels_distribution)-1][1]
    print("Undersampling to " + str(min_occurrences) + " transactions per class. A total of " + str(min_occurrences*NUM_RING_MEMBERS) + " transactions.")
    #max_occurrences = labels_distribution.most_common(1)[0][1]

    undersampled_y = []
    new_X = []
    enumerated_y = list(enumerate(y))
    del y
    collect()  # Garbage collector
    enumerated_X = []
    #enumerated_X = [X.iloc[[idx]] for idx, _ in enumerated_y]
    if not exists("./Dataset_Files/enumerated_X.pkl"):
        for i in tqdm(range(len(enumerated_y)), desc="Splicing Dataset Into Chunks", total=len(enumerated_y), colour='blue'):
            enumerated_X.append(X.iloc[0])
            X = X[1:]
            if i % 100000 == 0:
                collect()
        del X  # Remove the old dataset to save RAM
        collect()  # Garbage collector
        with open("./Dataset_Files/enumerated_X.pkl", "wb") as fp:
            pickle.dump(enumerated_X, fp)
        print("./Dataset_Files/enumerated_X.pkl Written to disk!")
    else:
        del X  # Remove the old dataset to save RAM
        collect()  # Garbage collector
        with open("./Dataset_Files/enumerated_X.pkl", "rb") as fp:
            enumerated_X = pickle.load(fp)
    assert len(enumerated_X) == len(enumerated_y)
    with Manager() as manager:
        #  Create a dictionary for all 11 spots in a ring signature
        occurrences = manager.dict()
        for i in range(NUM_RING_MEMBERS):
            occurrences[i + 1] = 0
        #  Multiprocessing enriching each transaction
        with manager.Pool(processes=NUM_PROCESSES) as pool:
            for result in tqdm(pool.imap_unordered(func=undersample_processing_wrapper,
                                                   iterable=zip(
                                                                enumerated_y,
                                                                enumerated_X,
                                                                repeat(min_occurrences, len(enumerated_y)),
                                                                repeat(occurrences, len(enumerated_y))
                                                                )
                                                   ),
                               desc="(Multiprocessing) Undersampling Dataset",
                               total=len(enumerated_y),
                               colour='blue'
                               ):
                subset_new_X = result[0]
                subset_undersampled_y = result[1]
                #  Add to the new X and y dataframes
                new_X = new_X + subset_new_X
                undersampled_y = undersampled_y + subset_undersampled_y

    # Combine the list of dataframes together into a single DF
    undersampled_X = concat(new_X, axis=0)
    del new_X
    collect()  # Garbage collector
    undersampled_X.reset_index(drop=True, inplace=True)

    # Sometimes there is a race condition where a class will get +1 samples in the class
    # This happens due to the shared memory and multiprocessing
    if not len(undersampled_X) == len(undersampled_y) == (min_occurrences * NUM_RING_MEMBERS):
        #  Find the number of occurrences for each class, so we can find the locate the outlier
        for class_num, class_occurrences in Counter(undersampled_y).items():
            #  Check if the number of occurrences is not equal to the undersampled amount
            if class_occurrences != min_occurrences:
                #  Iterate the number of times the extra class occurred
                for _ in range(class_occurrences-min_occurrences):
                    #  Iterate over the labels
                    for pos, val in enumerate(undersampled_y):
                        #  Check if the label is an occurrence of the bad class
                        if val == class_num:
                            #  Delete the entry
                            undersampled_X.drop(undersampled_X.index[[pos]], inplace=True)
                            del undersampled_y[pos]
                            print("Cleaned Undersampled Entry")
                            break
    #  Error Checking
    assert len(undersampled_X) == len(undersampled_y) == (min_occurrences * NUM_RING_MEMBERS)
    for _, class_occurrences in Counter(undersampled_y).items():
        assert class_occurrences == min_occurrences

    # Shuffle the data one last time
    undersampled_X, undersampled_y = shuffle(undersampled_X, undersampled_y)
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
        fp.write("HEADERS"+"\n")  # Keep a placeholder for the column names
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


def main():
    # Error Checking for command line args
    if len(argv) != 2:
        print("Usage Error: ./create_dataset.py < Wallets Directory Path >")
        exit(1)
    try:  # Check to see if the API URL given can be connected
        assert get(API_URL + "/block/1").status_code == 200
    except ConnectionError as e:
        print("Error: " + red + NETWORK + reset + " block explorer located at " + API_URL + " refused connection!")
        exit(1)
    # Configuration alert
    print("The dataset is being collected for the " + blue + NETWORK + reset + " network using " + API_URL + " as a block explorer!")

    if exists("./Dataset_Files/dataset.csv"):
        while True:
            answer = input(blue + "Dataset files exists already. They will be overwritten, Delete them? (y/n)" + reset)
            if answer.lower()[0] == "y":
                remove("./Dataset_Files/dataset.csv")
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

    #  Save data and labels to disk for future AI training
    with open("./Dataset_Files/X.pkl", "wb") as fp:
        pickle.dump(X, fp)
        X.to_csv('./Dataset_Files/X.csv', index=False, header=True)
    with open("./Dataset_Files/y.pkl", "wb") as fp:
        pickle.dump(y, fp)
    #  Error checking; labels and data should be the same length
    assert len(X) == len(y)
    print("./Dataset_Files/X.pkl, ./Dataset_Files/X.csv and ./Dataset_Files/y.pkl were written to disk!")

    ###################
    #  Undersampling  #
    ###################
    with open("./Dataset_Files/X.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("./Dataset_Files/y.pkl", "rb") as fp:
        y = pickle.load(fp)

    X_Undersampled, y_Undersampled = undersample(X, y)
    del X
    collect()  # Garbage collector

    with open("./Dataset_Files/X_Undersampled.pkl", "wb") as fp:
        pickle.dump(X_Undersampled, fp)
    X_Undersampled.to_csv('./Dataset_Files/X_Undersampled.csv', index=False, header=True)
    with open("./Dataset_Files/y_Undersampled.pkl", "wb") as fp:
        pickle.dump(y_Undersampled, fp)

    print("./Dataset_Files/X_Undersampled.pkl and ./Dataset_Files/y_Undersampled.pkl written to disk!\nFinished")


if __name__ == '__main__':
    try:
        main()
    # Gracefully exits if user hits CTRL + C
    except KeyboardInterrupt as e:
        print("Error: User stopped the script's execution!")
        exit(1)
    except Exception as e:
        import traceback
        print(e)
        print(traceback.print_exc())
        exit(1)

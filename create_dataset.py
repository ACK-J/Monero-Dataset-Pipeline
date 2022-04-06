import pickle
from sys import argv
from time import time
from tqdm import tqdm
from gc import collect
from requests import get
from os.path import exists
from statistics import median
from datetime import datetime
from collections import Counter
from os import walk, getcwd, chdir
from pandas import DataFrame, concat
from cherrypicker import CherryPicker  # https://pypi.org/project/cherrypicker/
from multiprocessing import Pool, cpu_count
from requests.exceptions import ConnectionError

'''
Description: Once transactions have been exported from collect.sh this script will combine
             the resulting six files, per wallet, into a central database. After the unique 
             information is pulled from each of the files, an enrichment phase will start.
             During enrichment, the script will contact a Monero block explorer and collect
             interesting heuristics and history associated to the transaction. The dataset
             will be serialized to disk in the current working directory. The next stage will
             clean the dataset into only relevant features and serialize an X and y dataframe
             which can be used for machine learning applications.
Usage: ./create_dataset.py < Wallets Directory Path >
Date: 4/5/2022
Author: ACK-J

Warning: DO NOT run this with a remote node, there are a lot of blockchain lookups and it will be slow!
Warning: Run your own monerod process and block explorer
To run your own block explorer:
    monerod --stagenet                        https://github.com/monero-project/monero
    xmrblocks --stagenet --enable-json-api    https://github.com/moneroexamples/onion-monero-blockchain-explorer
            
'''

data = {}  # Key = tx hash, val = dict(transaction metadata)
NUM_PROCESSES = cpu_count()  # Set the number of processes for multiprocessing
NETWORK = "testnet"
API_URL = "https://community.rino.io/explorer/" + NETWORK + "/api"  # Remote Monero Block Explorer
API_URL = "http://127.0.0.1:8081/api"  # Local Monero Block Explorer


def enrich_data(tx_dict_item):
    """

    :param tx_dict_item:
    :return:
    """
    tx_hash = tx_dict_item[0]
    transaction_entry = tx_dict_item[1]

    tx_response = get(API_URL + "/transaction/" + str(tx_hash)).json()["data"]
    block_response = get(API_URL + "/block/" + str(tx_response["block_height"])).json()["data"]
    previous_block_response = get(API_URL + "/block/" + str(int(tx_response["block_height"]) - 1)).json()["data"]
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
        decoy_tx_response = get(API_URL + "/transaction/" + str(Decoy['Tx_Hash'])).json()["data"]
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
                    Ring_Member_Times.append(get(API_URL + "/block/" + str(each_member['block_no'])).json()['data']['timestamp'])
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
    for input in tx_response['inputs']:
        transaction_entry['Inputs'].append(
            {
                'Amount': input['amount'],
                'Key_Image': input['key_image'],
                'Ring_Members': input['mixins']
            }
        )

    # Calculate lengths
    transaction_entry['Num_Inputs'] = len(transaction_entry['Inputs'])
    transaction_entry['Num_Outputs'] = len(transaction_entry['Outputs']['Output_Data'])
    transaction_entry['Num_Decoys'] = len(transaction_entry['Outputs']['Decoys_On_Chain'])
    transaction_entry['Block_To_xmr2csv_Time_Delta'] = int((datetime.fromtimestamp(transaction_entry['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(transaction_entry['Block_Timestamp_Epoch'])).total_seconds())

    # Temporal Features
    if len(transaction_entry['Inputs']) != 0:
        for input_idx, each_input in enumerate(transaction_entry['Inputs']):
            transaction_entry['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'] = {}
            #  A place to store the block times of each ring member
            ring_mem_times = []
            if len(each_input['Ring_Members']) != 0:
                for ring_num, ring_mem in enumerate(each_input['Ring_Members']):
                    ring_mem_times.append(get(API_URL + "/block/" + str(ring_mem['block_no'])).json()['data']['timestamp'])
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

    # Move labels to Input dictionary
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
            decoys_on_chain_times.append(get(API_URL + "/block/" + str(each_member['Block_Number'])).json()['data']['timestamp'])
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
                            wallet_tx_data[tx_hash]['Tx_Version'] = xmr2csv_report_csv_values[4].strip()
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
                                    # if len(wallet_tx_data[tx_hash]['Outputs']['Decoys_On_Chain']) >= 10:
                                    #     break

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
                print("Warning: " + str(Wallet_dir) + " did not contain any transactions!")

    return wallet_tx_data


def discover_wallet_directories(dir_to_search):
    """

    :param dir_to_search:
    :return:
    """
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
    for idx, dir in tqdm(enumerate(unique_directories), desc="Enumerating wallet files", total=len(unique_directories), colour='blue'):
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
    collect()
    # Multiprocess combining the 6 files for each wallet
    global data
    total_txs = 0
    num_bad_txs = 0
    pool = Pool(processes=NUM_PROCESSES)
    for wallet_tx_data in tqdm(pool.imap_unordered(func=combine_files, iterable=Wallet_info), desc="Multiprocessing Combining Exported Transactions", total=len(Wallet_info), colour='blue'):
        #  Make sure there are transactions in the data before adding it to the dataset
        for tx_hash, tx_data in wallet_tx_data.items():
            if "Input_True_Rings" in tx_data.keys():
                data[tx_hash] = tx_data
                total_txs += 1
            else:
                num_bad_txs += 1
    print("There were " + str(num_bad_txs) + " bad transactions that were deleted out of a total " + str(total_txs) + " transactions!")
    print("Dataset now includes " + str(len(data)) + " transactions.")


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
    del transaction['Num_Decoys']  # TODO
    del transaction['Block_To_xmr2csv_Time_Delta']
    collect()
    return private_info


def create_feature_set(database):
    """
    This function takes in a nested python dictionary dataset, removes
    any entries that would not be a useful feature to a machine learning
    model, flattens the dictionary and converts it to a dataframe. An
    accompanying labels dataframe is also created.
    :param database: Nested dictionary of Monero transaction metadata
    :return: A pandas dataframe of the input data and a list of labels
    """
    feature_set = DataFrame()
    labels = []
    Valid_Transactions = []
    num_errors = 0
    #  Iterate through each tx hash
    for idx, tx_hash in tqdm(enumerate(database.keys()), total=len(database), colour='blue', desc="Cleaning Transactions"):
        #  Pass the transaction ( by reference ) to be stripped of non-features and receive the labels back
        try:
            private_info = clean_transaction(database[tx_hash])
        except Exception as e:
            num_errors += 1
            continue
        #  add tx hash to good list
        Valid_Transactions.append(DataFrame(CherryPicker(database[tx_hash]).flatten(delim='.').get(), index=[idx]))
        #  add the labels to the list
        labels.append(private_info)

    print("Number of skipped transactions:", num_errors)
    del database
    collect()  # Garbage Collector

    # Combine dataframes together
    feature_set = concat(Valid_Transactions, axis=0)

    #  Replace any Null values with -1
    return feature_set.fillna(-1), labels


def undersample(X, y):
    """

    :param X:
    :param y:
    :return:
    """
    #  Only get the label we need
    true_spend = []
    for record in y:
        for idx, ring_pos in record["True_Ring_Pos"].items():
            true_spend.append(int(ring_pos.split("/")[0]))

    X.reset_index(drop=True, inplace=True)
    labels_distribution = Counter(true_spend)
    min_occurrences = labels_distribution.most_common()[len(labels_distribution)-1][1]
    print("Undersampling to " + str(min_occurrences) + " transactions per class.")
    #max_occurrences = labels_distribution.most_common(1)[0][1]
    occurrences = {}
    new_y = []
    new_X = []
    for i in range(len(labels_distribution)):
        occurrences[i+1] = 0
    for idx, val in tqdm(enumerate(y), total=len(y), colour='blue', desc="Undersampling Dataset"):
        for i in range(len(val["True_Ring_Pos"])):
            ring_pos = int(val["True_Ring_Pos"][i].split("/")[0])
            if occurrences[ring_pos] < min_occurrences:
                occurrences[ring_pos] = occurrences[ring_pos] + 1
                # https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.iloc.html#pandas.DataFrame.iloc
                temp_df = X.iloc[[idx]]
                if len(val["True_Ring_Pos"]) != 1:
                    for col in X.columns:
                        if "." in col and "." + str(i) + "." not in col:
                            temp_df.replace([col], -1.0)
                new_X.append(temp_df)
                new_y.append(true_spend[idx + i])
    del X
    collect()
    # Combine dataframes together
    undersampled_X = concat(new_X, axis=0)
    del new_X
    collect()
    undersampled_X.reset_index(drop=True, inplace=True)
    return undersampled_X, new_y


def main():
    # Error Checking
    if len(argv) != 2:
        print("Usage Error: ./create_dataset.py < Wallets Directory Path >")
        exit(1)
    try:
        assert get(API_URL + "/block/1").status_code == 200
    #  Check to see if the API URL given can be connected to
    except ConnectionError as e:
        print("Error: " + NETWORK + " block explorer located at " + API_URL + " refused connection!")
        exit(1)
    # Configuration warnings
    print("The dataset is being collected for the " + NETWORK + " using " + API_URL + " as a block explorer!")

    ###########################################
    #  Create the dataset from files on disk  #
    ###########################################
    global data
    print("Opening " + str(argv[1]) + "\n")
    #  Find where the wallets are stored and combine the exported files
    discover_wallet_directories(argv[1])

    #  https://leimao.github.io/blog/Python-tqdm-Multiprocessing/
    #  https://thebinarynotes.com/python-multiprocessing/
    #  https://docs.python.org/3/library/multiprocessing.html
    pool = Pool(processes=NUM_PROCESSES)
    for result in tqdm(pool.imap_unordered(func=enrich_data, iterable=list(data.items())), desc="Multiprocessing Enriching Transaction Data", total=len(data), colour='blue'):
        tx_hash, transaction_entry = result[0], result[1]
        data[tx_hash] = transaction_entry
    #  Save the raw database to disk
    with open("dataset.pkl", "wb") as fp:
        pickle.dump(data, fp)
    print("dataset.pkl written to disk!")

    ###############################
    #  Load in the saved dataset  #
    ###############################
    with open("dataset.pkl", "rb") as fp:
        data = pickle.load(fp)
    #  Feature selection on raw dataset
    X, y = create_feature_set(data)
    X.reset_index(drop=True, inplace=True)
    #  Save data and labels to disk for future AI training
    with open("X.pkl", "wb") as fp:
        pickle.dump(X, fp)
    with open("y.pkl", "wb") as fp:
        pickle.dump(y, fp)
    #  Error checking; labels and data should be the same length
    assert len(X) == len(y)
    print("X.pkl and y.pkl written to disk!")

    ###################
    #  Undersampling  #
    ###################

    with open("X.pkl", "rb") as fp:
        X = pickle.load(fp)
    with open("y.pkl", "rb") as fp:
        y = pickle.load(fp)

    print("Starting to undersample the dataset...")
    X_Undersampled, y_Undersampled = undersample(X, y)

    with open("X_Undersampled.pkl", "wb") as fp:
        pickle.dump(X_Undersampled, fp)
    with open("y_Undersampled.pkl", "wb") as fp:
        pickle.dump(y_Undersampled, fp)

    print("X_Undersampled.pkl and y_Undersampled.pkl written to disk!\nFinished")


if __name__ == '__main__':
    try:
        main()
    # Gracefully exits if user hits CTRL + C
    except KeyboardInterrupt as e:
        print("Error: User stopped the script's execution!")
        exit(1)
    except Exception as e:
        print("ERROR: " +str(e))
        exit(1)

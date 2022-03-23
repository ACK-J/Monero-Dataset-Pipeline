import os
import sys
import time
import pickle
import requests
from datetime import datetime
from statistics import median

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

Warning: DO NOT run this script with a remote node, there are a lot of blockchain lookups!
Warning: Run your own monerod process and block explorer
To run your own block explorer:
    monerod --testnet                        https://github.com/monero-project/monero
    xmrblocks --testnet --enable-json-api    https://github.com/moneroexamples/onion-monero-blockchain-explorer
            
'''


data = {}  # Key = tx hash, val = dict(transaction metadata)
NETWORK = "testnet"
API_URL = "https://community.rino.io/explorer/" + NETWORK + "/api"  # Remote Explorer
API_URL = "http://127.0.0.1:8081/api"  # Local Explorer


def enrich_data(tx_hash):
    """

    :param tx_hash:
    :return:
    """
    print(tx_hash)
    global data
    tx_response = requests.get(API_URL + "/transaction/" + str(tx_hash)).json()["data"]
    block_response = requests.get(API_URL + "/block/" + str(tx_response["block_height"])).json()["data"]
    previous_block_response = requests.get(API_URL + "/block/" + str(int(tx_response["block_height"]) - 1)).json()["data"]
    data[tx_hash]['Tx_Size'] = tx_response["tx_size"]
    # Check if the fee is missing
    if 'Tx_Fee' not in data[tx_hash].keys():
        data[tx_hash]['Tx_Fee'] = float(tx_response['tx_fee'] * 0.000000000001) #  Converted from piconero to monero
    data[tx_hash]['Tx_Fee_Per_Byte'] = float(data[tx_hash]['Tx_Fee']) / int(data[tx_hash]['Tx_Size'])
    data[tx_hash]['Num_Confirmations'] = tx_response["confirmations"]
    data[tx_hash]['Time_Of_Enrichment'] = int(time.time())
    if tx_response["coinbase"] == "false":
        data[tx_hash]['Is_Coinbase_Tx'] = False
    elif tx_response["coinbase"] == "true":
        data[tx_hash]['Is_Coinbase_Tx'] = True
    data[tx_hash]['Tx_Extra'] = tx_response["extra"]
    data[tx_hash]['Ring_CT_Type'] = tx_response["rct_type"]
    data[tx_hash]['Payment_ID'] = tx_response["payment_id"]
    data[tx_hash]['Payment_ID8'] = tx_response["payment_id8"]

    Total_Block_Tx_Fees = 0
    for tx in block_response["txs"]:
        Total_Block_Tx_Fees += int(tx["tx_fee"])
    data[tx_hash]['Total_Block_Tx_Fees'] = float(Total_Block_Tx_Fees * 0.000000000001) #  Converted from piconero to monero
    data[tx_hash]['Block_Size'] = block_response["size"]
    data[tx_hash]['Time_Since_Last_Block'] = int((datetime.fromtimestamp(int(block_response["timestamp"])) - datetime.fromtimestamp(int(previous_block_response["timestamp"]))).total_seconds())

    #  Output info
    for Decoy in data[tx_hash]['Outputs']['Decoys_On_Chain']:
        #  Add Temporal Features for the decoy ( This takes up a ton of time )
        #  Retrieve the transaction information about the decoy ring signatures
        decoy_tx_response = requests.get(API_URL + "/transaction/" + str(Decoy['Tx_Hash'])).json()["data"]
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
                    Ring_Member_Times.append(requests.get(API_URL + "/block/" + str(each_member['block_no'])).json()['data']['timestamp'])
                    #  If the list has at least 2 items
                    if len(Ring_Member_Times) > 1:
                        time_delta = int((datetime.fromtimestamp(Ring_Member_Times[member_idx]) - datetime.fromtimestamp(Ring_Member_Times[member_idx - 1])).total_seconds())
                        Decoy['Time_Deltas_Between_Ring_Members'][str(member_idx - 1) + '_' + str(member_idx)] = time_delta
                        # Add temporal features
                        #  Calculate the total time span of the ring signature ( newest ring on chain block time - oldest ring on chain block time )
                        Decoy['Time_Deltas_Between_Ring_Members']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(Ring_Member_Times[len(Ring_Member_Times) - 1]) - datetime.fromtimestamp(Ring_Member_Times[0])).total_seconds())
                        #  Calculate the time between the newest ring in the signature to the block time of the transaction
                        Decoy['Time_Deltas_Between_Ring_Members']['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(Ring_Member_Times[len(Ring_Member_Times) - 1])).total_seconds())
                        #  Calculate the time between the oldest ring in the signature to the block time of the transaction
                        Decoy['Time_Deltas_Between_Ring_Members']['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(Ring_Member_Times[0])).total_seconds())
                        #  Calculate the mean of the ring time
                        Decoy['Time_Deltas_Between_Ring_Members']['Mean_Ring_Time'] = int(sum(Ring_Member_Times) / len(Ring_Member_Times)) - Ring_Member_Times[0]
                        #  Calculate the median of the ring time
                        Decoy['Time_Deltas_Between_Ring_Members']['Median_Ring_Time'] = int(median(Ring_Member_Times)) - Ring_Member_Times[0]

    #  Add Input Information
    for input in tx_response['inputs']:
        data[tx_hash]['Inputs'].append(
            {
                'Amount': input['amount'],
                'Key_Image': input['key_image'],
                'Ring_Members': input['mixins']
            }
        )

    # Calculate lengths
    data[tx_hash]['Num_Inputs'] = len(data[tx_hash]['Inputs'])
    data[tx_hash]['Num_Outputs'] = len(data[tx_hash]['Outputs']['Output_Data'])
    data[tx_hash]['Num_Decoys'] = len(data[tx_hash]['Outputs']['Decoys_On_Chain'])
    data[tx_hash]['Block_To_xmr2csv_Time_Delta'] = int((datetime.fromtimestamp(data[tx_hash]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch'])).total_seconds())

    # Temporal Features
    if len(data[tx_hash]['Inputs']) != 0:
        for input_idx, each_input in enumerate(data[tx_hash]['Inputs']):
            data[tx_hash]['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'] = {}
            #  A place to store the block times of each ring member
            ring_mem_times = []
            if len(each_input['Ring_Members']) != 0:
                for ring_num, ring_mem in enumerate(each_input['Ring_Members']):
                    ring_mem_times.append(requests.get(API_URL + "/block/" + str(ring_mem['block_no'])).json()['data']['timestamp'])
                    #  If the list has at least 2 items
                    if len(ring_mem_times) > 1:
                        time_delta = int((datetime.fromtimestamp(ring_mem_times[ring_num]) - datetime.fromtimestamp(ring_mem_times[ring_num - 1])).total_seconds())
                        data[tx_hash]['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'][str(ring_num-1) + '_' + str(ring_num)] = time_delta
            if len(ring_mem_times) > 1:
                # Add temporal features
                #  Calculate the total time span of the ring signature ( newest ring on chain block time - oldest ring on chain block time )
                data[tx_hash]['Inputs'][input_idx]['Total_Ring_Time_Span'] = int((datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1]) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                #  Calculate the time between the newest ring in the signature to the block time of the transaction
                data[tx_hash]['Inputs'][input_idx]['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1])).total_seconds())
                #  Calculate the time between the oldest ring in the signature to the block time of the transaction
                data[tx_hash]['Inputs'][input_idx]['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                #  Calculate the mean of the ring time
                data[tx_hash]['Inputs'][input_idx]['Mean_Ring_Time'] = int(sum(ring_mem_times) / len(ring_mem_times)) - ring_mem_times[0]
                #  Calculate the median of the ring time
                data[tx_hash]['Inputs'][input_idx]['Median_Ring_Time'] = int(median(ring_mem_times)) - ring_mem_times[0]

    #  Temporal features for decoys on chain
    data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain'] = {}
    if len(data[tx_hash]['Outputs']['Decoys_On_Chain']) != 0:
        #  A place to store the block times of each ring member
        decoys_on_chain_times = []
        for member_idx, each_member in enumerate(data[tx_hash]['Outputs']['Decoys_On_Chain']):
            decoys_on_chain_times.append(requests.get(API_URL + "/block/" + str(each_member['Block_Number'])).json()['data']['timestamp'])
            #  If the list has at least 2 items
            if len(decoys_on_chain_times) > 1:
                time_delta = int((datetime.fromtimestamp(decoys_on_chain_times[member_idx]) - datetime.fromtimestamp(decoys_on_chain_times[member_idx - 1])).total_seconds())
                data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain'][str(member_idx-1) + '_' + str(member_idx)] = time_delta
                # Add temporal features
                #  Calculate the total time span of the ring signature ( newest ring on chain block time - oldest ring on chain block time )
                data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(decoys_on_chain_times[0])).total_seconds())
                #  Calculate the time between the newest ring in the signature to the block time of the transaction
                data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Newest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch'])).total_seconds())
                #  Calculate the time between the oldest ring in the signature to the block time of the transaction
                data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Oldest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[0]) - datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch'])).total_seconds())
                #  Calculate the mean of the ring time
                data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Mean_Decoy_Time'] = sum(decoys_on_chain_times) / len(decoys_on_chain_times) - decoys_on_chain_times[0]
                #  Calculate the median of the ring time
                data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Median_Decoy_Time'] = int(median(decoys_on_chain_times)) - decoys_on_chain_times[0]


def combine_files(Wallet_addr):
    """

    :param Wallet_addr:
    :return:
    """
    global data
    #  CSV HEADER -> "block, direction, unlocked, timestamp, amount, running balance, hash, payment ID, fee, destination, amount, index, note"
    with open("./cli_export_" + Wallet_addr + ".csv", "r") as fp:
        next(fp)  # Skip header of csv
        for line in fp:
            cli_csv_values = line.split(",")
            if cli_csv_values[1].strip() == "out":  # Only add outgoing transactions to the dataset
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

                with open("./xmr2csv_start_time_" + Wallet_addr + ".csv", "r") as fp2:
                    for line2 in fp2:
                        transaction['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                        break
                #  Check if the hash is a key in the dataset
                if cli_csv_values[6].strip() not in data:
                    data[cli_csv_values[6].strip()] = transaction

    #  CSV HEADER -> "Timestamp,Block_no,Tx_hash,Tx_public_key,Tx_version,Payment_id,Out_idx,Amount,Output_pub_key,Output_key_img,Output_spend"
    with open("./xmr_report_" + Wallet_addr + ".csv", "r") as fp:
        next(fp)  # Skip header of csv
        for line in fp:
            xmr2csv_report_csv_values = line.split(",")
            tx_hash = xmr2csv_report_csv_values[2].strip()
            #  Check if the tx hash is in the dataset yet
            if xmr2csv_report_csv_values[2].strip() in data:
                data[tx_hash]['Tx_Version'] = xmr2csv_report_csv_values[4].strip()
                data[tx_hash]['Tx_Public_Key'] = xmr2csv_report_csv_values[3].strip()
                data[tx_hash]['Output_Pub_Key'] = xmr2csv_report_csv_values[8].strip()
                data[tx_hash]['Output_Key_Img'] = xmr2csv_report_csv_values[9].strip()
                data[tx_hash]['Out_idx'] = int(xmr2csv_report_csv_values[6].strip())
                data[tx_hash]['Wallet_Output_Number_Spent'] = int(xmr2csv_report_csv_values[10].strip())
                #  Add Output Information
                output_info = requests.get(API_URL + "/transaction/" + str(tx_hash)).json()["data"]['outputs']
                for output_idx, output in enumerate(output_info):
                    data[tx_hash]['Outputs']['Output_Data'].append({'Amount': output['amount'], 'Stealth_Address': output['public_key']})

                #  Open the file that has the timestamp from when the data was collected
                with open("./xmr2csv_start_time_" + Wallet_addr + ".csv", "r") as fp2:
                    for line2 in fp2:
                        data[tx_hash]['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                        break

                #  Search through the export of all ring member occurrences on chain to see if our output public key was used
                data[tx_hash]['Outputs']['Decoys_On_Chain'] = []

                #  CSV HEADERS -> "Timestamp,Block_no,Decoy_Tx_hash,Output_pub_key,Key_image,ring_no/ring_size"
                with open("./xmr_report_ring_members_" + Wallet_addr + ".csv", "r") as fp2:
                    next(fp2)  # Skip header of csv
                    for line2 in fp2:
                        ring_members_csv_values = line2.split(",")
                        Ring_Member = {}
                        #  Iterate through each output from the transaction
                        for tx_output in data[tx_hash]['Outputs']['Output_Data']:
                            #  Make sure the ring members public key matches an output in this transaction
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
                                Ring_Member['Ring_Member_Relative_Age'] = int((datetime.fromtimestamp(data[tx_hash]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(Ring_Member['Block_Timestamp'])).total_seconds())

                                #  CSV HEADERS -> "Output_pub_key,Frequency,Ring_size"
                                with open("./xmr_report_ring_members_freq_" + Wallet_addr + ".csv", "r") as fp3:
                                    next(fp3)  # Skip header of csv
                                    for line3 in fp3:
                                        ring_member_freq_csv_values = line3.split(",")
                                        #  Check if the ring members public key matches the current public key
                                        if data[tx_hash]['Output_Pub_Key'] == ring_member_freq_csv_values[0].strip():
                                            #  Add the amount of times it has been seen on chain
                                            Ring_Member['Ring_Member_Freq'] = int(ring_member_freq_csv_values[1].strip())
                                data[tx_hash]['Outputs']['Decoys_On_Chain'].append(Ring_Member)
                        #  Only collect 10 decoys found on chain because it gets too resource intensive when
                        #  calculating all the temporal features for every decoy's ring signatures
                        # if len(data[tx_hash]['Outputs']['Decoys_On_Chain']) >= 10:
                        #     break

    #  CSV HEADERS -> "Timestamp,Block_no,Tx_hash,Output_pub_key,Key_image,Ring_no/Ring_size"
    with open("./xmr_report_outgoing_txs_" + Wallet_addr + ".csv", "r") as fp:
        next(fp)  # Skip header of csv
        for line in fp:
            xmr2csv_outgoing_csv_values = line.split(",")
            if xmr2csv_outgoing_csv_values[2].strip() in data:
                data[xmr2csv_outgoing_csv_values[2].strip()]['Ring_no/Ring_size'] = xmr2csv_outgoing_csv_values[5].strip()


def discover_wallet_directories(dir_to_search):
    """

    :param dir_to_search:
    :return:
    """
    # traverse root directory, and list directories as dirs and files as files
    unique_directories = []
    for root, dirs, files in os.walk(dir_to_search):
        for name in files:
            #  Find all csv files
            if name.lower().endswith(".csv"):
                #  Find all the unique folders holding csv files
                if root not in unique_directories:
                    unique_directories.append(root)
    cwd = os.getcwd()  # Set a starting directory
    #  Go through each directory that has csv files in it
    for idx, dir in enumerate(unique_directories):
        os.chdir(dir)
        Wallet_addrs = []
        for root, dirs, files in os.walk("."):
            for name in files:
                #  Get each csv file
                if name.lower().endswith(".csv"):
                    #  Extract the 2 unique wallet addr from the name of the files
                    addr = name[::-1].split(".")[1].split("_")[0][::-1]
                    if addr not in Wallet_addrs:
                        Wallet_addrs.append(addr)
                    #  Dont keep looking if the two wallet addresses are already found
                    if len(Wallet_addrs) == 2:
                        break
        #  Once the two wallet addr are found send the list to combine the files
        for address in Wallet_addrs:
            combine_files(address)
        os.chdir(cwd)


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
    del transaction['Direction']
    del transaction['Block_Timestamp']
    private_info['Tx_Amount'] = transaction['Amount']
    del transaction['Amount']
    private_info['Wallet_Balance'] = transaction['Wallet_Balance']
    del transaction['Wallet_Balance']
    del transaction['Destination_Address']
    del transaction['Sender_Address']
    del transaction['Network']
    del transaction['Outputs']['Output_Data']
    del transaction['Outputs']['Decoys_On_Chain']  # TODO NEED TO EXPAND UPON THIS
    for input in transaction['Inputs']:
        del input['Key_Image']
        del input['Ring_Members']
    del transaction['Tx_Public_Key']
    del transaction['Output_Pub_Key']
    del transaction['Output_Key_Img']
    private_info['Out_idx'] = transaction['Out_idx']
    del transaction['Out_idx']
    private_info['Wallet_Output_Number_Spent'] = transaction['Wallet_Output_Number_Spent']
    del transaction['Wallet_Output_Number_Spent']
    private_info['Ring_no/Ring_size'] = transaction['Ring_no/Ring_size']
    del transaction['Ring_no/Ring_size']
    del transaction['Payment_ID']
    del transaction['Payment_ID8']
    del transaction['Tx_Extra']  # TODO NEED TO USE THIS LATER ON
    del transaction['Num_Decoys']  # TODO
    return private_info


def create_feature_set(database):
    """
    This function takes in a nested python dictionary dataset, removes
    any entries that would not be a useful feature to a machine learning
    model, flattens the dictionary and converts it to a dataframe. An
    accompanying labels dataframe is also created.
    :param database: Nested dictionary of Monero transaction metadata
    :return: A pandas dataframe of the input data and labels
    """
    import pandas as pd
    from cherrypicker import CherryPicker  # https://pypi.org/project/cherrypicker/
    feature_set = pd.DataFrame()
    labels = pd.DataFrame()
    #  Iterate through each tx hash
    for idx, tx_hash in enumerate(database.keys()):
        #  Get the transaction
        transaction = database[tx_hash]
        #  Pass the transaction ( by reference ) to be stripped of non-features and receive the labels back
        private_info = clean_transaction(transaction)
        #  flatten the transaction data so it can be input into a dataframe
        transaction = CherryPicker(transaction).flatten(delim='.').get()
        #  add the transaction to the feature set dataframe
        feature_set = pd.concat([feature_set, pd.DataFrame(transaction, index=[idx])])
        #  add the labels to the dataframe
        labels = pd.concat([labels, pd.DataFrame(private_info, index=[idx])])
    #  Replace any Null values with -1
    return feature_set.fillna(-1), labels


def main():
    #  Error Checking
    if len(sys.argv) != 2:
        print("Usage Error: ./create_dataset.py < Wallets Directory Path >")
    try:
        assert requests.get(API_URL + "/block/1").status_code == 200
    except requests.exceptions.ConnectionError as e:
        print("Error: " + NETWORK + " block explorer located at " + API_URL + " refused connection!")
        exit(1)

    try:
        global data
        discover_wallet_directories(sys.argv[1])
        for tx_hash in data.keys():
            enrich_data(tx_hash)
        with open("data.pkl", "wb") as fp:
            pickle.dump(data, fp)

        with open("data.pkl", "rb") as fp:
            data = pickle.load(fp)
        X, y = create_feature_set(data)

        with open("X.pkl", "wb") as fp:
            pickle.dump(X, fp)
        with open("y.pkl", "wb") as fp:
            pickle.dump(y, fp)
    except KeyboardInterrupt as e:
        print("User stopped the script's execution!")
        exit(1)


if __name__ == '__main__':
    main()
